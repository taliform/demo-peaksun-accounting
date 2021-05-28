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


class AccountMove(models.Model):
    _inherit = 'account.move'

    counter_date = fields.Date(string='Counter Date', track_visibility='onchange', copy=False,
                               help="Indicate the date that the invoice was countered/received by the customer.")
    collection_days = fields.Float("Collection Days", compute='_get_collection_days', store=True, copy=False,
                                   help="Number of days between the counter date and completion of payment.")
    overdue_days = fields.Float("Days Overdue", compute='_get_days_overdue',
                                help="Number of days between the due date and completion of payment.")
    city = fields.Char(related='partner_id.city', store=True)

    def post(self):
        self.write({'counter_date': fields.Date.context_today(self)})
        res = super(AccountMove, self).post()
        return res

    @api.depends('payment_date', 'counter_date')
    def _get_collection_days(self):
        for rec in self:
            collection_days = 0.0
            if rec.payment_date and rec.counter_date:
                collection_days = (rec.payment_date - rec.counter_date).days
            rec.collection_days = collection_days

    def _get_days_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            overdue_days = 0.0
            if rec.state == 'posted':
                due_date = rec.invoice_date_due
                payment_date = rec.payment_date
                # print("due_date: ", due_date)
                if due_date:
                    if payment_date and payment_date > due_date:
                        overdue_days = (payment_date - due_date).days
                    elif today > due_date:
                        overdue_days = (today - due_date).days
            rec.overdue_days = overdue_days


class AccountInvoiceReport(models.Model):
    _inherit = 'account.invoice.report'

    collection_days = fields.Float(string="Collection Days", readonly=True)
    overdue_days = fields.Float(string="Days Overdue", readonly=True)

    _depends = {
        'account.move': ['collection_days', 'overdue_days', 'payment_date'],
    }

    def _select(self):
        return super()._select() + ", move.collection_days as collection_days" + \
               ", CASE " \
               "    WHEN move.payment_date IS NULL THEN (CURRENT_DATE - move.invoice_date_due)" \
               "    WHEN move.payment_date > move.invoice_date_due THEN (move.payment_date - move.invoice_date_due)" \
               "    ELSE 0.0" \
               "END AS overdue_days"

    def _group_by(self):
        return super()._group_by() + ", collection_days, overdue_days"



