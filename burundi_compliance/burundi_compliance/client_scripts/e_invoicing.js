frappe.ui.form.on('Sales Invoice', {
  before_submit: function(frm) {
    return new Promise((resolve, reject) => {
        let fields = [
            {
                label: 'Payment Type',
                fieldname: 'payment_type',
                fieldtype: 'Select',
                options: '\nCash\nBank\nCredit\nOthers',
                reqd: 1
            }
        ]

        if (frm.doc.is_return) {
            fields.push({
                label: 'Reason for Credit Note',
                fieldname: 'reason_for_credit',
                fieldtype: 'Text Editor',
                reqd: 1
            })
        }

        frappe.prompt(
            fields,
            function(values) {
                frm.doc.__payment_type = values.payment_type
                if (values.reason_for_credit) {
                    frm.doc.__reason_for_credit = values.reason_for_credit
                }
                resolve()
            },
            __('OBR Invoice Information'),
            __('Confirm')
        )
    })
},
  
   before_cancel: function(frm) {
    return new Promise((resolve, reject) => {
      frappe.prompt(
        {
          label: 'Reason for Cancellation',
          fieldname: 'reason_for_cancel',
          fieldtype: 'Text Editor',
          reqd: 1
        },
        function(values) {
          frm.doc.__reason_for_cancel = values.reason_for_cancel
          resolve()
        },
        __('Reason for Cancellation'),
        __('Confirm')
      )
    })
  },
  refresh: function (frm) {
    
  },
})


function addSalesInvoiceButtons(frm, obr) {
  if (obr.submitted_to_obr && frm.doc.docstatus == 1) {
    frm.add_custom_button(
      __('Get Invoice'),
      function () {
        callBackendFunction(
          frm,
          'apis.sales_invoice.get_invoice_from_obr',
          'GET',
          __('Getting Invoice...'),
          'Sales Invoice'
        )
      },
      __('eBIMS Actions')
    )
  }

  if (!obr.einvoice_signatures && frm.doc.docstatus == 1) {
    frm.add_custom_button(
      __('Re-Submit'),
      function () {
        callBackendFunction(
          frm,
          'apis.sales_invoice.resubmit_invoice_to_obr',
          'POST',
          __('Resubmitting Invoice...'),
          'Sales Invoice'
        )
      },
      __('eBIMS Actions')
    )
  }

  if (
    obr.submitted_to_obr &&
    frm.doc.docstatus == 2 &&
    !obr.ebms_invoice_cancelled
  ) {
    frm.add_custom_button(
      __('Cancel Invoice in OBR'),
      function () {
        callBackendFunction(
          frm,
          'apis.sales_invoice.cancel_invoice_in_obr',
          'POST',
          __('Cancelling Invoice in OBR...'),
          'Sales Invoice'
        )
      },
      __('eBIMS Actions')
    )
  }
}

frappe.ui.form.on('OBR Invoice Submission', {
  refresh: function (frm) {
    if (frm.doc.docstatus == 1 || (frm.doc.docstatus == 2 && frm.doc.submitted_to_obr)) {
      addOBRInvoiceButtons(frm)
    }
  },
})

function addOBRInvoiceButtons(frm) {
  if (frm.doc.submitted_to_obr && frm.doc.docstatus == 1) {
    frm.add_custom_button(
      __('Get Invoice'),
      function () {
        callBackendFunction(
          frm,
          'apis.sales_invoice.get_invoice_from_obr',
          'GET',
          __('Getting Invoice...'),
          'Sales Invoice'
        )
      },
      __('eBIMS Actions')
    )
  }

  if (!frm.doc.einvoice_signatures) {
    frm.add_custom_button(
      __('Re-Submit'),
      function () {
        callBackendFunction(
          frm,
          'apis.sales_invoice.resubmit_invoice_to_obr',
          'POST',
          __('Resubmitting Invoice...'),
          'Sales Invoice'
        )
      },
      __('eBIMS Actions')
    )
  }

  if (
    frm.doc.submitted_to_obr &&
    frm.doc.docstatus == 2 &&
    !frm.doc.ebms_invoice_cancelled
  ) {
    frm.add_custom_button(
      __('Cancel Invoice in OBR'),
      function () {
        callBackendFunction(
          frm,
          'apis.sales_invoice.cancel_invoice_in_obr',
          'POST',
          __('Cancelling Invoice in OBR...'),
          'Sales Invoice'
        )
      },
      __('eBIMS Actions')
    )
  }
}

