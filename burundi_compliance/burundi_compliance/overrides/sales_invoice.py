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


def get_obr_submission(invoice_name: str):
    """Get OBR Invoice Submission record for a Sales Invoice"""
    existing = frappe.db.exists(
        "OBR Invoice Submission", {"sales_invoice": invoice_name}
    )
    if existing:
        return frappe.get_doc("OBR Invoice Submission", existing)
    return None


def on_submit_invoice(doc: Document, method: str | None = None) -> None:
    if doc.is_opening == "Yes":
        return

    if doc.doctype == "Sales Invoice" and doc.is_consolidated:
        return

    if doc.doctype == "Sales Invoice":
        # Check OBR Invoice Submission for Sales Invoice
        obr_submission = get_obr_submission(doc.name)
        if obr_submission:
            if obr_submission.defer_submission_to_obr:
                return
            if obr_submission.submitted_to_obr:
                return
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
    company_name = doc.company
    if not frappe.db.exists(SETTINGS_DOCTYPE_NAME, company_name):
        return

    settings_doc = frappe.get_doc(SETTINGS_DOCTYPE_NAME, company_name)

    if not settings_doc.is_active:
        return

    if not in_configured_timeslot(settings_doc, "invoice"):
        return

    posting_date, start_date = doc.posting_date, settings_doc.start_date

    if isinstance(posting_date, str):
        posting_date = datetime.strptime(doc.posting_date, "%Y-%m-%d").date()

    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

    if posting_date < start_date:
        return

    if doc.doctype == "Sales Invoice":
        # Get data from OBR Invoice Submission for Sales Invoice
        obr_submission = get_obr_submission(doc.name)
        if not obr_submission:
            return
        if not obr_submission.submitted_to_obr:
            return
        if not obr_submission.reason_for_creditcancel:
            frappe.throw(
                _(
                    "Please provide a reason for invoice cancellation before cancelling the invoice."
                )
            )
        soup = BeautifulSoup(obr_submission.reason_for_creditcancel, "html.parser")
        ct_motif = soup.get_text()
        invoice_identifier = obr_submission.invoice_identifier
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

    if not invoice_identifier:
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
        payload = invoice_data

        obr_api.headers = headers
        obr_api.url = url
        obr_api.method = "POST"
        obr_api.payload = payload
        obr_api.service = "CancelInvoice"
        obr_api.success_callback_handler = handle_sales_invoice_cancellation

        frappe.enqueue(
            obr_api.make_remote_request,
            is_async=True,
            queue="default",
            timeout=600,
            job_name=f"obr_invoice_cancellation_{doc.name}",
            doctype=doc.doctype,
            document_name=doc.name,
        )