# -*- coding: utf-8 -*-

import copy
import re
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools.misc import formatLang, format_date, parse_date


class AccountReconciliation(models.AbstractModel):
    _inherit = 'account.reconciliation.widget'

    @api.model
    def process_bank_statement_line(self, st_line_ids, data):
        res = super(AccountReconciliation, self).process_bank_statement_line(st_line_ids, data)
        AccountMove = self.env['account.move']
        new_dict_data = data[0].get('new_aml_dicts')
        if 'moves' in res:
            acc_move_id = res.get('moves')[0]
            if acc_move_id:
                acc_record = AccountMove.browse(acc_move_id)
                for acc_move in acc_record.payment_id.reconciled_invoice_ids:
                    for payment in acc_move.payment_ids:
                        payment.state = 'reconciled'
                        payment.pdc_id.state = 'paid'
        if new_dict_data:
            cf_type_id = new_dict_data[0].get('cf_html_type_id')
            if cf_type_id:
                cf_section_id = new_dict_data[0].get('cf_html_section_id')
                move_id = res.get('moves', '')[0]
                new_invoice = AccountMove.search([
                    ('id', '=', move_id)
                ])
                new_invoice.cf_html_type_id = cf_type_id
                new_invoice.cf_html_section_id = cf_section_id
        dict_data = data[0].get('counterpart_aml_dicts')
        if dict_data:
            ctr_aml_name = dict_data[0].get('name')
            if ctr_aml_name:
                invoices = AccountMove.search([
                    ('name', '=', ctr_aml_name)
                ])
                for rec in invoices:
                    for payment in rec.payment_ids:
                        payment.state = 'reconciled'
                        payment.pdc_id.state = 'paid'
                return res
    def get_cf_section_ids(self):
        cf_operating = self.env.ref('tf_ph_reports.account_financial_report_cashsummary_operating0').id
        cf_investing = self.env.ref('tf_ph_reports.account_financial_report_cashsummary_investing0').id
        cf_financing = self.env.ref('tf_ph_reports.account_financial_report_cashsummary_financing0').id

        return {'cf_operating' : cf_operating, 'cf_investing' : cf_investing, 'cf_financing': cf_financing }