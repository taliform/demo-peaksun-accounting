# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Bamboo <joshua@taliform.com>
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
from datetime import timedelta

from odoo import api, fields, models,  _
from odoo.exceptions import ValidationError


class AccountTax(models.Model):
    _inherit = "account.tax"

    withholding_tax_account_id = fields.Many2one('account.account', 'Withholding Tax Account',
                                                 help='Account that will be the basis for the reclassification of '
                                                      'withholding tax of customers once certificate is received')
    tax_due_2307 = fields.Selection([('out_invoice', 'Based on Invoice'), ('entry', 'Based on Payment')],
                                    default='out_invoice', string="Tax Due",
                                    copy=False)

class AccountMove(models.Model):
    _inherit = 'account.move'

    reconcile_id = fields.Many2one('bir.creditable.tax.withheld.reconcile', 'Reconcile (2307)', copy=False)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    reconcile_id = fields.Many2one('bir.creditable.tax.withheld.reconcile', 'Reconcile (2307)', copy=False)
    tax_withheld = fields.Monetary('Tax Withheld', compute="_compute_tax_withheld")
    is_reconcile = fields.Boolean(copy=False)
    allocation = fields.Monetary(copy=False)

    @api.onchange('is_reconcile')
    def _onchange_reconcile(self):
        for rec in self:
            rec.allocation = rec.tax_withheld

    @api.depends('debit', 'credit')
    def _compute_tax_withheld(self):
        for rec in self:
            rec.tax_withheld = abs(rec.debit-rec.credit)
