# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Benjamin Cerdena Jr <benjamin@taliform.com>
#
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

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DeliveryOrder(models.Model):
    _inherit = 'logistics.delivery.order'

    def action_assign(self):
        self.ensure_one()
        view_id = self.env.ref('tf_peec_logistics.logistics_delivery_order_assign_view_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assign Delivery Unit'),
            'res_model': 'logistics.delivery.order.assign',
            'view_mode': 'form',
            'views': [[view_id, 'form']],
            'target': 'new',
            'context': {
                'default_delivery_order_id': self.id,
                'default_req_plant_ids': [self.cement_plant_id.id, self.batching_plant_id.id],
                'action': 'assign'
            }
        }
