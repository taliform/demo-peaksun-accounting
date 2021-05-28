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


class DeliveryOrderEndTrip(models.TransientModel):
    _name = 'logistics.delivery.order.end.trip'
    _description = 'Delivery Order End Trip'

    delivery_order_id = fields.Many2one('logistics.delivery.order', 'Delivery Order', required=True)
    delivery_unit_id = fields.Many2one('logistics.delivery.unit', 'Delivery Unit', required=True)
    trip_log_id = fields.Many2one('logistics.log.trip', 'Trip Log', required=True)
    odometer_reading = fields.Float('Odometer Reading', required=True)
    is_manual_date = fields.Boolean('Manual Date')
    arrival_date = fields.Datetime('Arrival Date')
    manual_reason = fields.Text('Reason for Manual Time Entry')

    @api.onchange('is_manual_date')
    def _onchange_is_manual_date(self):
        self.ensure_one()
        if not self.is_manual_date:
            self.arrival_date = False
            self.manual_reason = False

    def action_end_trip(self):
        self.ensure_one()

        delivery_order = self.delivery_order_id
        trip_log = self.trip_log_id
        vehicle = self.delivery_unit_id.tractor_head_id

        state = False
        end_trip_type = self._context.get('end_trip_type')
        if end_trip_type == 'cp':
            state = 'cp'
        elif end_trip_type == 'bp':
            state = 'bp'
        elif end_trip_type == 'garage' and delivery_order.validated_by:
            state = 'closed'

        arrival_date = self.arrival_date
        if not arrival_date:
            arrival_date = fields.Datetime.now()

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

        if trip_log.state != 'in_progress':
            raise ValidationError(_('The trip log has already ended prior to your action. Please refresh record.'))

        trip_log.write({
            'arrival_date': arrival_date,
            'end_odometer_id': odometer_reading.id,
            'state': 'done',
        })

        delivery_unit_vals = {
            'location_id': trip_log.destination_id.id
        }

        delivery_order_vals = {
            'trip_log_id': False
        }

        if state:
            delivery_order_vals['state'] = state

        if end_trip_type == 'garage':
            delivery_order_vals['return_date'] = arrival_date
            delivery_order_vals['is_returning'] = False
            if delivery_order.validated_by:
                delivery_unit_vals['delivery_order_id'] = False

        delivery_order.write(delivery_order_vals)
        self.delivery_unit_id.write(delivery_unit_vals)
