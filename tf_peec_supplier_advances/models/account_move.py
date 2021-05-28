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
from odoo import models, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_switch_bill_into_refund_debit_note(self):
        if any(move.type not in ('in_invoice', 'out_invoice') for move in self):
            raise ValidationError(_("This action isn't available for this document."))

        for move in self:
            move.type = move.type.replace('invoice', 'refund')
            reversed_move = move._reverse_move_vals({}, False)
            new_invoice_line_ids = []
            for cmd, virtualid, line_vals in reversed_move['line_ids']:
                if not line_vals['exclude_from_invoice_tab']:
                    new_invoice_line_ids.append((0, 0, line_vals))
            if move.amount_total < 0:
                # Inverse all invoice_line_ids
                for cmd, virtualid, line_vals in new_invoice_line_ids:
                    line_vals.update({
                        'quantity': -line_vals['quantity'],
                        'amount_currency': -line_vals['amount_currency'],
                        'debit': line_vals['credit'],
                        'credit': line_vals['debit']
                    })
            move.write({'invoice_line_ids': [(5, 0, 0)], 'invoice_partner_bank_id': False})
            move.write({'invoice_line_ids': new_invoice_line_ids})






