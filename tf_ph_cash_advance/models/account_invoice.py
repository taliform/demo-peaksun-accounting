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
from odoo import models, fields, api, _
from lxml import etree


class AccountInvoice(models.Model):
    _inherit = 'account.move'

    @api.depends('amount_total')
    def _check_amount_change(self):
        for rec in self:
            rec.reason_req = True
            if not rec.is_liquidation:
                if rec.cash_advance_id and rec.type == 'in_invoice' and rec.cash_advance_id.ca_type == 'ca':
                    ca_id = rec.cash_advance_id
                    if ca_id.amount == rec.amount_total:
                        rec.reason_req = False
                        rec.changed_amt_reason = False

            if rec.is_liquidation or rec.is_reimburse or rec.is_return or rec.cash_advance_id.ca_type == 'dr' \
                    or rec.cash_management_id or rec.cash_replenishment_id or not rec.is_fund or rec.is_replenishment:
                rec.reason_req = False

            if not rec.cash_advance_id and not rec.cash_management_id:
                rec.reason_req = False

    cash_advance_transaction_id = fields.Many2one('cash.advance.transaction', 'Cash Advance Transaction')
    cash_advance_id = fields.Many2one('cash.advance', 'Cash Advance')
    ca_invoice_tag = fields.Selection([('return', 'For Return'), ('reimburse', 'For Reibursement')],
                                      string='CA Invoice')
    is_liquidation = fields.Boolean('Liquidation')
    is_reimburse = fields.Boolean('Reimbursement')
    is_return = fields.Boolean('Returned')
    changed_amt_reason = fields.Text('Amount Changed Reason')
    reason_req = fields.Boolean(compute='_check_amount_change', string='Reason Required', store=True)

    @api.model
    def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
        '''
        @summary: Override this method to disable create/edit button for CM Managers (CA Invoices menu).
        '''

        res = super(AccountInvoice, self).fields_view_get(view_id=view_id, view_type=view_type,
                                                          toolbar=toolbar, submenu=submenu)
        ResUsers = self.env['res.users']
        doc = etree.XML(res['arch'])
        is_ca_manager = ResUsers.browse(self._uid).has_group('tf_ph_cash_advance.group_cash_advance_manager')
        is_ap = ResUsers.browse(self._uid).has_group('account.group_account_invoice')

        if view_type in ['tree', 'form']:
            # Hide Create button
            if is_ca_manager and not is_ap:
                for node in doc.xpath("//" + view_type):
                    node.attrib['create'] = 'false'
                    node.attrib['edit'] = 'false'
            res['arch'] = etree.tostring(doc)
        return res

    def write(self, vals):
        '''
        @note: This will transition the CA state from Fund Requested to Open (if paid).
        '''
        res = super(AccountInvoice, self).write(vals)
        for rec in self:
            ca_id = rec.cash_advance_id
            if not ca_id:
                return res
            # Revised Amount
            if vals.get('changed_amt_reason', False):
                ca_id.write({'amount_changed': True})

            # Invoice Payment
            invoice_payment_state = vals.get('invoice_payment_state', False)
            if invoice_payment_state:
                if invoice_payment_state == 'paid' and ca_id.state == 'confirm':
                    if rec.amount_total == ca_id.amount:
                        ca_id.write({'journal_id': rec.journal_id.id,
                                     'amount': rec.amount_total})
                        ca_id.change_state('open')
                    else:
                        # CA Amount should be revised
                        ca_id.write({'amount_changed': True})
                        ca_id.change_state('confirm')

            # Invoice Cancellation
            invoice_state = vals.get('state', False)
            if invoice_state:
                if invoice_state == 'cancel':
                    # Fund Request:
                    ca_id.write({'invoice_id': False})
                    ca_id.change_state('cancel')
                    ca_id.invoice_id.write({'cash_advance_id': False})

                    # Direct Reimbursement
                    if ca_id.invoice_id.id == rec.id:
                        ca_id.write({'state': 'submit',
                                     'dr_invoice_id': False})

                    # For Return/Reimbursement Invoice
                    if ca_id.wo_return_invoice_id.id == rec.id:
                        ca_id.write({'state': 'submit', 'wo_return_invoice_id': False, 'total_return': 0.0})

                    if ca_id.wo_reimburse_invoice_id.id == rec.id:
                        ca_id.write({'state': 'submit', 'wo_reimburse_invoice_id': False, 'total_reimburse': 0.0})
        return res

    def unlink(self):
        '''
        @note: If the invoice is for return/reimbursement, the CA reference will be for validation again.
        '''
        for rec in self:
            ca_id = rec.cash_advance_id
            if ca_id:
                # Fund request invoice
                if ca_id.invoice_id.id == rec.id:
                    # Send notification
                    partner_id = ca_id.issued_to.partner_id
                    partners = [partner_id.id]
                    msg_vals = {}
                    message = """
                        <p>Hi %s,</p>
                        <p>The invoice reference of Cash Advance: <b>%s</b> has been deleted.</p> 
                        <p>Thank you.</p>
                    """
                    msg_vals['body'] = message % (partner_id.name, ca_id.name)
                    msg_vals['partner_ids'] = partners

                    ca_id.message_post(type='notification', **msg_vals)
                    ca_id.write({'state': 'draft', 'invoice_id': False})
                    if self._context.get('cancel_ca', False):
                        ca_id.write({'state': 'cancel'})

                # Direct Reimbursement
                if ca_id.ca_type == 'dr' \
                        and rec.cash_advance_id.invoice_id.id == rec.id:
                    ca_id.write({'state': 'submit', 'wo_reimburse_invoice_id': False})

                # For Return/Reimbursement Invoice
                if rec.cash_advance_id and rec.cash_advance_id.wo_return_invoice_id.id == rec.id:
                    ca_id.write({'state': 'submit', 'wo_return_invoice_id': False, 'total_return': 0.0})

                if rec.cash_advance_id and rec.cash_advance_id.wo_reimburse_invoice_id.id == rec.id:
                    ca_id.write({'state': 'submit', 'wo_reimburse_invoice_id': False, 'total_reimburse': 0.0})

        return super(AccountInvoice, self).unlink()


class AccountInvoiceLine(models.Model):
    _inherit = 'account.move.line'

    cash_advance_transaction_id = fields.Many2one('cash.advance.transaction', 'CA Liquidation')
    cash_advance_id = fields.Many2one('cash.advance', 'Cash Advance')


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    def _prepare_default_reversal(self, move):
        res = super()._prepare_default_reversal(move)
        ca_id = self.move_id.cash_advance_id
       
        return res
