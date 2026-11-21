"""Executive Cockpit API.

Read-only aggregate endpoints for the executive dashboard. Every endpoint is
gated by the "Executive Dashboard" role (or System Manager) because the
queries aggregate across documents and bypass per-document permissions.
"""

import hashlib
import json
from datetime import date, timedelta

import frappe
from frappe.utils import add_months, add_days, flt, cint, getdate, today, get_first_day, get_last_day

ROLES = ("Executive Dashboard", "System Manager")
CACHE_PREFIX = "executive_cockpit:"
CACHE_INDEX_KEY = "executive_cockpit:keys"


# ---------------------------------------------------------------------------
# Access, settings, cache
# ---------------------------------------------------------------------------


SECTIONS = ("overview", "sales", "reps", "collection", "profit", "vat", "hr")


def allowed_sections(user=None):
	"""Sections of the dashboard the user may open.

	When the settings list specific users, only they get in (Administrator always),
	each with the sections ticked for them. With an empty list the dashboard falls
	back to the role rule: Executive Dashboard or System Manager see everything."""
	user = user or frappe.session.user
	if user == "Guest":
		return []
	if user == "Administrator":
		return list(SECTIONS)
	rows = frappe.get_cached_doc("Executive Cockpit Settings").get("allowed_users") or []
	if rows:
		for r in rows:
			if r.user == user:
				return [s for s in SECTIONS if r.get(s)]
		return []
	return list(SECTIONS) if set(ROLES) & set(frappe.get_roles(user)) else []


def has_app_permission():
	return bool(allowed_sections())


def _guard(section=None):
	sections = allowed_sections()
	if not sections:
		frappe.throw("ليس لديك صلاحية الوصول إلى لوحة القيادة التنفيذية", frappe.PermissionError)
	if section and section not in sections:
		frappe.throw("ليس لديك صلاحية الاطلاع على هذا القسم من لوحة القيادة", frappe.PermissionError)


def _settings():
	s = frappe.get_cached_doc("Executive Cockpit Settings")
	return frappe._dict(
		default_company=s.default_company,
		custody_parent_account=s.custody_parent_account,
		dso_target=cint(s.dso_target) or 60,
		cache_minutes=cint(s.cache_minutes) if s.cache_minutes is not None else 15,
	)


def _redis():
	return frappe.cache() if callable(frappe.cache) else frappe.cache


def _cached(name, F, compute, refresh=False):
	ttl = _settings().cache_minutes * 60
	raw = json.dumps([name, {k: str(v) for k, v in F.items() if k != "months"}], sort_keys=True)
	key = CACHE_PREFIX + hashlib.md5(raw.encode()).hexdigest()
	r = _redis()
	if ttl and not cint(refresh):
		hit = r.get_value(key)
		if hit is not None:
			return hit
	data = compute(F)
	data["generated_at"] = frappe.utils.now()
	if ttl:
		r.set_value(key, data, expires_in_sec=ttl)
		keys = set(r.get_value(CACHE_INDEX_KEY) or [])
		keys.add(key)
		r.set_value(CACHE_INDEX_KEY, list(keys))
	return data


def clear_cache():
	r = _redis()
	for key in r.get_value(CACHE_INDEX_KEY) or []:
		r.delete_value(key)
	r.delete_value(CACHE_INDEX_KEY)


# ---------------------------------------------------------------------------
# Period handling
# ---------------------------------------------------------------------------


def _fiscal_year_start(d, company):
	try:
		from erpnext.accounts.utils import get_fiscal_year

		return getdate(get_fiscal_year(d, company=company)[1])
	except Exception:
		return date(d.year, 1, 1)


