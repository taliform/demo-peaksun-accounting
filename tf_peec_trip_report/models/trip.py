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
from odoo import api, models, fields

_LOCAL = 'local'
_AREA1 = 'area1'
_AREA2 = 'area2'
_AREA3 = 'area3'

_AREAS = [
    (_LOCAL, 'Local'),
    (_AREA1, 'Area 1'),
    (_AREA2, 'Area 2'),
    (_AREA3, 'Area 3')
]


class TripReport(models.Model):
    _name = 'logistics.trip.report'
    _description = 'Trip Report'

    delivery_order_id = fields.Many2one('logistics.delivery.order', 'Delivery Order')
    delivery_date = fields.Date('Delivery Date')
    employee_id = fields.Many2one('hr.employee', 'Employee')
    job_id = fields.Many2one('hr.job', 'Position')
    volume = fields.Float('Volume')
    area = fields.Selection(_AREAS)
    product_id = fields.Many2one('product.product', 'Product')
    destination_id = fields.Many2one('res.partner', 'Destination')
    tutok = fields.Float('Tutok (HH:MM)')
    training_pay = fields.Float('Training Pay')
    multiplier_rate = fields.Monetary('Piece Rate')
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    pro_rate = fields.Float()

    @api.model
    def get_area(self, distance):
        if distance >= 181:
            area = _AREA3
        elif distance >= 141:
            area = _AREA2
        elif distance >= 101:
            area = _AREA1
        else:
            area = _LOCAL
        return area

    @api.model
    def get_pro_rate(self, du_list, employee):
        if (len(du_list)) == 1:
            pro_rate = 1
        else:
            if (employee in du_list[-1].helper_ids) or (employee in du_list[-1].driver_ids):
                pro_rate = .65
            else:
                pro_rate = .35

        return pro_rate

    @api.model
    def get_multiplier_rate(self, area, contract_id):
        if area == _AREA3:
            rate = contract_id.area3_rate
        elif area == _AREA2:
            rate = contract_id.area2_rate
        elif area == _AREA1:
            rate = contract_id.area1_rate
        else:
            rate = contract_id.local_rate
        return rate

    @api.model
    def get_tutok(self, trips, batching_plant):
        start_date = False
        end_date = False
        tutok_pay = 0.0
        for trip in trips:
            if trip.destination_id == batching_plant:
                start_date = trip.arrival_date
            elif trip.origin_id == batching_plant:
                end_date = trip.departure_date

        if start_date and end_date:
            diff = end_date - start_date
            tutok_pay = float(diff.days) * 24 + (float(diff.seconds) / 3600)
        return tutok_pay

    @api.model
    def generate_trip_report(self):
        report_vals = []
        # Update existing trip reports
        for rec in self.env['logistics.trip.report'].search([]):
            do_id = rec.delivery_order_id
            rec.delivery_date = do_id.departure_date
            rec.tutok = self.get_tutok(do_id.trip_ids, do_id.batching_plant_id)
            if not rec.multiplier_rate:
                rec.multiplier_rate = self.get_multiplier_rate(rec.area, rec.employee_id.contract_id)
        # Retrieve all finished Delivery Orders
        DeliveryOrder = self.env['logistics.delivery.order']
        delivery_orders = DeliveryOrder.search([('state', '=', 'closed'), ('is_reported', '=', False)])
        for do in delivery_orders:
            # Get list of employees from Trip Logs Delivery Unit
            du_list = []
            new_du_list = []
            employees = []
            for trip_id in do.trip_ids:
                du_list.append(trip_id.delivery_unit_id)
            for du_id in du_list:
                if du_id not in new_du_list:
                    new_du_list.append(du_id)
            for du_id in new_du_list:
                employees += du_id.driver_ids + du_id.helper_ids

            if not do.is_multiple_sale:
                # Get Volume
                volume = do.atw_id.weight_log_id.bags_qty
                # Get Area
                distance = sum([trip.distance_travelled for trip in do.trip_ids])
                area = self.get_area(distance)
                # Get tutok (time spent in batching plant)
                tutok = self.get_tutok(do.trip_ids, do.batching_plant_id)

                for employee in employees:
                    if employee.contract_id:
                        rate = self.get_multiplier_rate(area, employee.contract_id)
                        pro_rate = self.get_pro_rate(new_du_list, employee)
                        report_vals.append({
                            'delivery_order_id': do.id,
                            'delivery_date': fields.Date.to_date(do.departure_date),
                            'employee_id': employee.id,
                            'job_id': employee.contract_id.position_id.id,
                            'volume': volume,
                            'area': area,
                            'product_id': do.product_id.id,
                            'destination_id': do.batching_plant_id.id,
                            'tutok': tutok,
                            'multiplier_rate': rate,
                            'pro_rate': pro_rate
                            # 'training_pay': training_pay
                        })
            else:
                for allocation in do.allocation_ids:
                    # Get Volume
                    volume = do.atw_id.weight_log_id.bags_qty
                    # Get Area
                    area = 'area1'
                    # Get Destination
                    destination_id = allocation.batching_plant_id.id

                    for employee in employees:
                        if employee.contract_id:
                            pro_rate = self.get_pro_rate(new_du_list, employee)
                            rate = self.get_multiplier_rate(area, employee.contract_id)
                            report_vals.append({
                                'delivery_order_id': do.id,
                                'delivery_date': fields.Date.to_date(do.departure_date),
                                'employee_id': employee.id,
                                'job_id': employee.contract_id.position_id.id,
                                'volume': volume,
                                'area': area,
                                'product_id': do.product_id.id,
                                'destination_id': destination_id,
                                'multiplier_rate': rate,
                                'pro_rate': pro_rate
                            })

        # Tag delivery orders as reported to skip in future cron jobs
        delivery_orders.write({'is_reported': True})

        # Create report lines
        self.create(report_vals)
