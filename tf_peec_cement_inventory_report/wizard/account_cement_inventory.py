# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Joshua <joshua@taliform.com>
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
from datetime import datetime, timedelta, date

_ATW_STATUS = [('withdrawn', 'Withdrawn but not Delivered'),
               ('delivered', 'Withdrawn and Delivered'),
               ('all', 'All Options')]


class AccountCementInventory(models.TransientModel):
    _name = 'account.cement.inventory'
    _description = 'Account Cement Inventory'

    date_from = fields.Date(string='From')
    date_to = fields.Date(string='To')
    atw_status = fields.Selection(_ATW_STATUS, string='ATW Status', default='withdrawn')
    atw_ids = fields.Many2many('logistics.atw', string='ATWs')

    def action_print_cement_inventory(self):
        # Get ATWs
        domain = [
            ('atw_date', '>=', self.date_from),
            ('atw_date', '<=', self.date_to),
            ('purchase_id', '!=', False),
            ('picking_id', '!=', False)
        ]
        if self.atw_status == 'withdrawn':
            domain.append(('is_delivered', '=', False))
        elif self.atw_status == 'delivered':
            domain.append(('is_delivered', '=', True))

        atw_ids = self.env['logistics.atw'].search(domain)
        self.atw_ids = atw_ids
        return self.env.ref('tf_peec_cement_inventory_report.peec_custom_report_cement_inventory').report_action(self)

