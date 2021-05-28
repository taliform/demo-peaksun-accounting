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
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FleetVehicleDriveConfig(models.Model):
    _name = "fleet.vehicle.drive.configuration"
    _description = "Drive Configuration for Fleet Vehicles"

    _sql_constraints = [('name_unique', 'unique(name)', 'Drive configuration already exists.')]

    name = fields.Char("Name", required=True, copy=False, help="Indicates the drive configuration name.")


class FleetVehicleSuspensionType(models.Model):
    _name = "fleet.vehicle.suspension.type"
    _description = "Suspension Type for Fleet Vehicles"

    _sql_constraints = [('name_unique', 'unique(name)', 'Suspension Type already exists.')]

    name = fields.Char("Name", required=True, copy=False, help="Indicates the suspension type.")


class FleetVehicleTank(models.Model):
    _name = "fleet.vehicle.tank"
    _description = "Vehicle Tank for Fleet Vehicles"

    _sql_constraints = [('name_unique', 'unique(name)', 'Tank Name already exists.')]

    name = fields.Char("Name", required=True, copy=False, help="Indicated the name of the tank.")
    shape = fields.Selection([("cube", "Cube"), ("cylinder", "Cylinder")], "Shape",
                             default='cube', help="Indicates the shape of the tank")
    height = fields.Float("Height", help="Indicates the height of the tank.")
    length = fields.Float("Length", help="Indicates the length of the tank.")
    width = fields.Float("Width", help="Indicates the width of the tank.")
    diameter = fields.Float("Diameter", help="Indicates the diameter of the tank.")

    @api.onchange('shape')
    def onchange_shape(self):
        for rec in self:
            shape = rec.shape
            if shape == 'cube':
                rec.diameter = False
            elif shape == 'cylinder':
                rec.height = False
                rec.length = False
                rec.width = False


class FleetCard(models.Model):
    _name = "fleet.card"
    _description = "Fleet Card"

    _sql_constraints = [('name_unique', 'unique(name)', 'Fleet card number already exists.')]

    name = fields.Char("Fleet Card Number", required=True, copy=False, help="Indicates the fleet card number.")


class FleetLocation(models.Model):
    _name = "fleet.location"
    _description = "Vehicle Locations"

    _sql_constraints = [('name_unique', 'unique(name)', 'Fleet location name already exists.')]

    name = fields.Char("Location Name", required=True, copy=False, help="Indicates the fleet location name.")
    company_id = fields.Many2one('res.company', "Company", default=lambda self: self.env.user.company_id.id,
                                 help="Indicates the company the location is under (in case of a multi company setup).")



