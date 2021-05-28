# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.    
#
# You should have received a copy of the GNU Affero General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"
    
    internal_notes = fields.Text('Notes')

    
class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ["account.move", "mail.thread"]

    def _get_company_id(self):
        """
        @summary: This will default Company Id on the form by
        getting the attached company_id of the current User. 
        """
        user_id = self.env.uid
        company_id = self.env['res.users'].browse(user_id).company_id.id
        return company_id

    po_id = fields.Many2one('purchase.order', compute='_get_po_source', string='Purchase Order',
                            track_visibility='onchange', store=True)
    source_doc = fields.Char(compute='_get_po_source', string='Source Document', store=True)
    journal_type = fields.Selection(string='Journal Type', related='journal_id.type')
    payment_id = fields.Many2one('account.payment', related='line_ids.payment_id')
    amount_in_words = fields.Char('Amount in Words', related='payment_id.check_amount_in_words')
    check_no = fields.Char('Check No.', track_visibility='onchange')
    company_id = fields.Many2one('res.company', string='Company', default=_get_company_id, track_visibility='onchange')
    certified_by = fields.Many2one(related='company_id.certified_by_id', string='Certified By', track_visibility='onchange')
    noted_by = fields.Many2one(related='company_id.noted_by_id', string='Noted By', track_visibility='onchange')
    payee_id = fields.Many2one('res.partner', string='Payee', related='payment_id.payee_id', track_visibility='onchange')

    @api.depends('ref', 'invoice_origin')
    def _get_po_source(self):
        PurchaseOrder = self.env['purchase.order']
        for rec in self:
            po_ids = PurchaseOrder.search([('name', '=', rec.invoice_origin)])
            if po_ids:
                rec.po_id = po_ids[0].id
            else:
                rec.po_id = False
            rec.source_doc = rec.ref

    def action_print_voucher(self):
        if self.type == 'in_invoice':
            return self.env.ref('tf_ph_voucher.action_report_account_payable_voucher').report_action(self)
        return self.env.ref('tf_ph_voucher.action_report_check_voucher').report_action(self)

    def action_print_payment_voucher(self):
        return self.env.ref('tf_ph_voucher.action_report_check_voucher').report_action(self)

# class CheckVoucherReport(models.AbstractModel):
#     _name = 'report.ss_ph_voucher.report_check_voucher'
# 
#     @api.model
#     def render_html(self, docids, data=None):
#         Report = self.env['report']
#         report = Report._get_report_from_name('ss_ph_voucher.report_check_voucher')
# 
#         AccountMove = self.env['account.move']
#         move_ids = AccountMove.browse(docids)
#             
#         for rec in move_ids:
#             if rec.journal_id.type == 'bank' and rec.partner_id.supplier == True:
#                 pass
#             else:
#                 raise ValidationError(("You can't print Payment Voucher in this selection."))
#     
#         docargs = {
#             'doc_ids': self._ids,
#             'doc_model': report.model,
#             'docs': move_ids,
#         }
#         return Report.render('ss_ph_voucher.report_check_voucher', docargs)
# 
#     
# class AccountsPayableReport(models.AbstractModel):
#     _name = 'report.ss_ph_voucher.report_account_payable_voucher'
# 
#     @api.model
#     def render_html(self, docids, data=None):
#         Report = self.env['report']
#         report = Report._get_report_from_name('ss_ph_voucher.report_account_payable_voucher')
# 
#         AccountMove = self.env['account.move']
#         move_ids = AccountMove.browse(docids)
#             
#         for rec in move_ids:
#             if rec.journal_id.type == 'purchase':
#                 pass
#             else:
#                 raise ValidationError(("You can't print Accounts Payable Voucher in this selection."))
#     
#         docargs = {
#             'doc_ids': self._ids,
#             'doc_model': report.model,
#             'docs': move_ids,
#         }
#         return Report.render('ss_ph_voucher.report_account_payable_voucher', docargs)
