# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2021 Taliform Inc.
#
# Author: Ana Trajano <ana@taliform.com>
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
from odoo import fields, models, _


class SaleRateComputation(models.TransientModel):
    _name = 'sale.rate.computation'
    _description = "Rate Computation (Cement)"

    rate_table_id = fields.Many2one('sale.rate', 'Rate Table', ondelete='cascade')
    rate_id = fields.Many2one('sale.rate.rate', 'Rate')
    km = fields.Float('Km')

    def compute_rate(self):
        self.ensure_one()
        active_ids = self._context['active_ids']

        if self.rate_table_id:
            rt_id = self.rate_table_id

            # Call compute_rate in Rate Table object
            rt_id.km_comp = self.km
            rt_id.rate_id_comp = self.rate_id
            computed_rate = rt_id.compute_rate()

            # Pass value to Sales Agreement Line
            if self._context.get('active_model', False):
                active_model = self._context['active_model']
                if active_model == 'sale.agreement.line':
                    for active_id in active_ids:
                        agmt_line_id = self.env['sale.agreement.line'].browse(active_id)
                        sale_price = agmt_line_id.product_id.lst_price
                        agmt_line_id.rate_computed = sale_price + computed_rate['based_on_rate']
                        # Update Unit Price
                        agmt_line_id.price_unit = agmt_line_id.rate_computed




