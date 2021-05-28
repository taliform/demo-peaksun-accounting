# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Allen Guarnes <allen@taliform.com>
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
from odoo.exceptions import ValidationError


class DeliveryOrderAssign(models.TransientModel):
    _name = 'logistics.delivery.order.assign'
    _description = 'Delivery Order Assign'

    delivery_order_id = fields.Many2one('logistics.delivery.order', 'Delivery Order')
    delivery_unit_id = fields.Many2one('logistics.delivery.unit', 'Delivery Unit')

    def action_assign(self):
        self.ensure_one()
        if self.delivery_unit_id:
            if self.delivery_order_id.delivery_unit_id:
                self.delivery_order_id.delivery_unit_id.write({'delivery_order_id': False})

            if self.delivery_unit_id.delivery_order_id:
                raise ValidationError(_('The selected Delivery Unit currently has a Delivery Order assigned to it. '
                                        'Please re-open the wizard to get the latest available Delivery Units.'))

            if self._context.get('action', False) == 'assign':
                self.delivery_order_id.write({
                    'delivery_unit_id': self.delivery_unit_id.id,
                    'state': 'assigned'
                })
            else:
                self.delivery_order_id.delivery_unit_id = self.delivery_unit_id

            self.delivery_unit_id.write({
                'delivery_order_id': self.delivery_order_id.id
            })
