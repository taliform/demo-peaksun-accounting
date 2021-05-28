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
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DeliveryOrderStartTrip(models.TransientModel):
    _name = 'logistics.delivery.order.start.trip'
    _description = 'Delivery Order Start Trip'

    delivery_order_id = fields.Many2one('logistics.delivery.order', 'Delivery Order', required=True)
    delivery_unit_id = fields.Many2one('logistics.delivery.unit', 'Delivery Unit', required=True)
    is_inspection_done = fields.Boolean('Inspection Done', required=True)
    odometer_reading = fields.Float('Odometer Reading', required=True)
    is_manual_date = fields.Boolean('Manual Date')
    departure_date = fields.Datetime('Departure Date')
    manual_reason = fields.Text('Reason for Manual Time Entry')

    @api.onchange('is_manual_date')
    def _onchange_is_manual_date(self):
        self.ensure_one()
        if not self.is_manual_date:
            self.departure_date = False
            self.manual_reason = False

    def _get_origin(self):
        trip_log = self.env['logistics.log.trip'].search([
            ('delivery_unit_id', '=', self.delivery_unit_id.id),
            ('state', '=', 'done')
        ], order='arrival_date desc', limit=1)
        if trip_log and trip_log.destination_id:
            return trip_log.destination_id
        else:
            return self.env.company.logistics_default_origin

    def action_start_trip(self):
        self.ensure_one()

        if not self.is_inspection_done:
            raise ValidationError(_('Cannot start trip without declaring inspection as done.'))

        delivery_order = self.delivery_order_id
        vehicle = self.delivery_unit_id.tractor_head_id

        origin = self._get_origin()
        if not origin:
            raise ValidationError(_('Cannot determine Origin for Trip Log.'))

        state = False
        start_trip_type = self._context.get('start_trip_type')
        print(start_trip_type)
        is_loaded = False
        if start_trip_type == 'cp':
            destination = delivery_order.cement_plant_id
            state = 'in_transit_cp'
        elif start_trip_type == 'bp':
            destination = delivery_order.batching_plant_id
            state = 'in_transit_bp'
        else:
            destination = delivery_order.garage_id

        departure_date = self.departure_date
        if not departure_date:
            departure_date = fields.Datetime.now()

        # Get Last Weight Log
        last_weight_log = self.env['logistics.log.weight'].search([
            ('delivery_order_id', '=', delivery_order.id)
        ], order='weighing_date desc', limit=1)
        if last_weight_log and last_weight_log.bags_qty > 0:
            is_loaded = True

        if self.delivery_unit_id.driver_ids:
            driver_id = self.delivery_unit_id.driver_ids[0].id
        else:
            driver_id = False

        odometer_reading = self.env['fleet.vehicle.odometer'].create({
            'vehicle_id': vehicle.id,
            'driver_id': driver_id,
            'value': self.odometer_reading,
            'date': fields.Date.context_today(self)
        })

        trip_log = self.env['logistics.log.trip'].create({
            'delivery_order_id': delivery_order.id,
            'delivery_unit_id': self.delivery_unit_id.id,
            'origin_id': origin.id,
            'destination_id': destination.id,
            'is_inspection_done': self.is_inspection_done,
            'departure_date': departure_date,
            'start_odometer_id': odometer_reading.id,
            'state': 'in_progress',
            'is_loaded': is_loaded
        })

        delivery_order_vals = {
            'trip_log_id': trip_log.id,
        }
        if state:
            delivery_order_vals['state'] = state
        if not delivery_order.departure_date:
            delivery_order_vals['departure_date'] = departure_date
        if start_trip_type == 'garage':
            delivery_order_vals['is_returning'] = True
        delivery_order.write(delivery_order_vals)
