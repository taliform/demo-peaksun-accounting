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

    total_discount = fields.Monetary(string='Less Discount', compute="_get_total_discount", store=True)
    invoice_terms_conditions = fields.Text('Terms and Conditions',
                                           default=lambda self:
                                           self.env.company.invoice_terms
                                           or self.env['ir.config_parameter']
                                           .sudo().get_param('account.use_invoice_terms') or '')

    @api.depends('invoice_line_ids')
    def _get_total_discount(self):
        for rec in self:
            rec.total_discount = 0
            invoice_total_discount = 0
            for line in rec.invoice_line_ids:
                total_discount = line.price_unit - (line.price_unit * (1 - (line.discount / 100.0)))
                invoice_total_discount += total_discount
            rec.total_discount = invoice_total_discount
