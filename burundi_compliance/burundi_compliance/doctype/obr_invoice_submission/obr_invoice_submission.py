# Copyright (c) 2026, Navari Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class OBRInvoiceSubmission(Document):

    def before_insert(self):
        """Auto populate fields from linked Sales Invoice when record is created"""
        if self.sales_invoice:
            sales_invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)
            # Check if there's already an OBR submission for this invoice
            existing = frappe.db.exists(
                "OBR Invoice Submission", 
                {"sales_invoice": self.sales_invoice}
            )
            if existing and existing != self.name:
                frappe.throw(
                    f"An OBR Invoice Submission already exists for Sales Invoice {self.sales_invoice}"
                )

    def validate(self):
        """Validate that Sales Invoice is submitted before allowing OBR submission"""
        if self.sales_invoice:
            docstatus = frappe.db.get_value("Sales Invoice", self.sales_invoice, "docstatus")
            if docstatus != 1:
                frappe.throw(
                    "Sales Invoice must be submitted before creating an OBR Invoice Submission"
                )
