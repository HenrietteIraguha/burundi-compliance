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


def on_submit(doc: Document, method: str | None = None) -> None:
    sales_invoice = frappe.get_doc("Sales Invoice", doc.sales_invoice)

    if sales_invoice.is_opening == "Yes":
        return

    if sales_invoice.is_consolidated:
        return

    if doc.defer_submission_to_obr:
        return

    if doc.submitted_to_obr:
        return

    company_name = sales_invoice.company
    if not frappe.db.exists(SETTINGS_DOCTYPE_NAME, company_name):
        return

    settings_doc = frappe.get_doc(SETTINGS_DOCTYPE_NAME, company_name)

    if not settings_doc.is_active:
        return

    if not settings_doc.allow_obr_to_track_sales:
        return

    if not in_configured_timeslot(settings_doc, "invoice"):
        return

    posting_date, start_date = sales_invoice.posting_date, settings_doc.start_date
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
        payload = build_invoice_payload(sales_invoice, settings_doc)

        obr_api.headers = headers
        obr_api.url = url
        obr_api.method = "POST"
        obr_api.payload = payload
        obr_api.service = "AddCreditNote" if sales_invoice.is_return else "AddInvoice"
        obr_api.success_callback_handler = handle_sales_invoice_submission

        frappe.enqueue(
            obr_api.make_remote_request,
            is_async=True,
            queue="default",
            timeout=600,
            job_name=f"obr_invoice_submission_{sales_invoice.name}",
            doctype="Sales Invoice",
            document_name=sales_invoice.name,
        )


def on_cancel(doc: Document, method: str | None = None) -> None:
    sales_invoice = frappe.get_doc("Sales Invoice", doc.sales_invoice)
    company_name = sales_invoice.company

    if not frappe.db.exists(SETTINGS_DOCTYPE_NAME, company_name):
        return

    settings_doc = frappe.get_doc(SETTINGS_DOCTYPE_NAME, company_name)

    if not settings_doc.is_active:
        return

    if not in_configured_timeslot(settings_doc, "invoice"):
        return

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
            job_name=f"obr_invoice_cancellation_{sales_invoice.name}",
            doctype="Sales Invoice",
            document_name=sales_invoice.name,
        )