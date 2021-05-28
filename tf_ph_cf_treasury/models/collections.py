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


class TfCfCollection(models.Model):
    _name = 'tf.cf.collection'
    _description = "Cash Flow Projection"

    date_from = fields.Date("Date From", required=True)
    date_to = fields.Date("Date To", required=True)
    projected_rate = fields.Float("Projected Percentage Collected", required=True)

    @api.constrains('date_from', 'date_to')
    def check_dates(self):
        for rec in self:
            from_id = self.search([
                ('date_from', '<=', self.date_from),
                ('date_to', '>=', self.date_from),
                ('id', '!=', self.id)
            ])
            if from_id:
                raise ValidationError("Date From (%s) overlaps with projection (%s - %s)." % (
                    self.date_from, from_id.date_from, from_id.date_to))
            to_id = self.search([
                ('date_from', '<=', self.date_to),
                ('date_to', '>=', self.date_to),
                ('id', '!=', self.id)
            ])
            if to_id:
                raise ValidationError("Date To (%s) overlaps with projection (%s - %s)." % (
                    self.date_to, to_id.date_from, to_id.date_to))

    def get_initial_balance(self):
        self.env.cr.execute("""
        SELECT 
            COALESCE(SUM(aml.balance),0) as balance
        FROM 
            account_move_line as aml,
            account_move as am
        WHERE
            aml.move_id = am.id
            AND aml.date <= '%s'
            AND aml.account_internal_type = 'receivable'
            AND am.state = 'posted'
        """ % self.date_from)
        balance = self.env.cr.fetchone()
        balance = balance[0] if balance else 0.0

        self.env.cr.execute("""
              SELECT 
                  COALESCE(SUM(ap.amount),0) as pdc_amount
              FROM 
                  account_payment as ap
              WHERE
                  ap.pdc_id IS NOT NULL
                  AND ap.state NOT IN ('draft','cancelled')
                  AND ap.payment_date <= '%s'
                  AND ap.partner_type = 'customer'
              """ % self.date_from)
        pdc_amount = self.env.cr.fetchone()
        pdc_amount = pdc_amount[0] if pdc_amount else 0.0
        return (balance - pdc_amount) * self.projected_rate

    def get_payments_aof_date(self, date):
        self.env['account.payment']
        self.env.cr.execute("""
              SELECT 
                  COALESCE(SUM(ap.amount),0) as amount
              FROM 
                  account_payment as ap
              WHERE
                  ap.pdc_id IS NULL
                  AND ap.state NOT IN ('draft','cancelled')
                  AND ap.payment_date = '%s'
                  AND ap.partner_type = 'customer'
              """ % date)
        amount = self.env.cr.fetchone()
        amount = amount[0] if amount else 0.0

        return amount