def _resolve(company, period="ytd", as_of=None, from_date=None, to_date=None):
	if not company or not frappe.db.exists("Company", company):
		frappe.throw("الشركة غير موجودة")
	as_of = getdate(as_of or today())
	period = period or "ytd"
	if period == "custom" and from_date and to_date:
		f, t = getdate(from_date), getdate(to_date)
	elif period == "month":
		f, t = get_first_day(as_of), as_of
	elif period == "quarter":
		qm = ((as_of.month - 1) // 3) * 3 + 1
		f, t = date(as_of.year, qm, 1), as_of
	else:
		period = "ytd"
		f, t = _fiscal_year_start(as_of, company), as_of
	if f > t:
		f, t = t, f

	shift = {"ytd": 12, "quarter": 3, "month": 1}.get(period)
	if shift:
		pf, pt = getdate(add_months(f, -shift)), getdate(add_months(t, -shift))
	else:
		span = (t - f).days
		pt = add_days(f, -1)
		pf = add_days(pt, -span)

	month_end = get_first_day(t)
	months = [getdate(add_months(month_end, -i)) for i in range(11, -1, -1)]
	return frappe._dict(
		company=company,
		period=period,
		as_of=as_of,
		**{"from": f, "to": t},
		prev_from=getdate(pf),
		prev_to=getdate(pt),
		trend_from=months[0],
		months=months,
	)


def _p(F, **extra):
	"""SQL params from filters."""
	d = {
		"company": F.company,
		"from": F["from"],
		"to": F.to,
		"prev_from": F.prev_from,
		"prev_to": F.prev_to,
		"trend_from": F.trend_from,
	}
	d.update(extra)
	return d


def _months_payload(F):
	return [m.strftime("%Y-%m") for m in F.months]


def _series(rows, F):
	"""rows: iterable of (YYYY-MM, value) -> list aligned to F.months."""
	m = {r[0]: flt(r[1], 2) for r in rows}
	return [m.get(k, 0.0) for k in _months_payload(F)]


def _scalar(sql, params):
	r = frappe.db.sql(sql, params)
	return flt(r[0][0], 2) if r and r[0][0] is not None else 0.0


def _delta(cur, prev):
	# No meaningful comparison when the previous period is empty or negligible.
	if not prev or abs(prev) < abs(cur) * 0.02:
		return None
	return flt((cur - prev) / abs(prev) * 100, 1)


# ---------------------------------------------------------------------------
# Shared metric queries
# ---------------------------------------------------------------------------


def _sales(F, f="from", t="to", field="base_net_total"):
	return _scalar(
		f"""select sum({field}) from `tabSales Invoice`
		where docstatus=1 and company=%(company)s and posting_date between %({f})s and %({t})s""",
		_p(F),
	)


def _collected(F, f="from", t="to"):
	return _scalar(
		f"""select sum(base_received_amount) from `tabPayment Entry`
		where docstatus=1 and payment_type='Receive' and party_type='Customer'
		and company=%(company)s and posting_date between %({f})s and %({t})s""",
		_p(F),
	)


def _memo():
	"""Per-request memo (frappe.local is reset between requests)."""
	memo = getattr(frappe.local, "executive_cockpit_memo", None)
	if memo is None:
		memo = frappe.local.executive_cockpit_memo = {}
	return memo


def _pl_accounts(company):
	key = ("pl_accounts", company)
	memo = _memo()
	if key not in memo:
		rows = frappe.db.sql(
			"""select a.name, a.root_type, pa.account_name
			from `tabAccount` a left join `tabAccount` pa on pa.name = a.parent_account
			where a.company=%s and a.is_group=0 and a.root_type in ('Income','Expense')""",
			company,
		)
		memo[key] = {r[0]: (r[1], r[2] or "—") for r in rows}
	return memo[key]


def _pl_rows(F):
	"""Daily P&L balances per account, one query per request: [(account, date, credit-debit)]."""
	start = min(F["from"], F.prev_from, F.trend_from)
	key = ("pl_rows", F.company, str(start), str(F.to))
	memo = _memo()
	if key not in memo:
		accounts = _pl_accounts(F.company)
		memo[key] = (
			frappe.db.sql(
				"""select account, posting_date, sum(credit - debit) from `tabGL Entry`
				where company=%(company)s and is_cancelled=0
				and voucher_type != 'Period Closing Voucher'
				and posting_date between %(start)s and %(to)s and account in %(accounts)s
				group by account, posting_date""",
				_p(F, start=start, accounts=tuple(accounts) or ("",)),
			)
			if accounts
			else []
		)
	return memo[key]


def _pl(F, f="from", t="to"):
	accounts = _pl_accounts(F.company)
	lo, hi = F[f], F[t]
	income = credit_exp = 0.0
	for acc, d, v in _pl_rows(F):
		if lo <= d <= hi:
			if accounts[acc][0] == "Income":
				income += flt(v)
			else:
				credit_exp += flt(v)
	expense = -credit_exp
	return flt(income, 2), flt(expense, 2), flt(income - expense, 2)


def _net_receivable(F):
	return _scalar(
		"""select sum(amount) from `tabPayment Ledger Entry`
		where delinked=0 and account_type='Receivable' and party_type='Customer'
		and company=%(company)s and posting_date <= %(to)s""",
		_p(F),
	)


def _invoice_balances(F):
	"""Per-invoice receivable balance as of F.to (from Payment Ledger)."""
	return frappe.db.sql(
		"""select ple.against_voucher_no as invoice, si.customer, si.customer_name,
			si.due_date, si.posting_date, sum(ple.amount) as amount
		from `tabPayment Ledger Entry` ple
		join `tabSales Invoice` si on si.name = ple.against_voucher_no
		where ple.delinked=0 and ple.account_type='Receivable'
		and ple.against_voucher_type='Sales Invoice'
		and ple.company=%(company)s and ple.posting_date <= %(to)s
		group by ple.against_voucher_no
		having sum(ple.amount) > 0.01""",
		_p(F),
		as_dict=True,
	)


def _unbilled_orders(F):
	r = frappe.db.sql(
		"""select count(*), sum(base_net_total * (100 - per_billed) / 100)
		from `tabSales Order`
		where docstatus=1 and company=%(company)s and per_billed < 99.99
		and status not in ('Closed', 'Completed', 'On Hold')
		and transaction_date <= %(to)s""",
		_p(F),
	)[0]
	return cint(r[0]), flt(r[1], 2)


def _payroll_monthly(F):
	return frappe.db.sql(
		"""select date_format(start_date, '%%Y-%%m') m, sum(base_net_pay), sum(base_gross_pay), count(*)
		from `tabSalary Slip`
		where docstatus=1 and company=%(company)s and start_date between %(trend_from)s and %(to)s
		group by m""",
		_p(F),
	)


def _latest_payroll(F):
	# Latest month with a real payroll run (at least half the usual slip count),
	# so a month holding a few stray slips is not reported as the payroll.
	runs = frappe.db.sql(
		"""select date_format(start_date, '%%Y-%%m-01') m, count(*) n from `tabSalary Slip`
		where docstatus=1 and company=%(company)s and start_date <= %(to)s
		and start_date >= %(since)s group by m order by m""",
		_p(F, since=add_months(F.to, -24)),
	)
	if not runs:
		return None
	usual = max(cint(r[1]) for r in runs)
	full = [r[0] for r in runs if cint(r[1]) >= usual * 0.5]
	latest = get_first_day(getdate(full[-1] if full else runs[-1][0]))
	row = frappe.db.sql(
		"""select sum(base_net_pay), sum(base_gross_pay), count(*) from `tabSalary Slip`
		where docstatus=1 and company=%(company)s
		and start_date between %(m_from)s and %(m_to)s""",
		_p(F, m_from=latest, m_to=get_last_day(latest)),
	)[0]
	prev = get_first_day(add_months(latest, -1))
	prev_net = _scalar(
		"""select sum(base_net_pay) from `tabSalary Slip`
		where docstatus=1 and company=%(company)s and start_date between %(m_from)s and %(m_to)s""",
		_p(F, m_from=prev, m_to=get_last_day(prev)),
	)
	months_behind = (F.to.year - latest.year) * 12 + (F.to.month - latest.month)
	return frappe._dict(
		month=latest.strftime("%Y-%m"),
		net=flt(row[0], 2),
		gross=flt(row[1], 2),
		count=cint(row[2]),
		prev_net=prev_net,
		months_behind=months_behind,
	)


def _monthly_sql(sql, F):
	return _series(frappe.db.sql(sql, _p(F)), F)


def _sales_monthly(F, field="base_net_total"):
	return _monthly_sql(
		f"""select date_format(posting_date, '%%Y-%%m') m, sum({field}) from `tabSales Invoice`
		where docstatus=1 and company=%(company)s and posting_date between %(trend_from)s and %(to)s
		group by m""",
		F,
	)


def _collected_monthly(F):
	return _monthly_sql(
		"""select date_format(posting_date, '%%Y-%%m') m, sum(base_received_amount) from `tabPayment Entry`
		where docstatus=1 and payment_type='Receive' and party_type='Customer'
		and company=%(company)s and posting_date between %(trend_from)s and %(to)s
		group by m""",
		F,
	)


def _pl_monthly(F):
	accounts = _pl_accounts(F.company)
	inc_m, exp_m = {}, {}
	for acc, d, v in _pl_rows(F):
		if d < F.trend_from:
			continue
		k = d.strftime("%Y-%m")
		if accounts[acc][0] == "Income":
			inc_m[k] = inc_m.get(k, 0) + flt(v)
		else:
			exp_m[k] = exp_m.get(k, 0) - flt(v)
	inc = _series(inc_m.items(), F)
	exp = _series(exp_m.items(), F)
	net = [flt(i - e, 2) for i, e in zip(inc, exp)]
	return inc, exp, net


def _last_invoice_date(company):
	r = frappe.db.sql(
		"select max(posting_date) from `tabSales Invoice` where docstatus=1 and company=%s", company
	)
	return str(r[0][0]) if r and r[0][0] else None


def _unpaid_expense_claims(F):
	r = frappe.db.sql(
		"""select count(*), sum(grand_total - ifnull(total_amount_reimbursed, 0))
		from `tabExpense Claim` where docstatus=1 and status='Unpaid' and company=%(company)s""",
		_p(F),
	)[0]
	return cint(r[0]), flt(r[1], 2)


def _aging(balances, as_of):
	buckets = [
		{"key": "not_due", "label": "لم تستحق بعد", "amount": 0.0, "count": 0},
		{"key": "0_30", "label": "1 – 30 يوماً", "amount": 0.0, "count": 0},
		{"key": "31_60", "label": "31 – 60 يوماً", "amount": 0.0, "count": 0},
		{"key": "61_90", "label": "61 – 90 يوماً", "amount": 0.0, "count": 0},
		{"key": "90_plus", "label": "أكثر من 90 يوماً", "amount": 0.0, "count": 0},
	]
	for b in balances:
		days = (as_of - getdate(b.due_date or b.posting_date)).days
		i = 0 if days <= 0 else 1 if days <= 30 else 2 if days <= 60 else 3 if days <= 90 else 4
		buckets[i]["amount"] += flt(b.amount)
		buckets[i]["count"] += 1
	total = sum(x["amount"] for x in buckets) or 1
	for x in buckets:
		x["amount"] = flt(x["amount"], 2)
		x["pct"] = flt(x["amount"] / total * 100, 1)
	return buckets


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_boot():
	_guard()
	s = _settings()
	companies = frappe.get_all("Company", fields=["name", "abbr", "default_currency"], order_by="name")
	default = s.default_company
	if not default:
		r = frappe.db.sql(
			"""select company from `tabGL Entry` where is_cancelled=0
			group by company order by count(*) desc limit 1"""
		)
		default = r[0][0] if r else (companies[0].name if companies else None)
	return {
		"user": frappe.session.user,
		"sections": allowed_sections(),
		"full_name": frappe.utils.get_fullname(frappe.session.user),
		"companies": companies,
		"default_company": default,
		"today": today(),
		"dso_target": s.dso_target,
		"last_invoice_date": {c.name: _last_invoice_date(c.name) for c in companies},
	}


@frappe.whitelist()
def refresh_cache():
	_guard()
	clear_cache()
	return {"ok": True}


@frappe.whitelist()
def get_overview(company, period="ytd", as_of=None, from_date=None, to_date=None, refresh=0):
	_guard("overview")
	F = _resolve(company, period, as_of, from_date, to_date)
	data = _cached("overview", F, _overview, refresh)
	# the cached overview is shared by everyone: drop what this user may not see
	sections = allowed_sections()
	data = dict(data, kpis=dict(data["kpis"]))
	if "hr" not in sections:
		data["kpis"].pop("payroll", None)
	data["alerts"] = [a for a in data["alerts"] if a["route"].rsplit("/", 1)[-1] in sections]
	return data


def _overview(F):
	sales, sales_prev = _sales(F), _sales(F, "prev_from", "prev_to")
	gross = _sales(F, field="base_grand_total")
	coll, coll_prev = _collected(F), _collected(F, "prev_from", "prev_to")
	inc, exp, net = _pl(F)
	_, _, net_prev = _pl(F, "prev_from", "prev_to")
	net_ar = _net_receivable(F)
	balances = _invoice_balances(F)
	aging = _aging(balances, F.to)
	inv_open = flt(sum(flt(b.amount) for b in balances), 2)
	unbilled_n, unbilled_v = _unbilled_orders(F)
	payroll = _latest_payroll(F)
	ec_n, ec_v = _unpaid_expense_claims(F)
	inc_m, exp_m, net_m = _pl_monthly(F)
	sales_m = _sales_monthly(F)
	coll_m = _collected_monthly(F)

	alerts = []
	over90 = aging[4]
	if over90["amount"] > 0:
		alerts.append({
			"level": "high", "title": "فواتير متأخرة أكثر من 90 يوماً",
			"desc": f"{over90['count']:,} فاتورة · {over90['amount']:,.0f} ر.س", "route": "/executive/collection",
		})
	unallocated = flt(inv_open - net_ar, 2)
	if unallocated > 1000:
		alerts.append({
			"level": "medium", "title": "دفعات ومرتجعات غير مخصّصة لفواتير",
			"desc": f"{unallocated:,.0f} ر.س تُظهر الفواتير مفتوحة رغم تحصيلها جزئياً", "route": "/executive/collection",
		})
	if unbilled_n:
		alerts.append({
			"level": "medium", "title": f"{unbilled_n:,} أمر بيع لم يُفوتر بالكامل",
			"desc": f"المتبقي للفوترة {unbilled_v:,.0f} ر.س", "route": "/executive/sales",
		})
	if ec_n:
		alerts.append({
			"level": "medium", "title": f"{ec_n:,} مطالبة مصروفات غير مدفوعة",
			"desc": f"بقيمة {ec_v:,.0f} ر.س", "route": "/executive/hr",
		})
	if payroll and payroll.months_behind >= 2:
		alerts.append({
			"level": "high", "title": "مسير الرواتب غير محدّث",
			"desc": f"آخر شهر مسجّل: {payroll.month}", "route": "/executive/hr",
		})
	if net < 0:
		alerts.append({"level": "high", "title": "صافي خسارة في الفترة", "desc": f"{net:,.0f} ر.س", "route": "/executive/profit"})

	return {
		"filters": _filters_payload(F),
		"months": _months_payload(F),
		"kpis": {
			"sales": {"value": sales, "prev": sales_prev, "delta": _delta(sales, sales_prev), "trend": sales_m},
			"net_profit": {
				"value": net, "prev": net_prev, "delta": _delta(net, net_prev),
				"margin": flt(net / inc * 100, 1) if inc else None, "trend": net_m,
			},
			"collected": {
				"value": coll, "prev": coll_prev, "delta": _delta(coll, coll_prev),
				"rate": flt(coll / gross * 100, 1) if gross else None, "trend": coll_m,
			},
			"receivable": {
				"value": net_ar, "invoice_open": inv_open, "unallocated": unallocated,
				"over90_pct": over90["pct"],
			},
			"unbilled_orders": {"value": unbilled_v, "count": unbilled_n},
			"payroll": payroll and {
				"value": payroll.net, "month": payroll.month, "count": payroll.count,
				"delta": _delta(payroll.net, payroll.prev_net),
				"trend": _series([(r[0], r[1]) for r in _payroll_monthly(F)], F),
			},
		},
		"chart": {"sales": sales_m, "collected": coll_m, "income": inc_m, "expense": exp_m},
		"alerts": alerts,
	}


@frappe.whitelist()
def get_sales(company, period="ytd", as_of=None, from_date=None, to_date=None, refresh=0):
	_guard("sales")
	F = _resolve(company, period, as_of, from_date, to_date)
	return _cached("sales", F, _sales_view, refresh)


def _sales_view(F):
	p = _p(F)
	q = frappe.db.sql(
		"""select status, count(*), sum(base_net_total) from `tabQuotation`
		where docstatus=1 and company=%(company)s and transaction_date between %(from)s and %(to)s
		group by status""",
		p,
	)
	q_status = {r[0]: {"count": cint(r[1]), "value": flt(r[2], 2)} for r in q}
	q_count = sum(v["count"] for v in q_status.values())
	q_value = sum(v["value"] for v in q_status.values())
	converted = sum(q_status.get(s, {}).get("count", 0) for s in ("Ordered", "Partially Ordered"))
	decided = q_count - q_status.get("Open", {}).get("count", 0) - q_status.get("Replied", {}).get("count", 0)

	so = frappe.db.sql(
		"""select
			case when per_billed >= 99.99 then 'full' when per_billed > 0 then 'partial' else 'none' end b,
			count(*), sum(base_net_total), sum(base_net_total * (100 - per_billed) / 100)
		from `tabSales Order`
		where docstatus=1 and company=%(company)s and status != 'Closed'
		and transaction_date between %(from)s and %(to)s
		group by b""",
		p,
	)
	so_b = {r[0]: {"count": cint(r[1]), "value": flt(r[2], 2), "unbilled": flt(r[3], 2)} for r in so}
	so_count = sum(v["count"] for v in so_b.values())
	so_value = sum(v["value"] for v in so_b.values())

	si = frappe.db.sql(
		"""select count(*), sum(base_net_total) from `tabSales Invoice`
		where docstatus=1 and is_return=0 and company=%(company)s and posting_date between %(from)s and %(to)s""",
		p,
	)[0]
	pe = frappe.db.sql(
		"""select count(*), sum(base_received_amount) from `tabPayment Entry`
		where docstatus=1 and payment_type='Receive' and party_type='Customer'
		and company=%(company)s and posting_date between %(from)s and %(to)s""",
		p,
	)[0]

	q_trend = _monthly_sql(
		"""select date_format(transaction_date, '%%Y-%%m') m, sum(base_net_total) from `tabQuotation`
		where docstatus=1 and company=%(company)s and transaction_date between %(trend_from)s and %(to)s
		group by m""",
		F,
	)
	so_trend = _monthly_sql(
		"""select date_format(transaction_date, '%%Y-%%m') m, sum(base_net_total) from `tabSales Order`
		where docstatus=1 and company=%(company)s and transaction_date between %(trend_from)s and %(to)s
		group by m""",
		F,
	)
	bill_pct = _monthly_sql(
		"""select date_format(transaction_date, '%%Y-%%m') m,
			sum(base_net_total * per_billed / 100) / nullif(sum(base_net_total), 0) * 100
		from `tabSales Order`
		where docstatus=1 and company=%(company)s and status != 'Closed'
		and transaction_date between %(trend_from)s and %(to)s
		group by m""",
		F,
	)

	reps = _rep_attribution(F)
	customers = frappe.db.sql(
		"""select customer, customer_name, sum(base_net_total) v, count(*) n from `tabSales Invoice`
		where docstatus=1 and company=%(company)s and posting_date between %(from)s and %(to)s
		group by customer order by v desc limit 8""",
		p,
		as_dict=True,
	)

	return {
		"filters": _filters_payload(F),
		"months": _months_payload(F),
		"stages": [
			{"key": "quotation", "label": "عروض الأسعار", "count": q_count, "value": flt(q_value, 2), "route": "/app/quotation"},
			{"key": "order", "label": "أوامر البيع", "count": so_count, "value": flt(so_value, 2), "route": "/app/sales-order"},
			{"key": "invoice", "label": "فواتير المبيعات", "count": cint(si[0]), "value": flt(si[1], 2), "route": "/app/sales-invoice"},
			{"key": "payment", "label": "التحصيل", "count": cint(pe[0]), "value": flt(pe[1], 2), "route": "/app/payment-entry"},
		],
		"quotations": {
			"status": q_status,
			"count": q_count,
			"conversion": flt(converted / decided * 100, 1) if decided else None,
			"trend": q_trend,
		},
		"orders": {"billing": so_b, "trend": so_trend, "billed_pct_trend": bill_pct},
		"sales_persons": reps,
		"top_customers": customers,
	}


REP_SOURCES = {
	"doc_field": "حقل المندوب في المستند",
	"doc_team": "فريق المبيعات في المستند",
	"order_field": "حقل المندوب في أمر البيع",
	"quotation": "مالك عرض السعر",
	"order_team": "فريق المبيعات في أمر البيع",
	"creator": "منشئ أمر البيع",
	"customer": "مندوب العميل (تقديري)",
	"none": "غير محدد",
}
UNASSIGNED = "غير محدد"
OWNER_FIELD = "custom_qout_ownar"  # free text on Sales Invoice, Link to Sales Person on Sales Order
REP_DOCTYPES = {"Sales Invoice": "posting_date", "Sales Order": "transaction_date"}
AMOUNT_FIELDS = {"net": "base_net_total", "grand": "base_grand_total"}
MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]


