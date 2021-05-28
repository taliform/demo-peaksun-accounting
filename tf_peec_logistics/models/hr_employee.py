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
import werkzeug

from odoo import api, fields, models, _

_DH_AVAILABILITY = [
    ('available', 'Available'),
    ('leave', 'On Leave'),
    ('meeting', 'In Meeting'),
    ('unavailable', 'Unavailable')
]


class Employee(models.Model):
    _inherit = 'hr.employee'

    delivery_unit_id = fields.Many2one('logistics.delivery.unit', 'Delivery Unit',
                                       help='Current Delivery Unit the employee is assigned to')
    dh_availability = fields.Selection(_DH_AVAILABILITY, 'D/H Availability',
                                       default='unavailable', index=True)
    delivery_unit_state = fields.Selection(related='delivery_unit_id.delivery_order_state',
                                           string='Delivery Order Status')


class EmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    delivery_unit_id = fields.Many2one('logistics.delivery.unit', 'Delivery Unit')
    dh_availability = fields.Selection(_DH_AVAILABILITY, 'D/H Availability')
