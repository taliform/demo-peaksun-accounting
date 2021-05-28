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

_ATW_STATUS = [('withdrawn', 'Withdrawn'),
               ('delivered', 'Delivered'),
               ('invoiced', 'Invoiced')]

class AccountCostSales(models.TransientModel):
    _name = 'account.cost.sales'
    _description = 'Account Cost of Sales'

    date_from = fields.Date(string='From')
    date_to = fields.Date(string='To')
    atw_status = fields.Selection(_ATW_STATUS, string='ATW Status', default='withdrawn')
    atw_ids = fields.Many2many('logistics.atw', string='ATWs')

    def action_print_cost_of_sales(self):
        # Get ATWs
        atw_domain = [
            ('atw_date', '>=', self.date_from),
            ('atw_date', '<=', self.date_to),
            ('purchase_id', '!=', False),
            ('sale_id', '!=', False),
            ('picking_id', '!=', False)
        ]
        if self.atw_status == 'withdrawn':
            atw_domain.append(('is_delivered', '=', False))
        elif self.atw_status == 'delivered':
            atw_domain.append(('is_delivered', '=', True))
        self.atw_ids = self.env['logistics.atw'].search(atw_domain)

        return self.env.ref('tf_peec_cost_sales_report.peec_custom_report_cost_sales').report_action(self)

