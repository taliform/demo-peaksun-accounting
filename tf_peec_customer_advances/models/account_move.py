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


class AccountMove(models.Model):
    _inherit = 'account.move'

    customer_advance = fields.Boolean(string='Customer Advance', default=False)
    customer_total_advances = fields.Monetary(string="Total Advances", computed='_get_advance_amounts', readonly=True)
    customer_claimed_amount = fields.Monetary(string="Claimed Amount", computed='_get_advance_amounts', readonly=True)
    customer_unclaimed_balance = fields.Monetary(string="Unclaimed Balance", computed='_get_advance_amounts', readonly=True)


    @api.depends('amount_total', 'invoice_line_ids', 'invoice_outstanding_credits_debits_widget')
    def _get_advance_amounts(self):
        for rec in self:
            rec.customer_total_advances = rec.amount_total
            rec.customer_claimed_amount = rec.amount_total - rec.amount_residual
            rec.unclaimed_balance = rec.amount_residual