def _has_col(doctype, field):
	memo = _memo()
	key = ("has_col", doctype, field)
	if key not in memo:
		memo[key] = frappe.db.has_column(doctype, field)
	return memo[key]


def _valid_reps():
	memo = _memo()
	if "valid_reps" not in memo:
		memo["valid_reps"] = set(frappe.get_all("Sales Person", pluck="name"))
	return memo["valid_reps"]


def _team_shares(parenttype, parents):
	"""{parent: [(sales_person, share 0..1), ...]} from Sales Team rows."""
	out = {}
	parents = [p for p in set(parents) if p]
	if not parents:
		return out
	rows = frappe.db.sql(
		"""select parent, sales_person, allocated_percentage from `tabSales Team`
		where parenttype=%(pt)s and parent in %(parents)s and ifnull(sales_person, '') != ''
		order by parent, idx""",
		{"pt": parenttype, "parents": tuple(parents)},
	)
	for parent, sp, pct in rows:
		out.setdefault(parent, []).append([sp, flt(pct)])
	for parent, team in out.items():
		total = sum(p for _, p in team)
		# Normalise so every document is attributed exactly once (equal split if percentages are blank).
		out[parent] = [(sp, (p / total) if total else 1 / len(team)) for sp, p in team]
	return out


def _top(team):
	return max(team, key=lambda x: x[1])[0] if team else None


