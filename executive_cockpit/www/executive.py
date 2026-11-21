import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=" + frappe.utils.quote(frappe.request.path)
		raise frappe.Redirect

	from executive_cockpit.api import has_app_permission

	if not has_app_permission():
		frappe.throw("ليس لديك صلاحية الوصول إلى لوحة القيادة التنفيذية", frappe.PermissionError)

	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()  # nosemgrep: persist the csrf token for this session
	context.csrf_token = csrf_token
	context.site_name = frappe.local.site
	return context
