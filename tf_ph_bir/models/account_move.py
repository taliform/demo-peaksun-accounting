# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.

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


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"
    
    chk_2307 = fields.Boolean('Validated BIR 2307', default=False)
    wht_tax_amount = fields.Monetary('Withholding Tax Amount', compute='_compute_wht_tax_amount', store=True)

    @api.depends('tax_line_id')
    def _compute_wht_tax_amount(self):
        for move_line in self:
            if move_line.tax_line_id or move_line.tax_ids:
                wht_tax_amt = 0
                base_lines = move_line.move_id.line_ids.filtered(lambda line: move_line.tax_line_id in line.tax_ids)
                for line in base_lines:
                    wht_tax_amt += line.move_id.ewt
                move_line.wht_tax_amount = abs(wht_tax_amt)

                if move_line.tax_ids and not base_lines:
                    wht_tax_amt2 = 0
                    for line2 in move_line:
                        wht_tax_amt2 += line2.move_id.ewt
                    move_line.wht_tax_amount = abs(wht_tax_amt2)
            else:
                move_line.wht_tax_amount = 0

    @api.depends('move_id.line_ids', 'move_id.line_ids.tax_line_id', 'move_id.line_ids.debit', 'move_id.line_ids.credit')
    def _compute_tax_base_amount(self):
        for move_line in self:
            if move_line.tax_line_id or move_line.tax_ids:
                base_lines = move_line.move_id.line_ids.filtered(lambda line: move_line.tax_line_id in line.tax_ids)
                if move_line.move_id.type == 'in_refund':
                    move_line.tax_base_amount = sum(base_lines.mapped('balance'))
                if move_line.tax_ids and not base_lines:
                    move_line.tax_base_amount = abs(move_line.move_id.amount_untaxed)
                else:
                    move_line.tax_base_amount = abs(sum(base_lines.mapped('balance')))
            else:
                move_line.tax_base_amount = 0