def _quotation_owners(quotations):
	quotations = [q for q in set(quotations) if q]
	if not quotations or not _has_col("Quotation", "custom_quotation_owner"):
		return {}
	return dict(
		frappe.db.sql(
			"""select name, custom_quotation_owner from `tabQuotation`
			where name in %(q)s and ifnull(custom_quotation_owner, '') != ''""",
			{"q": tuple(quotations)},
		)
	)


def _order_info(orders):
	"""{sales_order: (owner, first linked quotation, rep field)}"""
	orders = [o for o in set(orders) if o]
	if not orders:
		return {}
	field = f"nullif(trim(so.`{OWNER_FIELD}`), '')" if _has_col("Sales Order", OWNER_FIELD) else "null"
	return {
		r[0]: (r[1], r[2], r[3])
		for r in frappe.db.sql(
			f"""select so.name, so.owner,
				(select soi.prevdoc_docname from `tabSales Order Item` soi
					where soi.parent = so.name and ifnull(soi.prevdoc_docname, '') != '' order by soi.idx limit 1),
				{field}
			from `tabSales Order` so where so.name in %(sos)s""",
			{"sos": tuple(orders)},
		)
	}


def _creator_rep_map(company):
	"""Sales Order creator (user) -> the rep they consistently enter orders for.

	Learned from orders where the rep is known. A user is mapped only when one rep accounts
	for >= 80% of at least 5 such orders, so back-office users who key orders for many reps
	(accountants, delivery) are never mapped.
	"""
	memo = _memo()
	key = ("creator_map", company)
	if key in memo:
		return memo[key]
	names = frappe.get_all("Sales Order", filters={"docstatus": 1, "company": company}, pluck="name")
	info = _order_info(names)
	teams = _team_shares("Sales Order", names)
	qt_owner = _quotation_owners([v[1] for v in info.values()])
	valid = _valid_reps()
	votes = {}
	for name, (owner, qt, field) in info.items():
		rep = (field if field in valid else None) or qt_owner.get(qt) or _top(teams.get(name))
		if rep:
			votes.setdefault(owner, {}).setdefault(rep, 0)
			votes[owner][rep] += 1
	result = {}
	for owner, reps in votes.items():
		total = sum(reps.values())
		rep, n = max(reps.items(), key=lambda x: x[1])
		if total >= 5 and n / total >= 0.8:
			result[owner] = rep
	memo[key] = result
	return result


