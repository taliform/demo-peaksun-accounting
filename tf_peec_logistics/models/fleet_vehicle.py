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

from odoo import fields, models


class FleetVehicleLogFuel(models.Model):
    _inherit = 'fleet.vehicle.log.fuel'

    trip_log_id = fields.Many2one('logistics.log.trip', 'Trip Log')
    target_sucf = fields.Float(related='trip_log_id.target_sucf',
                               help="Indicates the target SUCF, based on the Trip Log.")
    actual_sucf = fields.Float(related='trip_log_id.actual_sucf',
                               help="Indicates the actual SUCF, based on the distance travelled and amount fueled.")


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    delivery_unit_id = fields.Many2one('logistics.delivery.unit', 'Delivery Unit',
                                       help='Current Delivery Unit the vehicle is assigned to')
