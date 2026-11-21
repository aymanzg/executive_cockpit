import frappe
from frappe.utils import add_months, getdate, today

# The warm job runs every 15 minutes; entries it writes outlive the next run so
# users never land in the gap between expiry and re-computation.
WARM_TTL = 25 * 60


def _companies(s):
	from executive_cockpit import api

	c = s.default_company or api._busiest_company()
	return [c] if c else []


def enqueue_warm(force=False):
	"""Scheduler entry point (every 15 minutes).

	Skips entirely unless the dashboard was opened in the last couple of hours, so an
	unused dashboard costs the server nothing. The work runs on the long queue so it
	never holds up the short / default jobs (emails, notifications) of any site on the
	bench, and a run already queued or running is not queued twice."""
	from executive_cockpit import api

	if not force and not api._redis().get_value(api.SEEN_KEY, expires=True):
		return
	frappe.enqueue(
		"executive_cockpit.tasks.warm_cache",
		queue="long",
		job_id=f"executive_cockpit_warm::{frappe.local.site}",
		deduplicate=True,
	)


def warm_cache():
	"""Pre-compute every section for the default company so the dashboard opens instantly."""
	from executive_cockpit import api, vat

	s = api._settings()
	if not s.cache_minutes:
		return
	ttl = max(WARM_TTL, s.cache_minutes * 60)
	views = [
		("overview", api._overview),
		("sales", api._sales_view),
		("collection", api._collection_view),
		("profit", api._profit_view),
		("hr", api._hr_view),
	]
	d = getdate(today())
	last = getdate(add_months(d, -1))
	for company in _companies(s):
		jobs = []
		for period in ("ytd", "month", "quarter"):
			F = api._resolve(company, period, today())
			jobs += [(f"{name}/{period}", name, F, compute) for name, compute in views]
		jobs.append(("reps", "reps", api._reps_filters(company), api._reps_view))
		for y, pt, n in ((last.year, "month", last.month), (d.year, "month", d.month), (d.year, "quarter", (d.month - 1) // 3 + 1)):
			jobs.append((f"vat/{y}-{pt}-{n}", "vat", vat._resolve(company, y, pt, n), vat._compute))
		try:
			vat._years(company, refresh=True)
		except Exception:
			frappe.log_error(title="Executive Cockpit: warm vat years failed")
		for label, name, F, compute in jobs:
			try:
				api._cached(name, F, compute, refresh=1, ttl=ttl)
			except Exception:
				frappe.log_error(title=f"Executive Cockpit: warm {label} failed")
