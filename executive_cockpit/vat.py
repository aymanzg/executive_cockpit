"""VAT return (الإقرار الضريبي) and sales / purchase registers.

Everything is built from the GL lines posted to the output and input VAT
accounts, one row per voucher, so the totals equal the trial-balance movement
of those accounts to the halala. The month-end settlement journal (which moves
both VAT accounts into the VAT settlement account) is excluded from the
movement and shown separately so it can be checked against the return.
"""

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe.utils import cint, get_last_day, getdate


RATE = Decimal("0.15")
ZERO = Decimal("0")
CENT = Decimal("0.01")
TOLERANCE = Decimal("1.00")  # per-invoice rounding slack before an invoice is treated as partly zero-rated
DOMESTIC = {"", "saudi arabia", "السعودية", "المملكة العربية السعودية", "ksa"}
MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
QUARTERS_AR = ["الربع الأول", "الربع الثاني", "الربع الثالث", "الربع الرابع"]

BOX_LABELS = {
	"1": "المبيعات الخاضعة للنسبة الأساسية",
	"2": "المبيعات للمواطنين (الخدمات الصحية الخاصة / التعليم الأهلي الخاص)",
	"3": "المبيعات المحلية الخاضعة للنسبة الصفرية",
	"4": "الصادرات",
	"5": "المبيعات المعفاة",
	"6": "إجمالي المبيعات",
	"7": "المشتريات الخاضعة للنسبة الأساسية",
	"8": "الاستيرادات الخاضعة للضريبة بالنسبة الأساسية والتي تُدفع في الجمارك",
	"9": "الاستيرادات الخاضعة للضريبة التي يُطبق عليها آلية الاحتساب العكسي",
	"10": "المشتريات الخاضعة للنسبة الصفرية",
	"11": "المشتريات المعفاة",
	"12": "إجمالي المشتريات",
	"13": "إجمالي ضريبة القيمة المضافة المستحقة عن الفترة الضريبية الحالية",
	"14": "تصحيحات من الفترات السابقة (بين ±5,000 ريال)",
	"15": "ضريبة القيمة المضافة التي تم ترحيلها من الفترة / الفترات السابقة",
	"16": "صافي الضريبة المستحقة (أو المستردة)",
}

CATEGORY_LABELS = {
	"standard": "أساسية 15%",
	"mixed": "أساسية وصفرية",
	"zero": "صفرية / غير خاضعة",
	"export": "صادرات",
	"adjustment": "قيد على حساب الضريبة",
}


def _core():
	# imported lazily: api.py re-exports this module's endpoints, so a top-level
	# import would be circular when this module is loaded first
	from executive_cockpit import api

	return api


def _d(v):
	return Decimal(str(v or 0))


