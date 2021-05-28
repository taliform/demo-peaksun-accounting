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


class Company(models.Model):
    _inherit = 'res.company'

    ATW_NOTIFICATION_TYPES = [
        ('disabled', 'Disabled'),
        ('user', 'User'),
        ('group', 'Group')
    ]

    logistics_vehicle_available_states = fields.Many2many('fleet.vehicle.state', string='Available Vehicle States',
                                                          help='Indicates all the vehicle states where vehicles are '
                                                               'considered as available for use.')
    logistics_default_origin = fields.Many2one('res.partner', 'Default Origin',
                                               default=lambda self: self.env.company.partner_id,
                                               help='Indicates the location to use when the record\'s (i.e. Trip Log) '
                                                    'origin is not explicitly found or available.')
    logistics_atw_notification_type = fields.Selection(ATW_NOTIFICATION_TYPES, 'ATW Notification', default='disabled',
                                                       help='Indicates the type of notification to send when an ATW '
                                                            'needs to be matched:\n'
                                                            '* Disabled: Notifications will not be sent.\n'
                                                            '* User: Specified user will be notified '
                                                            'via an Activity in the ATW record.\n'
                                                            '* Group: All users within the specified group will '
                                                            'receive a notification and link to the ATW record.')
    logistics_atw_user_id = fields.Many2one('res.users', 'ATW Notification User')
    logistics_atw_group_id = fields.Many2one('res.groups', 'ATW Notification Group')
    logistics_cement_uom_category_id = fields.Many2one('uom.category', 'UoM Category of Cement Products',
                                                       help='Indicates the UoM category of cement products to '
                                                            'facilitate weight conversions.')
    logistics_cement_weight_uom_id = fields.Many2one('uom.uom', 'Weight UoM',
                                                     help='Indicates the UoM used for weight logs. '
                                                          'Should be a UoM under the Uom Category of Cement Products.')
    logistics_cement_bag_uom_id = fields.Many2one('uom.uom', 'Default Bag UoM',
                                                  help='Indicates the default UoM used for bags. '
                                                       'Should be a UoM under the Uom Category of Cement Products.')
    logistics_toll_fee_product_id = fields.Many2one('product.product', 'Toll Fee Product',
                                                    help='Indicates the product used for Toll Fees.')