def _attribute(doctype, company, from_date, to_date, amount="net", include_returns=True):
	"""Attribute every submitted document in the range to sales reps, each exactly once.

	Returns [(month 1..12, amount, [(rep, share)], source)]. Rep source, first match wins:
	the document's own rep field (custom_qout_ownar, only if it is a real Sales Person) ->
	its Sales Team -> (invoices) the linked order's rep field -> quotation owner ->
	order Sales Team -> order creator (learned map) -> customer default team -> unassigned.
	"""
	date_field = REP_DOCTYPES[doctype]
	amount_field = AMOUNT_FIELDS.get(amount, "base_net_total")
	is_inv = doctype == "Sales Invoice"
	field = f"nullif(trim(d.`{OWNER_FIELD}`), '')" if _has_col(doctype, OWNER_FIELD) else "null"
	if is_inv:
		link = """(select sii.sales_order from `tabSales Invoice Item` sii
			where sii.parent = d.name and ifnull(sii.sales_order, '') != '' order by sii.idx limit 1)"""
	else:
		link = "d.name"
	cond = "" if include_returns or not is_inv else "and d.is_return = 0"
	docs = frappe.db.sql(
		f"""select d.name, d.customer, d.`{amount_field}`, month(d.`{date_field}`), {field}, {link}
		from `tab{doctype}` d
		where d.docstatus=1 and d.company=%(company)s and d.`{date_field}` between %(f)s and %(t)s {cond}""",
		{"company": company, "f": from_date, "t": to_date},
	)
	valid = _valid_reps()
	doc_team = _team_shares(doctype, [d[0] for d in docs])
	orders = [d[5] for d in docs]
	info = _order_info(orders)
	order_team = _team_shares("Sales Order", orders) if is_inv else doc_team
	qt_owner = _quotation_owners([v[1] for v in info.values()])
	creator = _creator_rep_map(company)
	cust_team = _team_shares("Customer", [d[1] for d in docs])

	out = []
	for name, customer, value, month, own, so in docs:
		owner, qt, so_field = info.get(so, (None, None, None))
		if own in valid:
			src, team = "doc_field", [(own, 1.0)]
		elif name in doc_team:
			src, team = "doc_team", doc_team[name]
		elif is_inv and so_field in valid:
			src, team = "order_field", [(so_field, 1.0)]
		elif qt_owner.get(qt):
			src, team = "quotation", [(qt_owner[qt], 1.0)]
		elif is_inv and so in order_team:
			src, team = "order_team", order_team[so]
		elif creator.get(owner):
			src, team = "creator", [(creator[owner], 1.0)]
		elif customer in cust_team:
			src, team = "customer", cust_team[customer]
		else:
			src, team = "none", [(UNASSIGNED, 1.0)]
		out.append((cint(month), flt(value), team, src))
	return out


def _sources_summary(docs):
	sources = {k: {"count": 0, "value": 0.0} for k in REP_SOURCES}
	for _, value, _, src in docs:
		sources[src]["count"] += 1
		sources[src]["value"] += value
	return [
		{"key": k, "label": REP_SOURCES[k], "count": v["count"], "value": flt(v["value"], 2)}
		for k, v in sources.items()
		if v["count"]
	]


def _rep_attribution(F, limit=10):
	"""Net sales of the period per rep for the Sales page card."""
	docs = _attribute("Sales Invoice", F.company, F["from"], F.to)
	reps = {}
	for _, value, team, src in docs:
		for sp, share in team:
			r = reps.setdefault(sp, {"sales_person": sp, "v": 0.0, "n": 0, "estimated": 0.0})
			r["v"] += value * share
			r["n"] += 1
			if src == "customer":
				r["estimated"] += value * share
	rows = sorted((r for r in reps.values() if r["sales_person"] != UNASSIGNED), key=lambda r: -r["v"])
	top, rest = rows[:limit], rows[limit:]
	for r in top:
		r["v"], r["estimated"] = flt(r["v"], 2), flt(r["estimated"], 2)
	return {
		"rows": top,
		"others": {"count": len(rest), "v": flt(sum(r["v"] for r in rest), 2)},
		"unassigned": flt(reps.get(UNASSIGNED, {}).get("v", 0), 2),
		"total": flt(sum(d[1] for d in docs), 2),
		"sources": _sources_summary(docs),
	}


# ---------------------------------------------------------------------------
# Rep monthly performance (replaces the desk report "Sales Person Monthly Sales")
# ---------------------------------------------------------------------------

REP_MODES = ("smart", "field", "team", "creator")


def _monthly_by_mode(doctype, company, year, amount, include_returns, mode):
	"""{rep: [12 monthly values]} plus per-document attribution for 'smart'."""
	f, t = f"{year}-01-01", f"{year}-12-31"
	matrix, sources, estimated = {}, [], {}

	def add(rep, month, v):
		matrix.setdefault(rep, [0.0] * 12)[month - 1] += v

	if mode == "smart":
		docs = _attribute(doctype, company, f, t, amount, include_returns)
		for month, value, team, src in docs:
			for sp, share in team:
				add(sp, month, value * share)
				if src == "customer":
					estimated[sp] = estimated.get(sp, 0.0) + value * share
		return matrix, _sources_summary(docs), estimated

	date_field = REP_DOCTYPES[doctype]
	amount_field = AMOUNT_FIELDS.get(amount, "base_net_total")
	cond = "" if include_returns or doctype != "Sales Invoice" else "and d.is_return = 0"
	p = {"company": company, "f": f, "t": t, "dt": doctype, "na": UNASSIGNED}
	base = f"from `tab{doctype}` d where d.docstatus=1 and d.company=%(company)s and d.`{date_field}` between %(f)s and %(t)s {cond}"
	month = f"month(d.`{date_field}`)"
	if mode == "team":
		rows = frappe.db.sql(
			f"""select st.sales_person, {month}, sum(d.`{amount_field}` * ifnull(st.allocated_percentage, 0) / 100)
			from `tab{doctype}` d join `tabSales Team` st on st.parent = d.name and st.parenttype = %(dt)s
			where d.docstatus=1 and d.company=%(company)s and d.`{date_field}` between %(f)s and %(t)s {cond}
			group by 1, 2
			union all
			select %(na)s, {month}, sum(d.`{amount_field}` * (100 - ifnull(t.pct, 0)) / 100)
			from `tab{doctype}` d left join (select parent, sum(allocated_percentage) pct from `tabSales Team`
				where parenttype = %(dt)s group by parent) t on t.parent = d.name
			where d.docstatus=1 and d.company=%(company)s and d.`{date_field}` between %(f)s and %(t)s {cond}
				and ifnull(t.pct, 0) < 100
			group by 1, 2""",
			p,
		)
	elif mode == "creator":
		rows = frappe.db.sql(f"select d.owner, {month}, sum(d.`{amount_field}`) {base} group by 1, 2", p)
		names = dict(frappe.get_all("User", fields=["name", "full_name"], as_list=True))
		rows = [(names.get(r[0]) or r[0], r[1], r[2]) for r in rows]
	else:
		field = f"coalesce(nullif(trim(d.`{OWNER_FIELD}`), ''), %(na)s)" if _has_col(doctype, OWNER_FIELD) else "%(na)s"
		rows = frappe.db.sql(f"select {field}, {month}, sum(d.`{amount_field}`) {base} group by 1, 2", p)
	for rep, m, v in rows:
		if m:
			add(rep, cint(m), flt(v))
	return matrix, sources, estimated


