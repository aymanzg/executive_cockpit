import frappe
from frappe.model.document import Document


class ExecutiveCockpitSettings(Document):
	def on_update(self):
		from executive_cockpit.api import clear_cache

		clear_cache()
