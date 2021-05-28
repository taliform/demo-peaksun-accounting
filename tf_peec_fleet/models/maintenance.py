# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Bamboo <martin@taliform.com>
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
from odoo import models
from odoo.exceptions import ValidationError
from odoo.tools import datetime


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    def action_create_repair_order(self):
        # Overwrite Function in Maintenance Request to include inventory location as installation location
        RepairOrder = self.env['repair.order']
        sequence_obj = self.env['ir.sequence']
        for rec in self:
            order_vals = {
                'name': sequence_obj.next_by_code('repair.order'),
                'maintenance_request_id': rec.id,
                'equipment_id': rec.equipment_id.id,
                'vehicle_id': rec.vehicle_id.id,
                'product_id': rec.product_id.id,
                'to_repair': rec.to_maintain,
                'state': 'draft',
                'installation_loc': rec.vehicle_id.inventory_location_id.id or False,
            }
            repair_order = RepairOrder.create(order_vals)

            # Open the repair order
            form_view_id = self.env.ref('repair.view_repair_order_form').id
            return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'repair.order',
                'res_id': repair_order.id,
                'views': [(form_view_id, 'form')],
                'type': 'ir.actions.act_window',
                'target': 'current',
            }
