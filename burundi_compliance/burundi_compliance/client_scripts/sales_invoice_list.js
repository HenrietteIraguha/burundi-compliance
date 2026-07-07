frappe.listview_settings['OBR Invoice Submission'] = {
  onload: function (listview) {
    listview.page.add_action_item(__('Submit to EBMS'), function () {
      submit_bulk_obr_submissions(listview)
    })
  }
}

function submit_bulk_obr_submissions(listview) {
  let names = []
  $.each(listview.get_checked_items(), function (key, value) {
    names.push(value.name)
  })

  if (names.length === 0) {
    frappe.throw(__('No rows selected.'))
  }

  frappe.call({
    method:
      'burundi_compliance.burundi_compliance.apis.sales_invoice.bulk_submit_invoices_to_obr',
    args: {
      doctype: 'OBR Invoice Submission',
      invoice_list: names,
    },
    freeze: true,
    freeze_message: __('Submitting to EBMS...'),
  })
}