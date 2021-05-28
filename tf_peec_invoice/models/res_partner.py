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
from datetime import datetime


class ResPartner(models.Model):
    _inherit = 'res.partner'

    avg_collection_days = fields.Float("Collection Days (Avg)", compute='_get_avg_collection_days')
    avg_overdue_days = fields.Float("Overdue Days (Avg)", compute='_get_avg_overdue_days')

    def _get_avg_collection_days(self):
        for rec in self:
            avg_days = 0.0
            invoice_ids = rec.invoice_ids.filtered_domain([
                ('type', '=', 'out_invoice'),
                ('invoice_payment_state', '=', 'paid'),
                ('cash_management_id', '=', False),
                ('cash_advance_id', '=', False)])
            if invoice_ids:
                avg_days = sum(invoice_ids.mapped('collection_days')) / len(invoice_ids)
            rec.avg_collection_days = avg_days

    def _get_avg_overdue_days(self):
        for rec in self:
            avg_days = 0.0
            invoice_ids = rec.invoice_ids.filtered_domain([
                ('type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('cash_management_id', '=', False),
                ('cash_advance_id', '=', False)])
            if invoice_ids:
                avg_days = sum(invoice_ids.mapped('overdue_days')) / len(invoice_ids)
            rec.avg_overdue_days = avg_days
