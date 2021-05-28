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
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_TYPE = [
    ('internal', "INTERNAL TRANSFERS"),
    ('customer_pdc', "CUSTOMER PDCS"),
    ('collection', "COLLECTIONS"),
    ('disbursement', "DISBURSEMENTS"),
    ('vendor_pdc', "VENDOR PDCS"),
    ('other', "OTHER PROJECTIONS"),
    ('report', "REPORT")
]


class TfCfProjection(models.AbstractModel):
    _name = 'tf.cf.projection'
    _description = "Cash Flow Projection"

    type = fields.Selection(_TYPE, "Projection Type", required=True)
    date_from = fields.Date("Date From", required=True,
                            default=lambda a: fields.Date.context_today(a) - relativedelta(days=6))
    date_to = fields.Date("Date To", required=True,
                          default=fields.Date.context_today)

    @api.constrains('date_from', 'date_to')
    def validate_dates(self):
        if self.date_from > self.date_to:
            raise ValidationError(
                "To Date (%s) should be greater than From Date (%s)." % (self.date_to, self.date_from))


class TfCfProjectionLine(models.TransientModel):
    _name = 'tf.cf.projection.line'
    _description = 'Cash Flow Projection Report lines'

    type = fields.Selection(_TYPE, "Projection Type", required=True)
    journal_id = fields.Many2one('account.journal', "Journal")
    payment_id = fields.Many2one('account.payment', "Payment")
    move_id = fields.Many2one('account.move', "Transaction")
    date = fields.Date("Payment Date", required=True)
    currency_id = fields.Many2one(related="move_id.currency_id")
    amount = fields.Monetary(string='Amount', currency_field='currency_id', required=True)
    transfer_projected_date = fields.Date(
        string="Internal Transfer Projected Date", related='payment_id.transfer_projected_date')
    transfer_projected_bank_id = fields.Many2one(
        string="Internal Transfer Projected Bank", related='payment_id.transfer_projected_bank_id')
    disbursement_projected_date = fields.Date(
        string="Disbursement Projected Date", related='move_id.disbursement_projected_date')
    disbursement_projected_bank_id = fields.Many2one(
        string="Disbursement Projected Bank", related='move_id.disbursement_projected_bank_id')

