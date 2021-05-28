# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2021 Taliform Inc.
#
# Author: Ana Trajano <ana@taliform.com>
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
from odoo import models, api, fields


class LogExpense(models.Model):
    _inherit = 'logistics.log.expense'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Tags the order line if the added line is from Trip Expenses (Logistics)
        """
        records = super(LogExpense, self).create(vals_list)
        for rec in records:
            if rec.sale_line_id:
                if not rec.sale_line_id.is_do_trip_exp:
                    rec.sale_line_id.is_do_trip_exp = True
        return records

    def write(self, vals):
        """
        Tags the order line if the added line is from Trip Expenses (Logistics)
        """
        records = super(LogExpense, self).write(vals)
        for rec in self:
            if rec.sale_line_id:
                if not rec.sale_line_id.is_do_trip_exp:
                    rec.sale_line_id.is_do_trip_exp = True
        return records


class DeliveryOrder(models.Model):
    _inherit = 'logistics.delivery.order'

    is_report = fields.Boolean(help='Indicates if the delivery order is recorded in the Sales Cement/Hauling Report')
