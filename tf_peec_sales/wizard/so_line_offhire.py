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
from odoo import fields, models, api, _
from odoo.exceptions import UserError


class SaleOrderLineOffhire(models.TransientModel):
    _name = 'sale.line.offhire'
    _description = "Sales Order Line Offhire"

    def add_to_so_line(self):
        active_ids = self._context.get('active_ids')
        offhire_comp_ids = self.env['sale.offhire']
        so_ids = []

        if active_ids:
            offhire_ids = self.env['sale.offhire'].browse(active_ids)

            if offhire_ids:
                # Separate per Sales Order
                # Add checking
                for offhire_id in offhire_ids.filtered(lambda l: not l.waive and not l.added):
                    if offhire_id.so_line_id:
                        raise UserError(_('Some selected records are already added to the sales order line.'))
                    else:
                        offhire_comp_ids += offhire_id
                        if offhire_id.so_id not in so_ids:
                            so_ids.append(offhire_id.so_id)

                # Check if the Quantity is greater than zero
                total_quantity = self.comp_quantity(offhire_comp_ids)

                if total_quantity > 0.0:
                    # Create Offhire SO Line
                    if so_ids:
                        for so_id in so_ids:
                            so_id.so_line_offhire_ids = False
                            offhire_lst_ids = self.env['sale.offhire']
                            for offhire_id in offhire_comp_ids.filtered(lambda l: l.so_id == so_id):
                                so_id.so_line_offhire_ids += offhire_id
                                if offhire_id not in offhire_lst_ids:
                                    offhire_lst_ids += offhire_id

                            product_qty = self.comp_quantity(offhire_lst_ids)
                            price_unit = sum(offhire_lst_ids.mapped('offhire_rate'))

                            # Create SO Line if quantity is greater than 0
                            if product_qty > 0.0:
                                so_id.create_so_line_offhire_ids(offhire_lst_ids, product_qty, price_unit)

    def comp_quantity(self, offhire_ids):
        """
        :param offhire_ids: List of offhire record to be computed
        :return: total quantity to be added in the so line
        """
        # Quantity = sum(Later Hours) + sum(Missing Hours) - sum(Maintenance Privilege)
        sum_lh_hrs = sum_mh_hrs = sum_mp_hrs = total_quantity = 0.0
        if offhire_ids:
            sum_lh_hrs = sum(offhire_ids.mapped('lt_hrs'))
            sum_mh_hrs = sum(offhire_ids.mapped('miss_hrs'))
            sum_mp_hrs = sum(offhire_ids.mapped('mnt_privilege'))

        total_quantity = (sum_lh_hrs + sum_mh_hrs) - sum_mp_hrs
        return total_quantity
