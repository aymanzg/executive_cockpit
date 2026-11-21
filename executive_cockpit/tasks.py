import frappe
from frappe.utils import today


def warm_cache():
	"""Pre-compute the dashboard for the default company so it opens instantly."""
	from executive_cockpit import api

	s = api._settings()
	if not s.default_company or not s.cache_minutes:
		return
	views = [
		("overview", api._overview),
		("sales", api._sales_view),
		("collection", api._collection_view),
		("profit", api._profit_view),
		("hr", api._hr_view),
	]
	for period in ("ytd", "month", "quarter"):
		F = api._resolve(s.default_company, period, today())
		for name, compute in views:
			try:
				api._cached(name, F, compute, refresh=1)
			except Exception:
				frappe.log_error(title=f"Executive Cockpit: warm {name}/{period} failed")
