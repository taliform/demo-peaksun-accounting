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
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, RedirectWarning


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    preventive_maintenance_distance = fields.Float('Preventive Maintenance Distance')
    est_next_preventive_maintenance_distance = fields.Float('Estimated Next Preventive Maintenance Distance', compute='_get_est_prev_maintenance_distance', store=True)
    vehicle_code = fields.One2many('fleet.vehicle.code', 'vehicle', 'Vehicle Code')

    @api.depends('preventive_maintenance_distance')
    def _get_est_prev_maintenance_distance(self):
        for rec in self:
            rec.est_next_preventive_maintenance_distance = rec.preventive_maintenance_distance + rec.odometer

class FleetVehicleCode(models.Model):
    _name = "fleet.vehicle.code"
    _description = "Fleet Vehicle Code"

    asset_type = fields.Many2one('vmrs.code', string='Asset Type')
    equipment_voc = fields.Many2one('vmrs.code', string='Equipment Vocation')
    body_style_config = fields.Many2one('vmrs.code', string='Body Style Configuration')
    vehicle = fields.Many2one('fleet.vehicle', string='Vehicle')


class FleetVehicleOdometer(models.Model):
    _inherit = 'fleet.vehicle.odometer'

    @api.model
    def create(self, vals):
        res = super(FleetVehicleOdometer, self).create(vals)
        new_reading = vals['value']
        est_nxt_preventive_maintenance = res.vehicle_id.est_next_preventive_maintenance_distance
        # Only create PM if PM distance is greater than 0, otherwise treat it as disabled
        if new_reading > est_nxt_preventive_maintenance and res.vehicle_id.preventive_maintenance_distance > 0:
            res.generate_preventive_maintenance(vals['vehicle_id'])
        
        return res

    def generate_preventive_maintenance(self, vehicle_id):
        MaintenanceRequest = self.env['maintenance.request']
        sequence_obj = self.env['ir.sequence']
        preventive_maintenance_requests = MaintenanceRequest.search([('vehicle_id', '=', vehicle_id),
                                                                     ('maintenance_type', '=', 'preventive'),
                                                                     ('can_create_repair_order', '=', True)
                                                                    ])
        if preventive_maintenance_requests:
            raise ValidationError('There is an existing preventive maintenance request for this vehicle. Please follow up.')

        MaintenanceRequest.create({
            'maintenance_type': 'preventive',
            'to_maintain': 'vehicle',
            'vehicle_id': vehicle_id,
            'name': sequence_obj.next_by_code('maintenance.request')
        })








