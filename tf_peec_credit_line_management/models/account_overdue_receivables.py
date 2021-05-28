# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Joshua <joshua@taliform.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsibility of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
##############################################################################
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, date
from odoo.addons.base.models.res_partner import WARNING_MESSAGE, WARNING_HELP

class AccountOverdueReceivables(models.Model):
    _name = 'account.overdue.receivables'
    _description = 'Account Overdue Receivables'

    credit_line = fields.Boolean(default=False)
    max_percentage = fields.Float(string='Max Percentage',
                                  help='Indicate the maximum percentage of the customer’s overdue invoices amount '
                                       'to the total unpaid invoices amount that will trigger an exception action.')

    def action_analyze_overdue_accounts(self):
        is_credit_line = self.env['ir.config_parameter'].sudo().get_param('account_overdue_receivables.credit_line')
        CreditApplication = self.env['credit.application']
        AccountInvoices = self.env['account.move']
        if is_credit_line:
            max_percent_config = self.env['ir.config_parameter'].sudo().get_param(
                'account_overdue_receivables.max_percentage')
            unpaid_invoices = AccountInvoices.search([('invoice_payment_state', '!=', 'paid'), ('state', '=', 'posted'),
                                                      ('type', '=', 'out_invoice')])
            overdue_invoices = []
            current_invoices = []
            partners = unpaid_invoices.mapped('partner_id')
            total_unpaid_invoice = 0.0
            for rec in unpaid_invoices:
                payment_term_days = timedelta(days=rec.invoice_payment_term_id.line_ids.days)
                total_unpaid_invoice += rec.amount_residual
                if rec.invoice_payment_term_id and (rec.invoice_date + payment_term_days) <= date.today():
                    overdue_invoices.append(rec.id)
                else:
                    current_invoices.append(rec.id)
            for partner in partners:
                partner_overdue_invoices = unpaid_invoices.browse(overdue_invoices).filtered(lambda x:
                                                                                             x.partner_id == partner)
                partner_current_invoices = unpaid_invoices.browse(current_invoices).filtered(lambda x:
                                                                                             x.partner_id == partner)
                overdue_amount = int(sum(partner_overdue_invoices.mapped('amount_residual')))
                current_unpaid_amount = int(sum(partner_current_invoices.mapped('amount_residual')))
                partner_total_amount = overdue_amount + current_unpaid_amount
                partner_credit_app = CreditApplication.search([
                    ('partner_id', '=', partner.id),
                    ('state', '=', 'approved')
                ])
                credit_app_amount = int(partner_credit_app.approved_credit_line)
                has_partner_credit = False
                if credit_app_amount > 0 and partner_total_amount > credit_app_amount:
                    has_partner_credit = True
                sale_vals = {
                    'sale_warn':  'no-message',
                    'sale_warn_msg': '',
                    'picking_warn': 'no-message',
                    'picking_warn_msg': ''
                }
                overdue_percentage = 0
                if overdue_amount != 0 and partner_total_amount != 0:
                    overdue_percentage = (overdue_amount/partner_total_amount)*100
                credit_max = float(max_percent_config)
                if overdue_percentage >= credit_max or has_partner_credit:
                    warn_msg = f'This customer has existing invoices that are overdue. \n' \
                               f'Total Overdue Amount: {overdue_amount} \n' \
                               f'Total Unpaid Invoice: {current_unpaid_amount}'
                    sale_vals = {
                        'sale_warn': 'block',
                        'sale_warn_msg': warn_msg,
                        'picking_warn': 'block',
                        'picking_warn_msg': warn_msg
                    }
                print(sale_vals)
                partner.write(sale_vals)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    sale_warn = fields.Selection(WARNING_MESSAGE, 'Sales Warnings', default='no-message', help=WARNING_HELP,
                                 track_visibility='onchange')
    sale_warn_msg = fields.Text('Message for Sales Order', track_visibility='onchange')
    picking_warn = fields.Selection(WARNING_MESSAGE, 'Stock Picking', help=WARNING_HELP, default='no-message',
                                    track_visibility='onchange')
    picking_warn_msg = fields.Text('Message for Stock Picking', track_visibility='onchange')


class CreditApplication(models.Model):
    _inherit = 'credit.application'

    @api.onchange('partner_id')
    def _onchange_partner(self):
        CreditApplication = self.env['credit.application']
        for rec in self:
            partner_approved_rec = CreditApplication.search([
                ('partner_id', '=', rec.partner_id.id),
                ('state', '=', 'approved')
            ])
            if partner_approved_rec:
                raise ValidationError('Partner still has an existing approved credit application!')
