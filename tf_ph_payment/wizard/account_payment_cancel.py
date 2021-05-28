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
from odoo import models, fields
from odoo.tools.translate import _


class AccountPaymentCancel(models.TransientModel):
    _name = 'account.payment.cancel'
    _description = 'Account Payment Cancel'

    date = fields.Date(string='Reversal date', default=fields.Date.context_today, required=True)
    journal_id = fields.Many2one('account.journal', string='Use Specific Journal',
                                 help='If empty, uses the journal of the journal entry to be reversed.')
    cancel_reason = fields.Text('Reason')

    def _prepare_default_reversal(self, move):
        return {
            'ref': _('Reversal of: %s, %s') % (move.name, self.cancel_reason) \
                if self.cancel_reason else _('Reversal of: %s') % (move.name),
            'date': self.date or move.date,
            'invoice_date': move.is_invoice(include_receipts=True) and (self.date or move.date) or False,
            'journal_id': move.journal_id.id or self.journal_id and self.journal_id.id,
            'invoice_payment_term_id': None,
            'auto_post': True if self.date > fields.Date.context_today(self) else False,
            'invoice_user_id': move.invoice_user_id.id,
        }

    def cancel_payment(self):
        payments = self._context.get('active_ids', False)
        payments = self.env['account.payment'].browse(payments)

        AccountMoveLine = self.env['account.move.line']

        # Get move lines
        move_line_ids = AccountMoveLine.search([('payment_id', 'in', payments.ids)])

        # Get Service Vat move lines
        for invoice_id in payments.invoice_ids:
            for svat_id in invoice_id.service_vat_ids:
                move_line_id = AccountMoveLine.search([
                    ('move_id', '=', svat_id.id),
                    ('payment_id', 'in', payments.ids)
                ])
                if move_line_id not in move_line_ids:
                    move_line_ids += move_line_id
                    # Unlink invoice reference
                if move_line_id:
                    svat_id.vat_invoice_rel_id = False

        # Unreconcile move lines from invoice
        move_line_ids.remove_move_reconcile()

        # Remove invoice references
        payments.write({
            'state': 'cancelled',
            'invoice_ids': [(5, 0, 0)],
            'cancel_reason': self.cancel_reason
        })

        # Get the journal entry created for the payment
        moves = move_line_ids.mapped('move_id')

        # Create default values.
        default_values_list = []
        for move in moves:
            default_values_list.append(self._prepare_default_reversal(move))

        # Handle reverse method.
        if any([vals.get('auto_post', False) for vals in default_values_list]):
            new_moves = moves._reverse_moves(default_values_list)
        else:
            new_moves = moves._reverse_moves(default_values_list, cancel=True)

        # Create action.
        action = {
            'name': _('Reverse Moves'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
        }
        if len(new_moves) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': new_moves.id,
            })
        else:
            action.update({
                'view_mode': 'tree,form',
                'domain': [('id', 'in', new_moves.ids)],
            })

        return action
