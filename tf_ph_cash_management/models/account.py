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
from odoo.exceptions import ValidationError
from odoo import models, fields, api, _
from lxml import etree


class AccountMove(models.Model):
    _inherit = 'account.move'

    cash_replenishment_id = fields.Many2one('cash.replenishment', string='Cash Replenishment', ondelete='cascade')
    cash_management_id = fields.Many2one('cash.management', string='Cash Management', ondelete='cascade')
    fund_id = fields.Many2one('request.fund', string='Request Fund', copy=False)
    is_repl_released = fields.Boolean(string='Replenishment Released', copy=False)
    is_replenishment = fields.Boolean(string='Replenishment', copy=False)
    received = fields.Boolean(string='Received?', copy=False)
    is_fund = fields.Boolean(string='Fund', copy=False)
    for_closing = fields.Boolean(copy=False)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        '''
        @note: Hides wizards not related to CM and hides Edit button if the current user is CM Custodian only
        '''
        res = super(AccountMove, self).fields_view_get(view_id, view_type, toolbar=toolbar, submenu=submenu)

        if 'cm_invoice' in self._context.keys():
            res['toolbar'] = {'print': [], 'action': [], 'relate': []}

        user_id = self.env.user
        is_custodian = user_id.has_group('tf_ph_cash_management.group_cash_management_manager')
        is_billing = user_id.has_group('account.group_account_invoice')
        doc = etree.XML(res['arch'])
        if is_custodian and not is_billing:
            for form in doc.xpath("//" + view_type):
                form.attrib['create'] = 'false'
                form.attrib['delete'] = 'false'
                form.attrib['edit'] = 'false'

            res['arch'] = etree.tostring(doc)
        return res

    def write(self, vals):
        '''
        @note: Notification if the requested fund amount changed.
        '''
        res = super(AccountMove, self).write(vals)
        for rec in self:
            if vals.get('invoice_payment_state', False):
                if vals['invoice_payment_state'] == 'paid':
                    # Request Fund
                    if rec.fund_id:
                        fund_id = rec.fund_id
                        if rec.amount_total != fund_id.amount:
                            # Send notification
                            msg = _(
                                'The requested fund amount has been changed. The new requested fund amount of %s is %s.') % (
                                  rec.number, str(rec.amount_total))
                            fund_id.cash_management_id.message_post(body=msg)

                    # Automatically close the CM
                    if rec.for_closing and rec.cash_management_id:
                        cm_id = rec.cash_management_id
                        cm_id.write({'state': 'close'})

        return res

    def unlink(self):
        cash_replenishment_id = False
        for rec in self:
            if rec.state == 'draft':
                if rec.cash_management_id and not rec.is_fund:
                    raise ValidationError(_("You cannot delete invoices created from CM Transactions."))

                if rec.cash_management_id and rec.is_fund:
                    # Send notification to the CM Custodian
                    current_user = self.env.user.partner_id
                    cm_id = rec.cash_management_id
                    partner_id = cm_id.create_uid.partner_id
                    partners = [partner_id.id]
                    msg_vals = {}
                    message = """
                        <p>Hi %s,</p>
                        <p>The draft CM Invoice for <b>%s</b> has been deleted by %s. You are allowed to request fund again.</p> 
                        <p>Thank you.</p>
                    """
                    msg_vals['body'] = message % (partner_id.name, cm_id.name, current_user.name)
                    msg_vals['partner_ids'] = partners

                    cm_id.message_post(type='notification', **msg_vals)

                if rec.invoice_line_ids:
                    for line in rec.invoice_line_ids:
                        if line.cash_transaction_id:
                            line.cash_transaction_id.write({'state': 'open'})

                if rec.cash_replenishment_id and not cash_replenishment_id.replenishment_line_ids:
                    cash_replenishment_id.unlink()
            else:
                raise ValidationError(_("You may only delete an invoice record in 'Draft' state."))

            res = super(AccountMove, self).unlink()
        return res


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    #Former Account Invoice Line

    cash_transaction_id = fields.Many2one('cash.transaction', string='Cash Transaction')


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    def reverse_moves(self):
        res = super(AccountMoveReversal, self).reverse_moves()
        move_obj = self.env['account.move']

        if 'domain' in res:
            orig_invoice = cm_id = origin = is_cancel = False

            if self._context.get('active_id', False):
                active_id = self._context['active_id']
                orig_invoice = move_obj.browse(active_id)
                if orig_invoice.cash_management_id:
                    cm_id = orig_invoice.cash_management_id
                    origin = orig_invoice.origin
                    orig_invoice.write({'cash_management_id': False,
                                        'is_fund': False})

                    if self.refund_method == 'cancel':
                        # Send notification to the CM Custodian
                        current_user = self.env.user.partner_id
                        partner_id = cm_id.create_uid.partner_id
                        partners = [partner_id.id]
                        msg_vals = {}
                        message = """
                            <p>Hi %s,</p>
                            <p>The CM Invoice for <b>%s</b> has been cancelled by %s. You are allowed to request fund again.</p> 
                            <p>CM Invoice: %s</p>
                            <p>Thank you.</p>
                        """
                        msg_vals['body'] = message % (
                        partner_id.name, cm_id.name, current_user.name, orig_invoice.number)
                        msg_vals['partner_ids'] = partners

                        cm_id.message_post(type='notification', **msg_vals)
                        is_cancel = True

            new_ids = []
            if 'domain' in res:
                for domain in res['domain']:
                    if len(domain) == 3:
                        if domain[0] == 'id':
                            new_ids = domain[2]

            for inv_id in new_ids:
                new_invoice = self.env['account.move'].browse(inv_id)

                # Only copy the CM details if the orig_invoice is modified and not cancelled
                if self.refund_method == 'modify':
                    if new_invoice and cm_id and orig_invoice and not is_cancel:
                        # Send notification to the CM Custodian
                        current_user = self.env.user.partner_id
                        partner_id = cm_id.create_uid.partner_id
                        partners = [partner_id.id]
                        msg_vals = {}
                        message = """
                            <p>Hi %s,</p>
                            <p>The CM Invoice for <b>%s</b> has been cancelled and replaced by new draft invoice.</p> 
                            <p>Old CM Invoice: %s</p>
                            <p>Thank you.</p>
                        """
                        msg_vals['body'] = message % (partner_id.name, cm_id.name, orig_invoice.number)
                        msg_vals['partner_ids'] = partners

                        cm_id.message_post(type='notification', **msg_vals)
                        cm_id.write({'invoice_ids': [(4, inv_id)]})
                        new_invoice.write({'cash_management_id': cm_id.id,
                                           'origin': origin,
                                           'is_fund': True})

        return res