def _q(v):
	return float(Decimal(v).quantize(CENT, rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------------
# Period and accounts
# ---------------------------------------------------------------------------


def _resolve(company, year=None, period_type="month", num=None):
	if not company or not frappe.db.exists("Company", company):
		frappe.throw("الشركة غير موجودة")
	t = getdate()
	year = cint(year) or t.year
	period_type = period_type if period_type in ("month", "quarter") else "month"
	if period_type == "quarter":
		num = min(max(cint(num) or (t.month - 1) // 3 + 1, 1), 4)
		f = date(year, (num - 1) * 3 + 1, 1)
		to = getdate(get_last_day(date(year, num * 3, 1)))
		label = f"{QUARTERS_AR[num - 1]} {year}"
	else:
		num = min(max(cint(num) or t.month, 1), 12)
		f = date(year, num, 1)
		to = getdate(get_last_day(f))
		label = f"{MONTHS_AR[num - 1]} {year}"
	return frappe._dict(company=company, year=year, period_type=period_type, num=num, label=label, **{"from": f, "to": to})


def _vat_accounts(company):
	"""Output / input VAT accounts (account type Tax) and the settlement account
	the month-end journal moves them into. Memoised in Redis for an hour."""
	r = _core()._redis()
	key = f"executive_cockpit:vat_accounts:{company}"
	hit = r.get_value(key, expires=True)
	if hit:
		return frappe._dict(hit)
	tax = frappe.db.sql(
		"""select a.name, a.root_type,
			exists(select 1 from `tabGL Entry` g force index (account) where g.account = a.name and g.is_cancelled = 0) used
		from `tabAccount` a
		where a.company = %s and a.account_type = 'Tax' and a.is_group = 0 and a.root_type in ('Liability', 'Asset')
		order by a.tax_rate desc, a.lft""",
		company,
		as_dict=True,
	)
	out = next((a.name for a in tax if a.root_type == "Liability" and a.used), None)
	inp = next((a.name for a in tax if a.root_type == "Asset" and a.used), None)
	if not out or not inp:
		frappe.throw("لم يتم العثور على حسابي ضريبة المخرجات والمدخلات (نوع الحساب: Tax) لهذه الشركة")
	jvs = frappe.db.sql(
		"""select distinct voucher_no from `tabGL Entry` force index (account)
		where account = %s and voucher_type = 'Journal Entry' and is_cancelled = 0 and debit > 0""",
		out,
		pluck=True,
	)
	settle = None
	if jvs:
		rows = frappe.db.sql(
			"""select s.account, count(distinct s.voucher_no) n
			from `tabGL Entry` s join `tabAccount` a on a.name = s.account
			where s.voucher_type = 'Journal Entry' and s.voucher_no in %(jvs)s and s.is_cancelled = 0
				and s.account not in (%(out)s, %(inp)s) and a.root_type = 'Liability'
			group by s.account order by n desc limit 1""",
			{"jvs": tuple(jvs), "out": out, "inp": inp},
		)
		settle = rows[0][0] if rows else None
	acc = {"output": out, "input": inp, "settlement": settle}
	r.set_value(key, acc, expires_in_sec=3600)
	return frappe._dict(acc)


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------


def _split(net, vat):
	"""Split a document's net amount into its standard-rated and zero-rated parts."""
	if not vat:
		return ZERO, net
	if abs(vat - net * RATE) <= TOLERANCE:
		return net, ZERO
	std = (vat / RATE).quantize(CENT, rounding=ROUND_HALF_UP)
	if abs(std) > abs(net):
		std = net
	return std, net - std


def _round_rows(rows, key, total):
	"""Round each row's exact amount to the halala so that the rounded rows add
	up exactly to the rounded total (largest remainder)."""
	if not rows:
		return
	target = Decimal(total).quantize(CENT, rounding=ROUND_HALF_UP)
	for r in rows:
		r["_r"] = r[key].quantize(CENT, rounding=ROUND_HALF_UP)
	diff = target - sum(r["_r"] for r in rows)
	steps = int((diff / CENT).to_integral_value())
	if steps:
		sign = 1 if steps > 0 else -1
		order = sorted(rows, key=lambda r: -sign * (r[key] - r["_r"]))
		for r in order[: abs(steps)]:
			r["_r"] += CENT * sign
	for r in rows:
		r[key] = r.pop("_r")


def _gl_scan(F, acc):
	"""One pass over the VAT accounts' GL up to the period end.

	Returns the exact VAT per voucher (output and input, settlement journal
	excluded), the settlement journals of the period and the trial-balance
	lines (opening, period debit / credit, closing) of each VAT account."""
	names = {k: acc[k] for k in ("output", "input", "settlement") if acc.get(k)}
	key_of = {v: k for k, v in names.items()}
	rows = frappe.db.sql(
		"""select account, voucher_type, if(posting_date < %(from)s, '', voucher_no) voucher_no,
			min(posting_date) posting_date, cast(sum(debit) as char) dr, cast(sum(credit) as char) cr
		from `tabGL Entry` force index (account)
		where account in %(accs)s and company = %(company)s and is_cancelled = 0 and posting_date <= %(to)s
		group by account, voucher_type, if(posting_date < %(from)s, '', voucher_no)""",
		{"company": F.company, "accs": tuple(names.values()), "from": F["from"], "to": F.to},
		as_dict=True,
	)
	tb = {k: {"opening": ZERO, "debit": ZERO, "credit": ZERO} for k in names}
	period = []
	settle_jvs = set()
	for r in rows:
		k = key_of[r.account]
		dr, cr = _d(r.dr), _d(r.cr)
		if not r.voucher_no:
			tb[k]["opening"] += dr - cr
			continue
		tb[k]["debit"] += dr
		tb[k]["credit"] += cr
		if k == "settlement":
			if r.voucher_type == "Journal Entry":
				settle_jvs.add(r.voucher_no)
		else:
			period.append((k, r, dr, cr))

	out, inp, by_jv = {}, {}, {}
	for k, r, dr, cr in period:
		vkey = (r.voucher_type, r.voucher_no)
		closing = dr if k == "output" else cr
		if r.voucher_type == "Journal Entry" and r.voucher_no in settle_jvs and closing:
			# the settlement journal closes output (debit) and input (credit) into the settlement account;
			# other journals on that account (VAT payments) keep their VAT lines, e.g. VAT on bank charges
			j = by_jv.setdefault(r.voucher_no, {"voucher": r.voucher_no, "date": r.posting_date, "output": ZERO, "input": ZERO})
			if k == "output":
				j["output"] += dr
				dr = ZERO
			else:
				j["input"] += cr
				cr = ZERO
			if not (dr or cr):
				continue
		if k == "output":
			out[vkey] = (cr - dr, r.posting_date)
		else:
			inp[vkey] = (dr - cr, r.posting_date)
	settlement = sorted(by_jv.values(), key=lambda j: (j["date"], j["voucher"]))

	lines = []
	for k, name in names.items():
		t = tb[k]
		settle = sum((j[k] for j in settlement), ZERO) if k != "settlement" else ZERO
		dr, cr = t["debit"], t["credit"]
		lines.append(
			{
				"key": k,
				"account": name,
				"opening": t["opening"],
				"debit": dr,
				"credit": cr,
				"closing": t["opening"] + dr - cr,
				"settlement": settle,
				# movement before the settlement journal, in the account's natural sign
				"movement": (cr - dr + settle) if k == "output" else (dr - cr + settle) if k == "input" else cr - dr,
			}
		)
	return out, inp, settlement, lines


def _fetch(doctype, names, fields):
	if not names:
		return {}
	out = {}
	names = list(names)
	for i in range(0, len(names), 2000):
		for r in frappe.get_all(doctype, filters={"name": ("in", names[i : i + 2000])}, fields=fields):
			out[r.name] = r
	return out


def _party_vat(doctype, names, fields):
	return {r.name: r for r in frappe.get_all(doctype, filters={"name": ("in", list(names))}, fields=fields)} if names else {}


def _countries(names):
	if not names:
		return {}
	return dict(frappe.get_all("Address", filters={"name": ("in", list(names))}, fields=["name", "country"], as_list=True))


def _doc_rows(F, gl, doctype, party_field, is_sales):
	"""Register rows for sales or purchase invoices: with VAT (from GL) and without VAT."""
	with_vat = {vn: v for (vt, vn), v in gl.items() if vt == doctype}
	no_vat = frappe.get_all(
		doctype,
		filters={
			"company": F.company,
			"docstatus": 1,
			"is_opening": "No",
			"posting_date": ("between", [F["from"], F.to]),
		},
		pluck="name",
	)
	no_vat = [n for n in no_vat if n not in with_vat]
	fields = ["name", "posting_date", party_field, f"{party_field}_name as party_name", "is_return", "return_against", "base_net_total", "tax_id"]
	if is_sales:
		fields += ["is_debit_note", "customer_address as address"]
	else:
		fields += ["bill_no", "bill_date", "supplier_address as address"]
	docs = _fetch(doctype, set(with_vat) | set(no_vat), fields)

	party_dt = "Customer" if is_sales else "Supplier"
	pfields = ["name", "tax_id"]
	if is_sales and _core()._has_col("Customer", "custom_vat_registration_number"):
		pfields.append("custom_vat_registration_number")
	parties = _party_vat(party_dt, {d[party_field] for d in docs.values() if d[party_field]}, pfields)
	countries = _countries({d.address for d in docs.values() if d.address})

	rows = []
	for name, d in docs.items():
		vat, posting = with_vat.get(name, (ZERO, d.posting_date))
		net = _d(d.base_net_total)
		std, zero = _split(net, vat)
		p = parties.get(d[party_field]) or {}
		vat_no = (d.tax_id or p.get("custom_vat_registration_number") or p.get("tax_id") or "").strip()
		foreign = (countries.get(d.address) or "").strip().lower() not in DOMESTIC
		if vat:
			category = "standard" if not zero else "mixed"
		else:
			category = "export" if (is_sales and foreign) else "zero"
		if is_sales:
			kind = "إشعار دائن" if d.is_return else "إشعار مدين" if d.is_debit_note else "فاتورة ضريبية" if vat_no else "فاتورة ضريبية مبسطة"
		else:
			kind = "إشعار مدين (مرتجع)" if d.is_return else "فاتورة مشتريات"
		rows.append(
			{
				"doctype": doctype,
				"name": name,
				"date": str(posting),
				"kind": kind,
				"party": d.party_name or d[party_field],
				"vat_no": vat_no,
				"bill_no": d.get("bill_no") or "",
				"bill_date": str(d.bill_date) if d.get("bill_date") else "",
				"ref": d.return_against or "",
				"category": category,
				"is_return": cint(d.is_return),
				"std": std,
				"zero": zero,
				"vat": vat,
				"estimated": False,
			}
		)
	return rows


def _other_rows(gl, doctypes_done, is_sales):
	"""Journal entries, payment entries and any other voucher posted directly to a VAT account."""
	keys = [(vt, vn) for (vt, vn) in gl if vt not in doctypes_done]
	if not keys:
		return []
	jv = _fetch("Journal Entry", {vn for vt, vn in keys if vt == "Journal Entry"}, ["name", "title", "user_remark", "bill_no", "bill_date"])
	pe = _fetch("Payment Entry", {vn for vt, vn in keys if vt == "Payment Entry"}, ["name", "party_name", "reference_no"])
	names = {
		"Journal Entry": "قيد يومية",
		"Payment Entry": "سند صرف / قبض",
		"Purchase Invoice": "فاتورة مشتريات (مرحّلة على حساب المخرجات)",
		"Sales Invoice": "فاتورة مبيعات (مرحّلة على حساب المدخلات)",
	}
	rows = []
	for vt, vn in keys:
		vat, posting = gl[(vt, vn)]
		j, p = jv.get(vn), pe.get(vn)
		party = (j and (j.title or (j.user_remark or "")[:80])) or (p and p.party_name) or ""
		# input VAT on a journal / payment line: the taxable base is derived from the VAT (VAT ÷ 15%)
		est = not is_sales and vt in ("Journal Entry", "Payment Entry")
		rows.append(
			{
				"doctype": vt,
				"name": vn,
				"date": str(posting),
				"kind": names.get(vt, vt),
				"party": party,
				"vat_no": "",
				"bill_no": (j and j.bill_no) or (p and p.reference_no) or "",
				"bill_date": str(j.bill_date) if j and j.bill_date else "",
				"ref": "",
				"category": "standard" if est else "adjustment",
				"is_return": 0,
				"std": (vat / RATE).quantize(CENT, rounding=ROUND_HALF_UP) if est else ZERO,
				"zero": ZERO,
				"vat": vat,
				"estimated": est,
			}
		)
	return rows


def _box(amount=ZERO, adjustment=ZERO, vat=ZERO):
	return {"amount": amount, "adjustment": adjustment, "vat": vat}


def _boxes(sales, purchases):
	b = {k: _box() for k in BOX_LABELS}

	def add(box, r, base):
		col = "adjustment" if r["is_return"] else "amount"
		b[box][col] += base

	# The ZATCA portal computes the VAT of boxes 1 and 7 as 15% of (amount + adjustment),
	# so their amounts are derived from the VAT itself (VAT ÷ 15%) - the same method the
	# filed returns use - and the box stays consistent with the VAT to the halala.
	for r in sales:
		add("1", r, r["vat"] / RATE)
		b["1"]["vat"] += r["vat"]
		if r["zero"]:
			add("4" if r["category"] == "export" else "3", r, r["zero"])
	for r in purchases:
		add("7", r, r["vat"] / RATE)
		b["7"]["vat"] += r["vat"]
		if r["zero"]:
			add("10", r, r["zero"])
	for total, parts in (("6", ("1", "2", "3", "4", "5")), ("12", ("7", "8", "9", "10", "11"))):
		for col in ("amount", "adjustment", "vat"):
			b[total][col] = sum((b[p][col] for p in parts), ZERO)
	b["13"]["vat"] = b["6"]["vat"] - b["12"]["vat"]
	b["16"]["vat"] = b["13"]["vat"] + b["14"]["vat"] - b["15"]["vat"]
	return b


def _vat_full(F):
	acc = _vat_accounts(F.company)
	out_gl, in_gl, settlement, tb = _gl_scan(F, acc)

	sales = _doc_rows(F, out_gl, "Sales Invoice", "customer", True) + _other_rows(out_gl, {"Sales Invoice"}, True)
	purchases = _doc_rows(F, in_gl, "Purchase Invoice", "supplier", False) + _other_rows(in_gl, {"Purchase Invoice"}, False)
	for rows in (sales, purchases):
		rows.sort(key=lambda r: (r["date"], r["name"]))

	out_total = sum((v for v, _ in out_gl.values()), ZERO)
	in_total = sum((v for v, _ in in_gl.values()), ZERO)
	boxes = _boxes(sales, purchases)

	# monthly breakdown (one row per month of the period) with the settlement journal of that month
	monthly = {}
	for key, rows in (("output", sales), ("input", purchases)):
		for r in rows:
			m = r["date"][:7]
			monthly.setdefault(m, {"month": m, "output": ZERO, "input": ZERO, "settle_output": ZERO, "settle_input": ZERO, "vouchers": []})
			monthly[m][key] += r["vat"]
	for j in settlement:
		m = str(j["date"])[:7]
		monthly.setdefault(m, {"month": m, "output": ZERO, "input": ZERO, "settle_output": ZERO, "settle_input": ZERO, "vouchers": []})
		monthly[m]["settle_output"] += j["output"]
		monthly[m]["settle_input"] += j["input"]
		monthly[m]["vouchers"].append(j["voucher"])

	# halala-exact rounding of the register rows against the GL totals
	_round_rows(sales, "vat", out_total)
	_round_rows(purchases, "vat", in_total)
	for rows in (sales, purchases):
		for r in rows:
			r["std"] = r["std"].quantize(CENT, rounding=ROUND_HALF_UP)
			r["zero"] = r["zero"].quantize(CENT, rounding=ROUND_HALF_UP)
			r["total"] = r["std"] + r["zero"] + r["vat"]

	missing_supplier_vat = [r for r in purchases if r["doctype"] == "Purchase Invoice" and r["vat"] and not r["vat_no"]]
	mixed = [r for r in purchases + sales if r["category"] == "mixed"]
	estimated = [r for r in purchases if r["estimated"]]
	misposted = [r for r in sales + purchases if r["category"] == "adjustment"]
	checks = [
		{
			"key": "missing_supplier_vat",
			"level": "high" if missing_supplier_vat else "ok",
			"title": "فواتير مشتريات عليها ضريبة والمورد بدون رقم ضريبي",
			"desc": "لا تُقبل ضريبة المدخلات عند الفحص بدون الرقم الضريبي للمورد. أضف الرقم في بطاقة المورد (Tax ID).",
			"count": len(missing_supplier_vat),
			"vat": sum((r["vat"] for r in missing_supplier_vat), ZERO),
		},
		{
			"key": "estimated",
			"level": "warn" if estimated else "ok",
			"title": "ضريبة مدخلات مسجلة بقيود يومية أو سندات صرف",
			"desc": "الضريبة نفسها مطابقة للقيد، أما المبلغ الخاضع فمحسوب من الضريبة ÷ 15% لأن القيد لا يحمل قيمة الفاتورة.",
			"count": len(estimated),
			"vat": sum((r["vat"] for r in estimated), ZERO),
		},
		{
			"key": "mixed",
			"level": "info" if mixed else "ok",
			"title": "فواتير جزء منها خاضع وجزء صفري",
			"desc": "قُسّمت تلقائياً: الخاضع = الضريبة ÷ 15% والباقي في البند الصفري.",
			"count": len(mixed),
			"vat": sum((r["vat"] for r in mixed), ZERO),
		},
		{
			"key": "misposted",
			"level": "warn" if misposted else "ok",
			"title": "مستندات مرحّلة على حساب الضريبة الآخر أو قيود تسوية مباشرة",
			"desc": "مثل فاتورة مشتريات رُحّلت ضريبتها على حساب المخرجات. أُدرجت حتى يطابق التقرير الميزان، وتحتاج مراجعة.",
			"count": len(misposted),
			"vat": sum((r["vat"] for r in misposted), ZERO),
		},
	]

	return {
		"filters": {
			"company": F.company,
			"year": F.year,
			"period_type": F.period_type,
			"num": F.num,
			"label": F.label,
			"from": str(F["from"]),
			"to": str(F.to),
			"company_vat": frappe.db.get_value("Company", F.company, "tax_id") or "",
		},
		"accounts": acc,
		"boxes": boxes,
		"totals": {"output": out_total, "input": in_total, "net": out_total - in_total},
		"trial_balance": tb,
		"settlement": settlement,
		"monthly": sorted(monthly.values(), key=lambda m: m["month"]),
		"checks": checks,
		"counts": {
			"sales": len(sales),
			"purchases": len(purchases),
			"sales_vat": sum(1 for r in sales if r["vat"]),
			"purchases_vat": sum(1 for r in purchases if r["vat"]),
		},
		"sales": sales,
		"purchases": purchases,
	}


def _jsonable(v):
	if isinstance(v, Decimal):
		return _q(v)
	if isinstance(v, dict):
		return {k: _jsonable(x) for k, x in v.items()}
	if isinstance(v, (list, tuple)):
		return [_jsonable(x) for x in v]
	if isinstance(v, date):
		return str(v)
	return v


def _compute(F):
	return _jsonable(_vat_full(F))


def _get(company, year, period_type, num, refresh):
	_core()._guard("vat")
	F = _resolve(company, year, period_type, num)
	return _core()._cached("vat", F, _compute, refresh)


def _years(company, refresh=False):
	"""Years that have ledger entries. The scan covers the whole ledger, so it is memoised
	for 6 hours (and refreshed by the warm job) instead of running on every request."""
	r = _core()._redis()
	key = f"executive_cockpit:vat_years:{company}"
	ys = None if refresh else r.get_value(key, expires=True)
	if ys is None:
		ys = [
			cint(y[0])
			for y in frappe.db.sql(
				"select distinct year(posting_date) from `tabGL Entry` where company=%s and is_cancelled=0 order by 1 desc",
				company,
			)
			if y[0]
		]
		r.set_value(key, ys, expires_in_sec=6 * 3600)
	return ys


@frappe.whitelist()
def get_vat(company, year=None, period_type="month", num=None, refresh=0):
	d = dict(_get(company, year, period_type, num, refresh))
	box_list = [{"no": k, "label": BOX_LABELS[k], **v} for k, v in d.pop("boxes").items()]
	sales, purchases = d.pop("sales"), d.pop("purchases")
	d["boxes"] = box_list
	d["years"] = _years(company)
	d["register_totals"] = {
		"sales": _sum_rows(sales),
		"purchases": _sum_rows(purchases),
	}
	return d


@frappe.whitelist()
def get_vat_register(company, year=None, period_type="month", num=None, kind="sales", refresh=0):
	d = _get(company, year, period_type, num, refresh)
	rows = d["purchases"] if kind == "purchases" else d["sales"]
	return {"kind": kind, "label": d["filters"]["label"], "rows": rows, "totals": _sum_rows(rows), "categories": CATEGORY_LABELS}


def _sum_rows(rows):
	t = {k: Decimal("0") for k in ("std", "zero", "vat", "total")}
	for r in rows:
		for k in t:
			t[k] += _d(r[k])
	return {k: _q(v) for k, v in t.items()} | {"count": len(rows)}


# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------


@frappe.whitelist()
def export_vat_excel(company, year=None, period_type="month", num=None, kind="all"):
	from io import BytesIO

	from openpyxl import Workbook
	from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
	from openpyxl.utils import get_column_letter

	d = _get(company, year, period_type, num, 0)
	Fd = d["filters"]
	thin = Side(style="thin", color="999999")
	border = Border(left=thin, right=thin, top=thin, bottom=thin)
	bold = Font(name="Calibri", size=11, bold=True)
	font = Font(name="Calibri", size=11)
	head_fill = PatternFill("solid", fgColor="DDEBF7")
	total_fill = PatternFill("solid", fgColor="F2F2F2")
	center = Alignment(horizontal="center", vertical="center", wrap_text=True)
	right = Alignment(horizontal="right", vertical="center", wrap_text=True)
	money = "#,##0.00"

	wb = Workbook()
	wb.remove(wb.active)

	def header_block(ws, title, ncols):
		ws.sheet_view.rightToLeft = True
		ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
		c = ws.cell(row=1, column=1, value=title)
		c.font, c.alignment = Font(name="Calibri", size=14, bold=True), center
		info = f"{Fd['company']} — الرقم الضريبي: {Fd['company_vat'] or '—'} — الفترة: {Fd['label']} ({Fd['from']} إلى {Fd['to']})"
		ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
		c = ws.cell(row=2, column=1, value=info)
		c.font, c.alignment = font, center
		ws.row_dimensions[1].height = 24
		return 4

	def table(ws, start, headers, rows, widths, money_cols, total_label=None):
		for col, h in enumerate(headers, start=1):
			c = ws.cell(row=start, column=col, value=h)
			c.font, c.alignment, c.border, c.fill = bold, center, border, head_fill
		ws.row_dimensions[start].height = 32
		for i, row in enumerate(rows, start=start + 1):
			for col, v in enumerate(row, start=1):
				c = ws.cell(row=i, column=col, value=v)
				c.font, c.border = font, border
				c.alignment = right if col not in money_cols else Alignment(horizontal="left", vertical="center")
				if col in money_cols:
					c.number_format = money
		last = start + len(rows)
		if total_label is not None:
			t = last + 1
			ws.cell(row=t, column=1, value=total_label)
			for col in range(1, len(headers) + 1):
				c = ws.cell(row=t, column=col)
				c.font, c.border, c.fill = bold, border, total_fill
				if col in money_cols:
					letter = get_column_letter(col)
					c.value = f"=SUM({letter}{start + 1}:{letter}{last})" if rows else 0
					c.number_format = money
		for col, w in enumerate(widths, start=1):
			ws.column_dimensions[get_column_letter(col)].width = w
		ws.freeze_panes = ws.cell(row=start + 1, column=1)
		ws.page_setup.orientation = "landscape"
		ws.page_setup.fitToWidth = 1
		ws.page_setup.fitToHeight = 0
		ws.sheet_properties.pageSetUpPr.fitToPage = True
		ws.print_title_rows = f"{start}:{start}"

	def return_sheet():
		ws = wb.create_sheet("الإقرار")
		start = header_block(ws, "إقرار ضريبة القيمة المضافة", 5)
		rows = []
		for b in get_vat(company, year, period_type, num)["boxes"]:
			n = int(b["no"])
			if n <= 12:
				rows.append([b["no"], b["label"], b["amount"], b["adjustment"], b["vat"]])
			else:
				rows.append([b["no"], b["label"], None, None, b["vat"]])
		table(ws, start, ["البند", "الوصف", "المبلغ (ريال)", "مبلغ التعديل (ريال)", "مبلغ ضريبة القيمة المضافة (ريال)"], rows, [7, 62, 18, 18, 20], {3, 4, 5})
		for r in range(start + 1, start + len(rows) + 1):
			if ws.cell(row=r, column=1).value in ("6", "12", "13", "16"):
				for col in range(1, 6):
					ws.cell(row=r, column=col).font = bold
					ws.cell(row=r, column=col).fill = total_fill

	def register_sheet(kind):
		rows = d["sales"] if kind == "sales" else d["purchases"]
		cat = CATEGORY_LABELS
		if kind == "sales":
			ws = wb.create_sheet("سجل المبيعات")
			headers = ["م", "رقم الفاتورة", "التاريخ", "نوع المستند", "اسم العميل", "الرقم الضريبي للعميل", "الفاتورة الأصلية",
				"التصنيف", "المبلغ الخاضع للنسبة الأساسية", "المبلغ الصفري / غير الخاضع", "ضريبة القيمة المضافة", "الإجمالي شامل الضريبة"]
			data = [[i, r["name"], r["date"], r["kind"], r["party"], r["vat_no"], r["ref"], cat.get(r["category"], ""),
				r["std"], r["zero"], r["vat"], r["total"]] for i, r in enumerate(rows, start=1)]
			widths = [6, 20, 12, 18, 40, 18, 18, 16, 18, 18, 16, 18]
			mcols = {9, 10, 11, 12}
			title = "سجل المبيعات (ضريبة المخرجات)"
		else:
			ws = wb.create_sheet("سجل المشتريات")
			headers = ["م", "الرقم الداخلي", "تاريخ القيد", "رقم فاتورة المورد", "تاريخ فاتورة المورد", "نوع المستند", "اسم المورد / البيان",
				"الرقم الضريبي للمورد", "التصنيف", "المبلغ الخاضع للنسبة الأساسية", "المبلغ الصفري / غير الخاضع", "ضريبة القيمة المضافة",
				"الإجمالي شامل الضريبة", "ملاحظة"]
			data = [[i, r["name"], r["date"], r["bill_no"], r["bill_date"], r["kind"], r["party"], r["vat_no"], cat.get(r["category"], ""),
				r["std"], r["zero"], r["vat"], r["total"], "المبلغ الخاضع محسوب من الضريبة" if r["estimated"] else ""]
				for i, r in enumerate(rows, start=1)]
			widths = [6, 22, 12, 18, 14, 18, 40, 18, 16, 18, 18, 16, 18, 26]
			mcols = {10, 11, 12, 13}
			title = "سجل المشتريات (ضريبة المدخلات)"
		start = header_block(ws, title, len(headers))
		table(ws, start, headers, data, widths, mcols, "الإجمالي")

	def reconcile_sheet():
		ws = wb.create_sheet("المطابقة مع الميزان")
		start = header_block(ws, "مطابقة التقرير مع ميزان المراجعة", 9)
		names = {"output": "ضريبة المخرجات", "input": "ضريبة المدخلات", "settlement": "حساب تسوية الضريبة"}
		report = {"output": d["totals"]["output"], "input": d["totals"]["input"]}
		rows = []
		for t in d["trial_balance"]:
			rep = report.get(t["key"])
			rows.append([names[t["key"]], t["account"], t["opening"], t["debit"], t["credit"], t["closing"], t["settlement"] if rep is not None else None,
				t["movement"] if rep is not None else None, rep])
		table(ws, start, ["البيان", "الحساب", "رصيد أول المدة (مدين)", "مدين الفترة", "دائن الفترة", "رصيد آخر المدة (مدين)",
			"قيد التسوية الشهري", "حركة الحساب قبل قيد التسوية", "ضريبة التقرير"], rows, [18, 46, 18, 16, 16, 18, 18, 20, 16], {3, 4, 5, 6, 7, 8, 9})
		r = start + len(rows) + 2
		ws.cell(row=r, column=1, value="قيود التسوية في الفترة").font = bold
		srows = [[j["voucher"], j["date"], j["output"], j["input"], round(j["output"] - j["input"], 2)] for j in d["settlement"]]
		table(ws, r + 1, ["القيد", "التاريخ", "ضريبة المخرجات المقفلة", "ضريبة المدخلات المقفلة", "الصافي"], srows, [18, 46, 18, 16, 16, 18, 18, 20, 16], {3, 4, 5})
		ws.freeze_panes = None

	if kind in ("all", "return"):
		return_sheet()
	if kind in ("all", "sales"):
		register_sheet("sales")
	if kind in ("all", "purchases"):
		register_sheet("purchases")
	if kind == "all":
		reconcile_sheet()

	out = BytesIO()
	wb.save(out)
	prefix = {"sales": "سجل المبيعات", "purchases": "سجل المشتريات", "return": "الإقرار الضريبي"}.get(kind, "الإقرار الضريبي والسجلات")
	return _core().xlsx_response(out.getvalue(), f"{prefix} - {Fd['label']}.xlsx")