@frappe.whitelist()
def get_reps(company, year=None, document_type="Sales Invoice", amount="net", include_returns=1, mode="smart", refresh=0):
	_guard("reps")
	if not company or not frappe.db.exists("Company", company):
		frappe.throw("الشركة غير موجودة")
	year = cint(year) or getdate(today()).year
	F = frappe._dict(
		company=company,
		year=year,
		document_type=document_type if document_type in REP_DOCTYPES else "Sales Invoice",
		amount=amount if amount in AMOUNT_FIELDS else "net",
		include_returns=cint(include_returns),
		mode=mode if mode in REP_MODES else "smart",
	)
	return _cached("reps", F, _reps_view, refresh)


def _reps_view(F):
	matrix, sources, estimated = _monthly_by_mode(
		F.document_type, F.company, F.year, F.amount, F.include_returns, F.mode
	)
	matrix = {k: v for k, v in matrix.items() if any(abs(x) > 0.005 for x in v)}
	total = sum(sum(v) for v in matrix.values())
	if F.mode == "creator":
		full = dict(frappe.get_all("User", fields=["name", "full_name"], as_list=True))
		codes = {
			full.get(user) or user: emp
			for emp, user in frappe.get_all("Employee", filters={"user_id": ["is", "set"]}, fields=["name", "user_id"], as_list=True)
		}
	else:
		codes = dict(frappe.get_all("Sales Person", fields=["name", "employee"], as_list=True))
	rows = [
		{
			"name": rep,
			"code": codes.get(rep) or "",
			"months": [round(x, 2) for x in m],
			"total": round(sum(m), 2),
			"share": flt(sum(m) / total * 100, 2) if total else 0,
			"estimated": flt(estimated.get(rep, 0), 2),
			"active_months": sum(1 for x in m if abs(x) > 0.005),
			"unassigned": rep == UNASSIGNED,
		}
		for rep, m in matrix.items()
	]
	rows.sort(key=lambda r: (r["unassigned"], -r["total"]))
	month_totals = [flt(sum(r["months"][i] for r in rows), 2) for i in range(12)]
	years = frappe.db.sql(
		f"""select distinct year(`{REP_DOCTYPES[F.document_type]}`) from `tab{F.document_type}`
		where docstatus=1 and company=%s order by 1 desc""",
		F.company,
	)
	return {
		"filters": {k: F[k] for k in ("company", "year", "document_type", "amount", "include_returns", "mode")},
		"years": [cint(y[0]) for y in years if y[0]] or [F.year],
		"month_names": MONTHS_AR,
		"rows": rows,
		"month_totals": month_totals,
		"total": flt(total, 2),
		"sources": sources,
	}


# Month headers exactly as written in the manual yearly sheets / old report export
EXPORT_MONTHS = ["يناير", "فبراير", "مارس", "ابريل", "مايو", "يونيو", "يوليو", "اغسطس", "سبتمبر", "اكتوبر", "نوفمبر", "ديسمبر"]
EXPORT_TITLES = {
	"Sales Order": "إجمالي أوامر العمل الصادرة لعام {year}م",
	"Sales Invoice": "إجمالي الفواتير الصادرة لعام {year}م",
}


def xlsx_response(content, filename):
	"""An .xlsx download with a correctly encoded Arabic file name (RFC 5987).
	Frappe's own binary response garbles non-Latin file names."""
	from urllib.parse import quote

	from werkzeug.wrappers import Response

	r = Response(content, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
	r.headers["Content-Disposition"] = f"attachment; filename=\"report.xlsx\"; filename*=UTF-8''{quote(filename)}"
	r.headers["Cache-Control"] = "no-store"
	return r


@frappe.whitelist()
def export_reps_excel(company, year=None, document_type="Sales Invoice", amount="net", include_returns=1, mode="smart"):
	"""Excel in the exact layout of the manual yearly sheets (same as the old desk report export)."""
	from io import BytesIO

	from openpyxl import Workbook
	from openpyxl.styles import Alignment, Border, Font, Side
	from openpyxl.utils import get_column_letter

	d = get_reps(company, year, document_type, amount, include_returns, mode)
	F = frappe._dict(d["filters"])
	rows = d["rows"]

	wb = Workbook()
	ws = wb.active
	ws.title = "شامل"
	ws.sheet_view.rightToLeft = True

	thin = Side(style="thin")
	border = Border(left=thin, right=thin, top=thin, bottom=thin)
	font = Font(name="Calibri", size=12)
	bold = Font(name="Calibri", size=12, bold=True)
	center = Alignment(horizontal="center", vertical="center")

	last_col = 2 + 12 + 2  # A..P
	total_col = get_column_letter(15)  # O
	pct_col = get_column_letter(16)  # P

	ws.row_dimensions[1].height = 6
	ws.row_dimensions[2].height = 21
	ws.row_dimensions[3].height = 6
	ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_col)
	title = ws.cell(row=2, column=1, value=EXPORT_TITLES[F.document_type].format(year=F.year))
	title.font = Font(name="Calibri", size=14, bold=True)
	title.alignment = center

	name_label = "المستخدم" if F.mode == "creator" else "اسم المندوب"
	headers = ["الكود", name_label, *EXPORT_MONTHS, "إجمالي", "النسبة المئوية"]
	ws.row_dimensions[4].height = 27
	for col, label in enumerate(headers, start=1):
		c = ws.cell(row=4, column=col, value=label)
		c.font, c.alignment, c.border = bold, center, border

	first = 5
	last = first + len(rows) - 1
	total_row = last + 1
	pct_row = last + 2

	for i, r in enumerate(rows):
		row_no = first + i
		ws.row_dimensions[row_no].height = 27
		ws.cell(row=row_no, column=1, value=r["code"]).alignment = center
		ws.cell(row=row_no, column=2, value=r["name"]).alignment = center
		for m, value in enumerate(r["months"]):
			ws.cell(row=row_no, column=3 + m, value=round(value, 2) or None).number_format = "#,##0"
		ws.cell(row=row_no, column=15, value=f"=SUM(C{row_no}:N{row_no})").number_format = "#,##0"
		ws.cell(
			row=row_no, column=16, value=f"=IF(${total_col}${total_row}=0,0,{total_col}{row_no}/${total_col}${total_row})"
		).number_format = "0.00%"
		for col in range(1, last_col + 1):
			ws.cell(row=row_no, column=col).font = font
			ws.cell(row=row_no, column=col).border = border

	ws.row_dimensions[total_row].height = 30
	ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=2)
	ws.cell(row=total_row, column=1, value="الأجمالي")
	for col in range(3, 16):
		letter = get_column_letter(col)
		ws.cell(row=total_row, column=col, value=f"=SUM({letter}{first}:{letter}{last})" if rows else 0).number_format = "#,##0"
	ws.cell(row=total_row, column=16, value=f"=SUM({pct_col}{first}:{pct_col}{last})" if rows else 0).number_format = "0.00%"

	ws.row_dimensions[pct_row].height = 30
	ws.merge_cells(start_row=pct_row, start_column=1, end_row=pct_row, end_column=2)
	ws.cell(row=pct_row, column=1, value="النسبة المئوية")
	for col in range(3, 15):
		letter = get_column_letter(col)
		ws.cell(
			row=pct_row, column=col, value=f"=IF(${total_col}${total_row}=0,0,{letter}{total_row}/${total_col}${total_row})"
		).number_format = "0.00%"
	ws.cell(row=pct_row, column=15, value=f"=SUM(C{pct_row}:N{pct_row})").number_format = "0.00%"

	for row_no in (total_row, pct_row):
		for col in range(1, last_col + 1):
			c = ws.cell(row=row_no, column=col)
			c.font, c.border = bold, border
		ws.cell(row=row_no, column=1).alignment = center

	widths = {"A": 12, "B": 30, "O": 15, "P": 14}
	for col in range(1, last_col + 1):
		letter = get_column_letter(col)
		ws.column_dimensions[letter].width = widths.get(letter, 13)

	ws.freeze_panes = "C5"
	ws.print_options.horizontalCentered = True
	ws.page_setup.orientation = "landscape"
	ws.page_setup.fitToWidth = 1
	ws.sheet_properties.pageSetUpPr.fitToPage = True

	out = BytesIO()
	wb.save(out)
	prefix = "اوامر عمل مبيعات" if F.document_type == "Sales Order" else "فواتير مبيعات"
	return xlsx_response(out.getvalue(), f"{prefix} عام {F.year}م.xlsx")


