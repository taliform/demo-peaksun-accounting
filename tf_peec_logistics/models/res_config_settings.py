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
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    logistics_vehicle_available_states = fields.Many2many(related='company_id.logistics_vehicle_available_states',
                                                          readonly=False)
    logistics_default_origin = fields.Many2one(related='company_id.logistics_default_origin',
                                               readonly=False)
    logistics_atw_notification_type = fields.Selection(related='company_id.logistics_atw_notification_type',
                                                       readonly=False)
    logistics_atw_user_id = fields.Many2one(related='company_id.logistics_atw_user_id', readonly=False)
    logistics_atw_group_id = fields.Many2one(related='company_id.logistics_atw_group_id', readonly=False)
    logistics_cement_uom_category_id = fields.Many2one(related='company_id.logistics_cement_uom_category_id',
                                                       readonly=False)
    logistics_cement_weight_uom_id = fields.Many2one(related='company_id.logistics_cement_weight_uom_id',
                                                     readonly=False)
    logistics_cement_bag_uom_id = fields.Many2one(related='company_id.logistics_cement_bag_uom_id', readonly=False)
    logistics_toll_fee_product_id = fields.Many2one(related='company_id.logistics_toll_fee_product_id', readonly=False)
