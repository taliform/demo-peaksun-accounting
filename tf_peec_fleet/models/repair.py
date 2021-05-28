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


class RepairOrder(models.Model):
    _inherit = "repair.order"

    def action_repair_invoice_create(self):
        res = super(RepairOrder, self).action_repair_invoice_create()
        VehicleCost = self.env['fleet.vehicle.cost']
        sub_type_id = self.env.ref('fleet.type_service_service_8').id
        now = datetime.now()
        for rec in self:
            if rec.to_repair == 'vehicle':
                vehicle_cost_vals = {
                    'repair_order_id': rec.id,
                    'vehicle_id': rec.vehicle_id.id,
                    'cost_subtype_id': sub_type_id,
                    'amount': rec.amount_total,
                    'date': now,
                    'description': f'Repair Order: {rec.name}'
                }
                VehicleCost.create(vehicle_cost_vals)

        return res