@frappe.whitelist()
def get_collection(company, period="ytd", as_of=None, from_date=None, to_date=None, refresh=0):
	_guard("collection")
	F = _resolve(company, period, as_of, from_date, to_date)
	return _cached("collection", F, _collection_view, refresh)


def _collection_view(F):
	net_ar = _net_receivable(F)
	balances = _invoice_balances(F)
	inv_open = flt(sum(flt(b.amount) for b in balances), 2)
	aging = _aging(balances, F.to)

	parties = frappe.db.sql(
		"""select ple.party, c.customer_name, sum(ple.amount) v
		from `tabPayment Ledger Entry` ple left join `tabCustomer` c on c.name = ple.party
		where ple.delinked=0 and ple.account_type='Receivable' and ple.party_type='Customer'
		and ple.company=%(company)s and ple.posting_date <= %(to)s
		group by ple.party having sum(ple.amount) > 1 order by v desc""",
		_p(F),
		as_dict=True,
	)
	positive_total = sum(flt(x.v) for x in parties) or 1
	top10 = sum(flt(x.v) for x in parties[:10])

	open_by_customer = {}
	oldest = {}
	for b in balances:
		open_by_customer[b.customer] = open_by_customer.get(b.customer, 0) + flt(b.amount)
		d = getdate(b.due_date or b.posting_date)
		if b.customer not in oldest or d < oldest[b.customer]:
			oldest[b.customer] = d
	debtors = [
		{
			"customer": x.party,
			"customer_name": x.customer_name or x.party,
			"balance": flt(x.v, 2),
			"invoice_open": flt(open_by_customer.get(x.party, 0), 2),
			"oldest_days": (F.to - oldest[x.party]).days if x.party in oldest else None,
		}
		for x in parties[:10]
	]

	ttm_from = getdate(add_months(F.to, -12))
	ttm_gross = _scalar(
		"""select sum(base_grand_total) from `tabSales Invoice`
		where docstatus=1 and company=%(company)s and posting_date > %(ttm_from)s and posting_date <= %(to)s""",
		_p(F, ttm_from=ttm_from),
	)
	dso = flt(net_ar / ttm_gross * 365, 0) if ttm_gross > 0 else None

	gross_m = _sales_monthly(F, "base_grand_total")
	coll_m = _collected_monthly(F)
	rate_m = [flt(c / g * 100, 1) if g else None for c, g in zip(coll_m, gross_m)]

	return {
		"filters": _filters_payload(F),
		"months": _months_payload(F),
		"kpis": {
			"net_receivable": net_ar,
			"invoice_open": inv_open,
			"unallocated": flt(inv_open - net_ar, 2),
			"customers_with_balance": len(parties),
			"dso": dso,
			"dso_target": _settings().dso_target,
			"top10_share": flt(top10 / positive_total * 100, 1) if parties else None,
			"collected": _collected(F),
		},
		"aging": aging,
		"debtors": debtors,
		"trend": {"invoiced": gross_m, "collected": coll_m, "rate": rate_m},
	}


@frappe.whitelist()
def get_profit(company, period="ytd", as_of=None, from_date=None, to_date=None, refresh=0):
	_guard("profit")
	F = _resolve(company, period, as_of, from_date, to_date)
	return _cached("profit", F, _profit_view, refresh)


def _group_by_parent(F, root_type, limit):
	accounts = _pl_accounts(F.company)
	sign = 1 if root_type == "Income" else -1
	groups = {}
	for acc, d, v in _pl_rows(F):
		rt, parent = accounts[acc]
		if rt == root_type and F["from"] <= d <= F.to:
			groups[parent] = groups.get(parent, 0) + sign * flt(v)
	items = sorted(
		({"label": k, "value": flt(v, 2)} for k, v in groups.items() if flt(v, 2)),
		key=lambda x: -x["value"],
	)
	if len(items) > limit:
		other = sum(i["value"] for i in items[limit:])
		items = items[:limit] + [{"label": "أخرى", "value": flt(other, 2)}]
	return items


def _profit_view(F):
	inc, exp, net = _pl(F)
	pinc, pexp, pnet = _pl(F, "prev_from", "prev_to")
	inc_m, exp_m, net_m = _pl_monthly(F)
	cc = frappe.db.sql(
		"""select g.cost_center,
			sum(case when a.root_type='Income' then g.credit - g.debit else 0 end) inc,
			sum(case when a.root_type='Expense' then g.debit - g.credit else 0 end) exp
		from `tabGL Entry` g join `tabAccount` a on a.name = g.account
		where g.is_cancelled=0 and g.company=%(company)s
		and g.voucher_type != 'Period Closing Voucher'
		and g.posting_date between %(from)s and %(to)s and a.root_type in ('Income','Expense')
		group by g.cost_center order by inc desc""",
		_p(F),
		as_dict=True,
	)
	return {
		"filters": _filters_payload(F),
		"months": _months_payload(F),
		"kpis": {
			"income": {"value": inc, "prev": pinc, "delta": _delta(inc, pinc)},
			"expense": {"value": exp, "prev": pexp, "delta": _delta(exp, pexp)},
			"net": {"value": net, "prev": pnet, "delta": _delta(net, pnet)},
			"margin": flt(net / inc * 100, 1) if inc else None,
			"prev_margin": flt(pnet / pinc * 100, 1) if pinc else None,
		},
		"trend": {"income": inc_m, "expense": exp_m, "net": net_m},
		"expenses": _group_by_parent(F, "Expense", 9),
		"incomes": _group_by_parent(F, "Income", 5),
		"cost_centers": [
			{
				"cost_center": r.cost_center or "بدون مركز تكلفة",
				"income": flt(r.inc, 2),
				"expense": flt(r.exp, 2),
				"net": flt(flt(r.inc) - flt(r.exp), 2),
			}
			for r in cc
		],
	}


