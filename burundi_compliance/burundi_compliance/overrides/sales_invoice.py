from datetime import datetime

import frappe
from bs4 import BeautifulSoup
from frappe import _
from frappe.model.document import Document

from ..apis.api_builder import OBRAPI
from ..doctype.doctype_names_mapping import SETTINGS_DOCTYPE_NAME
from ..handlers.sales_invoice import (
    handle_sales_invoice_cancellation,
    handle_sales_invoice_submission,
)
from ..utils.build_headers import build_headers
from ..utils.build_invoice_payload import build_invoice_payload
from ..utils.utils import get_urls, in_configured_timeslot

obr_api = OBRAPI()

def create_obr_submission(doc: Document, method: str | None = None) -> None:
    existing = frappe.db.exists(
        "OBR Invoice Submission", {"sales_invoice": doc.name}
    )
    if not existing:
        obr_doc = frappe.new_doc("OBR Invoice Submission")
        obr_doc.sales_invoice = doc.name
        obr_doc.payment_type = doc.get("__payment_type") or "Others"
        obr_doc.insert(ignore_permissions=True)
        obr_doc.submit()
        frappe.db.commit()


def on_submit_invoice(doc: Document, method: str | None = None) -> None:
    if doc.doctype == "OBR Invoice Submission":
        # Get the linked Sales Invoice
        sales_invoice = frappe.get_doc("Sales Invoice", doc.sales_invoice)

        if sales_invoice.is_opening == "Yes":
            return

        if sales_invoice.is_consolidated:
            return

        if doc.defer_submission_to_obr:
            return

        if doc.submitted_to_obr:
            return

        generic_invoice_on_submit_override(sales_invoice, "Sales Invoice")

    else:
        # POS Invoice — use custom fields as before
        if doc.custom_defer_submission_to_obr:
            return
        if doc.custom_submitted_to_obr:
            return

        generic_invoice_on_submit_override(doc, doc.doctype)


def generic_invoice_on_submit_override(doc: Document, invoice_type: str):
    company_name = doc.company
    if not frappe.db.exists(SETTINGS_DOCTYPE_NAME, company_name):
        return

    settings_doc = frappe.get_doc(SETTINGS_DOCTYPE_NAME, company_name)

    if not settings_doc.is_active:
        return

    if not settings_doc.allow_obr_to_track_sales:
        return

    if not in_configured_timeslot(settings_doc, "invoice"):
        return

    posting_date, start_date = doc.posting_date, settings_doc.start_date
    if isinstance(posting_date, str):
        posting_date = datetime.strptime(posting_date, "%Y-%m-%d").date()

    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

    if posting_date < start_date:
        return

    environment = "sandbox" if settings_doc.sandbox else "production"
    headers = build_headers(company_name)

    request_url, server_url = get_urls(environment, "add_invoice")

    if headers and server_url and request_url:
        url = f"{server_url}/{request_url}"
        payload = build_invoice_payload(doc, settings_doc)

        obr_api.headers = headers
        obr_api.url = url
        obr_api.method = "POST"
        obr_api.payload = payload
        obr_api.service = "AddCreditNote" if doc.is_return else "AddInvoice"
        obr_api.success_callback_handler = handle_sales_invoice_submission

        frappe.enqueue(
            obr_api.make_remote_request,
            is_async=True,
            queue="default",
            timeout=600,
            job_name=f"obr_invoice_submission_{doc.name}",
            doctype=invoice_type,
            document_name=doc.name,
        )


def on_cancel(doc: Document, method: str | None = None) -> None:
    if doc.doctype == "OBR Invoice Submission":
        # Read directly from OBR Invoice Submission fields
        if not doc.submitted_to_obr:
            return

        if not doc.reason_for_creditcancel:
            frappe.throw(
                _(
                    "Please provide a reason for invoice cancellation before cancelling."
                )
            )

        soup = BeautifulSoup(doc.reason_for_creditcancel, "html.parser")
        ct_motif = soup.get_text()
        invoice_identifier = doc.invoice_identifier
        company_name = frappe.get_value("Sales Invoice", doc.sales_invoice, "company")
        doctype = "Sales Invoice"
        document_name = doc.sales_invoice

    else:
        # POS Invoice — use custom fields as before
        if not doc.custom_submitted_to_obr:
            return

        if not doc.custom_reason_for_creditcancel:
            frappe.throw(
                _(
                    "Please provide a reason for invoice cancellation before cancelling the invoice."
                )
            )

        soup = BeautifulSoup(doc.custom_reason_for_creditcancel, "html.parser")
        ct_motif = soup.get_text()
        invoice_identifier = doc.custom_invoice_identifier
        company_name = doc.company
        doctype = doc.doctype
        document_name = doc.name

    if not invoice_identifier:
        return

    if not frappe.db.exists(SETTINGS_DOCTYPE_NAME, company_name):
        return

    settings_doc = frappe.get_doc(SETTINGS_DOCTYPE_NAME, company_name)

    if not settings_doc.is_active:
        return

    if not in_configured_timeslot(settings_doc, "invoice"):
        return

    invoice_data = {
        "invoice_signature": f"{invoice_identifier}",
        "cn_motif": ct_motif,
    }

    environment = "sandbox" if settings_doc.sandbox else "production"
    headers = build_headers(company_name)

    request_url, server_url = get_urls(environment, "cancel_invoice")

    if headers and server_url and request_url:
        url = f"{server_url}/{request_url}"

        obr_api.headers = headers
        obr_api.url = url
        obr_api.method = "POST"
        obr_api.payload = invoice_data
        obr_api.service = "CancelInvoice"
        obr_api.success_callback_handler = handle_sales_invoice_cancellation

        frappe.enqueue(
            obr_api.make_remote_request,
            is_async=True,
            queue="default",
            timeout=600,
            job_name=f"obr_invoice_cancellation_{document_name}",
            doctype=doctype,
            document_name=document_name,
        )


def before_save(doc: Document, method: str | None = None) -> None:
    if doc.doctype == "OBR Invoice Submission":
        if not doc.sales_invoice:
            return
        sales_invoice = frappe.get_doc("Sales Invoice", doc.sales_invoice)
        if sales_invoice.is_return:
            doc.einvoice_signatures = ""
            doc.invoice_registered_no = ""
            doc.invoice_registered_date = None
            doc.submitted_to_obr = 0