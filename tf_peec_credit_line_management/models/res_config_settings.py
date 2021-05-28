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

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    credit_line = fields.Boolean(config_parameter='account_overdue_receivables.credit_line', default=False, help='Indicate to activate the functions for credit line management for credit limit and overdue receivables.')
    max_percentage = fields.Float(config_parameter='account_overdue_receivables.max_percentage', string='Max Percentage',
                                  help='Indicate the maximum percentage of the customer’s overdue invoices amount to the total unpaid invoices amount that will trigger an exception action.')

    def write(self, vals):
        res = super(ResConfigSettings, self).write(vals)
        print(vals)
        return res