@frappe.whitelist()
def get_hr(company, period="ytd", as_of=None, from_date=None, to_date=None, refresh=0):
	_guard("hr")
	F = _resolve(company, period, as_of, from_date, to_date)
	return _cached("hr", F, _hr_view, refresh)


def _custody_accounts(F):
	parent = _settings().custody_parent_account
	if parent and frappe.db.get_value("Account", parent, "company") == F.company:
		lft, rgt = frappe.db.get_value("Account", parent, ["lft", "rgt"])
		return frappe.get_all(
			"Account",
			filters={"lft": [">", lft], "rgt": ["<", rgt], "is_group": 0, "company": F.company},
			fields=["name", "account_name"],
		)
	return frappe.get_all(
		"Account",
		filters={"account_name": ["like", "%عهد%"], "is_group": 0, "company": F.company},
		fields=["name", "account_name"],
	)


def _hr_view(F):
	p = _p(F)
	emp = dict(
		frappe.db.sql("select status, count(*) from `tabEmployee` where company=%(company)s group by status", p)
	)
	payroll_rows = _payroll_monthly(F)
	payroll = _latest_payroll(F)
	depts = []
	if payroll:
		m_from = getdate(payroll.month + "-01")
		depts = frappe.db.sql(
			"""select ifnull(department, 'بدون إدارة') department, count(*) n, sum(base_net_pay) v
			from `tabSalary Slip` where docstatus=1 and company=%(company)s
			and start_date between %(m_from)s and %(m_to)s
			group by department order by v desc""",
			_p(F, m_from=m_from, m_to=get_last_day(m_from)),
			as_dict=True,
		)

	leave_types = frappe.db.sql(
		"""select leave_type, count(*) n, sum(total_leave_days) days from `tabLeave Application`
		where docstatus=1 and status='Approved' and company=%(company)s
		and from_date <= %(to)s and to_date >= %(from)s
		group by leave_type order by n desc""",
		p,
		as_dict=True,
	)
	on_leave = frappe.db.sql(
		"""select employee, employee_name, leave_type, from_date, to_date from `tabLeave Application`
		where docstatus=1 and status='Approved' and company=%(company)s
		and %(as_of)s between from_date and to_date order by to_date limit 30""",
		_p(F, as_of=F.as_of),
		as_dict=True,
	)
	upcoming = frappe.db.sql(
		"""select employee, employee_name, leave_type, from_date, to_date from `tabLeave Application`
		where docstatus=1 and status='Approved' and company=%(company)s
		and from_date > %(as_of)s and from_date <= %(until)s order by from_date limit 30""",
		_p(F, as_of=F.as_of, until=add_days(F.as_of, 14)),
		as_dict=True,
	)

	adv = frappe.db.sql(
		"""select status, count(*) n, sum(advance_amount) amount,
			sum(case when status='Unpaid' then advance_amount - paid_amount
				else paid_amount - claimed_amount - return_amount end) outstanding
		from `tabEmployee Advance` where docstatus=1 and company=%(company)s
		group by status""",
		p,
		as_dict=True,
	)
	adv_top = frappe.db.sql(
		"""select employee, employee_name, sum(paid_amount - claimed_amount - return_amount) v, count(*) n
		from `tabEmployee Advance` where docstatus=1 and company=%(company)s and status in ('Paid', 'Partly Claimed and Returned')
		group by employee having v > 0 order by v desc limit 8""",
		p,
		as_dict=True,
	)

	accounts = _custody_accounts(F)
	custody = []
	if accounts:
		rows = frappe.db.sql(
			"""select account, sum(debit - credit) bal, max(posting_date) last_date
			from `tabGL Entry` where is_cancelled=0 and company=%(company)s and posting_date <= %(to)s
			and account in %(accounts)s group by account""",
			_p(F, accounts=tuple(a.name for a in accounts)),
			as_dict=True,
		)
		names = {a.name: a.account_name for a in accounts}
		for r in rows:
			if abs(flt(r.bal)) < 1:
				continue
			custody.append({
				"account": r.account,
				"label": names.get(r.account, r.account),
				"balance": flt(r.bal, 2),
				"last_date": str(r.last_date) if r.last_date else None,
				"idle_days": (F.to - getdate(r.last_date)).days if r.last_date else None,
			})
		custody.sort(key=lambda x: -x["balance"])

	ec_n, ec_v = _unpaid_expense_claims(F)
	ec_paid = frappe.db.sql(
		"""select count(*), sum(total_amount_reimbursed) from `tabExpense Claim`
		where docstatus=1 and status='Paid' and company=%(company)s and posting_date between %(from)s and %(to)s""",
		p,
	)[0]

	return {
		"filters": _filters_payload(F),
		"months": _months_payload(F),
		"employees": {"by_status": emp, "active": cint(emp.get("Active"))},
		"payroll": {
			"latest": payroll,
			"trend_net": _series([(r[0], r[1]) for r in payroll_rows], F),
			"trend_gross": _series([(r[0], r[2]) for r in payroll_rows], F),
			"trend_count": _series([(r[0], r[3]) for r in payroll_rows], F),
			"departments": depts,
		},
		"leaves": {
			"by_type": leave_types,
			"on_leave": on_leave,
			"upcoming": upcoming,
			"total": sum(cint(x.n) for x in leave_types),
		},
		"advances": {
			"by_status": adv,
			"outstanding": flt(sum(flt(x.outstanding) for x in adv if x.status != "Unpaid"), 2),
			"unpaid": flt(sum(flt(x.outstanding) for x in adv if x.status == "Unpaid"), 2),
			"top": adv_top,
		},
		"custody": {
			"accounts": custody,
			"total": flt(sum(c["balance"] for c in custody), 2),
			"count": len(custody),
		},
		"expense_claims": {
			"unpaid_count": ec_n,
			"unpaid_amount": ec_v,
			"paid_count": cint(ec_paid[0]),
			"paid_amount": flt(ec_paid[1], 2),
		},
	}


def _filters_payload(F):
	return {
		"company": F.company,
		"period": F.period,
		"from": str(F["from"]),
		"to": str(F.to),
		"prev_from": str(F.prev_from),
		"prev_to": str(F.prev_to),
		"last_invoice_date": _last_invoice_date(F.company),
	}


# VAT return and registers live in their own module; re-exported so the
# frontend calls every endpoint through executive_cockpit.api.*
from executive_cockpit.vat import export_vat_excel, get_vat, get_vat_register  # noqa: E402, F401
