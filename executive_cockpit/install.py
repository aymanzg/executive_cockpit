import frappe

ROLE = "Executive Dashboard"


def after_install():
	ensure_role()


def ensure_role():
	if not frappe.db.exists("Role", ROLE):
		frappe.get_doc(
			{"doctype": "Role", "role_name": ROLE, "desk_access": 1, "is_custom": 0}
		).insert(ignore_permissions=True)
		frappe.db.commit()