frappe.ui.form.on('POS Invoice', {
  onload: function (frm) {
    if (frm.is_new()) {
      frm.set_value('custom_submitted_to_obr', 0)
      frm.set_value('custom_einvoice_signatures', '')
      frm.set_value('custom_invoice_registered_no', '')
      frm.set_value('custom_invoice_registered_date', '')
      frm.set_value('custom_invoice_identifier', '')
    }
  },

  refresh: function (frm) {
    if (frm.doc.docstatus == 1) {
      addInvoiceButtons(frm, 'POS Invoice')
    }
  },
})

function addInvoiceButtons(frm, invoiceType) {
  if (frm.doc.custom_submitted_to_obr && frm.doc.docstatus == 1) {
    frm.add_custom_button(
      __('Get Invoice'),
      function () {
        callBackendFunction(
          frm,
          'apis.sales_invoice.get_invoice_from_obr',
          'GET',
          __('Getting Invoice...'),
          invoiceType
        )
      },
      __('eBIMS Actions')
    )
  }

  if (!frm.doc.custom_einvoice_signatures) {
    frm.add_custom_button(
      __('Re-Submit'),
      function () {
        callBackendFunction(
          frm,
          'apis.sales_invoice.resubmit_invoice_to_obr',
          'POST',
          __('Resubmitting Invoice...'),
          invoiceType
        )
      },
      __('eBIMS Actions')
    )
  }

  if (
    frm.doc.custom_submitted_to_obr &&
    frm.doc.docstatus == 2 &&
    !frm.doc.custom_ebms_invoice_cancelled
  ) {
    frm.add_custom_button(
      __('Cancel Invoice in OBR'),
      function () {
        callBackendFunction(
          frm,
          'apis.sales_invoice.cancel_invoice_in_obr',
          'POST',
          __('Cancelling Invoice in OBR...'),
          invoiceType
        )
      },
      __('eBIMS Actions')
    )
  }
}

function callBackendFunction(
  frm,
  method,
  action,
  freeze_message = null,
  invoiceType = null
) {
  frappe.call({
    method: `burundi_compliance.burundi_compliance.${method}`,
    args: {
      name: frm.doc.name,
      invoice_type: invoiceType,
    },
    callback: function (response) {
      if (response) {
        if (action === 'GET') {
          if (response.message.success) {
            showInvoiceDetailsDialog(response.message.result)
          } else {
            frappe.msgprint(__('Failed to Retrieve Invoice details'))
          }
        }

        if (action === 'POST') {
          if (frm.doc.docstatus == 1) {
            frappe.msgprint(__('Invoice Resubmission has been Queued'))
          } else {
            frappe.msgprint(__('Invoice Cancellation has been Queued'))
          }
        }
      }
    },
    freeze: true,
    freeze_message: freeze_message || __('Processing...'),
  })
}

function showInvoiceDetailsDialog(result) {
  let invoice = result.invoices[0]

  let dialog = new frappe.ui.Dialog({
    title: __('Invoice Retrieved successfully'),
    fields: [
      {
        label: __('Invoice Number'),
        fieldname: 'invoice_number',
        fieldtype: 'Data',
        default: invoice.invoice_number,
        read_only: true,
      },
      {
        label: __('Invoice Date'),
        fieldname: 'invoice_date',
        fieldtype: 'Data',
        default: invoice.invoice_date,
        read_only: true,
      },
      {
        label: __('TP Type'),
        fieldname: 'tp_type',
        fieldtype: 'Data',
        default: invoice.tp_type,
        read_only: true,
      },
      {
        label: __('TP Name'),
        fieldname: 'tp_name',
        fieldtype: 'Data',
        default: invoice.tp_name,
        read_only: true,
      },
      {
        label: __('TP TIN'),
        fieldname: 'tp_TIN',
        fieldtype: 'Data',
        default: invoice.tp_TIN,
        read_only: true,
      },
      {
        label: __('Customer Name'),
        fieldname: 'customer_name',
        fieldtype: 'Data',
        default: invoice.customer_name,
        read_only: true,
      },
      {
        label: __('Customer TIN'),
        fieldname: 'customer_TIN',
        fieldtype: 'Data',
        default: invoice.customer_TIN,
        read_only: true,
      },
    ],
  })

  dialog.set_primary_action(__('Close'), function () {
    dialog.hide()
  })

  dialog.show()
}