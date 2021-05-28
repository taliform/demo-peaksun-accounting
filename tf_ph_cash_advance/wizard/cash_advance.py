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
from odoo.exceptions import ValidationError


class CashAdvanceCancel(models.TransientModel):
    _name = 'cash.advance.cancel'
    _description = 'Cancel Cash Advance'

    cash_advance_id = fields.Many2one('cash.advance', 'Cash Advance')

    def cancel_ca(self):
        CashAdvance = self.env['cash.advance']
        active_ids = self._context['active_ids']

        for active_id in active_ids:
            ca_id = CashAdvance.browse(active_id)
            invoice_id = ca_id.invoice_id

            # If Fund Requested and has draft invoice, the draft invoice will be automatically deleted and the CA still be in Fund Requested state
            # If validated, cancel the invoice. Then, the user may create new invoice and tag the CA reference
            if ca_id.state in ['confirm', 'open']:
                if invoice_id.state == 'draft':
                    invoice_id.with_context({'cancel_ca': True, 'force_delete': True}).unlink()
                elif invoice_id.state == 'posted' and invoice_id.invoice_payment_state == 'not_paid':
                    mode, view_id = self.env['ir.model.data'].get_object_reference('account',
                                                                                   'view_account_move_reversal')
                    if view_id:
                        context = self.sudo()._context.copy()
                        context.update(
                            {'default_display_name': 'Cancel' + ': ' + invoice_id.number,
                             'default_refund_method': 'cancel', 'active_ids': [invoice_id.id],
                             'active_id': [invoice_id.id]})
                        return {
                            'name': 'Cancel Invoice',
                            'view_mode': 'form',
                            'view_id': view_id,
                            'res_model': 'account.move.reversal',
                            'type': 'ir.actions.act_window',
                            'target': 'new',
                            'context': context
                        }

                # If Open state, the payment of the paid invoice should be cancelled first to be able to cancel the CA record
                elif invoice_id.state == 'posted' and invoice_id.invoice_payment_state != 'not_paid':
                    raise Warning(_(
                        'The payment record of %s should be cancelled first to cancel this CA record.') % invoice_id.number)

            if ca_id.cash_transaction_ids:
                for cat_id in ca_id.cash_transaction_ids: cat_id.write({'state': 'cancel'})
            ca_id.write({'state': 'cancel'})


class CashAdvanceReject(models.TransientModel):
    _name = 'cash.advance.reject'
    _description = 'Cancel CA'

    notes = fields.Text('Reason')

    def reject_ca(self):
        CashAdvance = self.env['cash.advance']
        active_ids = self._context['active_ids']

        for active_id in active_ids:
            ca_id = CashAdvance.browse(active_id)
            # CA Rejected
            if ca_id.state in ['draft', 'for_approval']:
                ca_id.ca_reject_reason = self.notes
                ca_id.change_state('rejected')
                ca_id.change_state('cancel')

            # Liquidation Rejected
            elif ca_id.state == 'liq_for_approval':
                ca_id.liq_reject_reason = self.notes
                ca_id.is_liq_approved = False
                for cat_id in ca_id.cash_transaction_ids:
                    cat_id.write({'state': 'draft'})
                if ca_id.ca_type == 'ca':
                    ca_id.change_state('rejected')
                    ca_id.change_state('open')
                elif ca_id.ca_type == 'dr':
                    ca_id.change_state('rejected')
                    ca_id.change_state('draft')


class CashAdvanceRevise(models.TransientModel):
    _name = 'cash.advance.revise'
    _description = 'Revise Cash Advance'

    cash_advance_id = fields.Many2one('cash.advance', 'Cash Advance')
    amount = fields.Monetary()
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.user.company_id.currency_id,
                                  required=True)

    def revise_ca(self):
        CashAdvance = self.env['cash.advance']
        active_ids = self._context['active_ids']

        for active_id in active_ids:
            ca_id = CashAdvance.browse(active_id)
            invoice_id = ca_id.invoice_id
            if ca_id.amount != invoice_id.amount_total:
                if self.amount != invoice_id.amount_total:
                    raise ValidationError(_('The amount should be equal to the %s total amount.') % invoice_id.number)
                else:
                    #
                    #                     # Basic Approval
                    #                     if self.env.user.company_id.ca_multiple_approval == 'basic':
                    #                         approver_id = self.env.user.company_id.basic_approver_id
                    #                         ca_id.activity_schedule('ss_ph_cash_advance_enterprise.mail_act_ca_liq_for_approval',
                    #                                             user_id=approver_id.id,
                    #                                             note=_("Approve <a href='#' data-oe-model='%s' data-oe-id='%d'>%s</a> for user <a href='#' data-oe-model='%s' data-oe-id='%s'>%s</a>") % (
                    #                                                 ca_id._name, ca_id.id, ca_id.name,
                    #                                                 ca_id.issued_to._name, ca_id.issued_to.id, ca_id.issued_to.name))
                    ca_id.write({'amount': self.amount})
                    ca_id.change_state('open')


class CashAdvanceValidate(models.TransientModel):
    _name = 'cash.advance.validate'
    _description = 'Validate Cash Advance'

    cash_advance_id = fields.Many2one('cash.advance', 'Cash Advance')
    account_date = fields.Date("Accounting Date")

    def action_confirm(self):
        self.cash_advance_id.action_validate(self.account_date)
