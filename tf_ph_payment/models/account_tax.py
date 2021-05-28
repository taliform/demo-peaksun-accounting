# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################
from odoo import api, fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    @api.depends('invoice_repartition_line_ids', 'invoice_repartition_line_ids.account_id')
    def _compute_account_id(self):
        """ Get the corresponding account from the tax's repartition lines. Only gets the first account found, so it's
        not exactly a reliable way to determine the account to use, but should be enough for localized PH. """
        for tax in self:
            account = None
            for line in tax.invoice_repartition_line_ids.filtered(lambda l: l.account_id):
                account = line.account_id
                break
            tax.account_id = account

    account_id = fields.Many2one('account.account', 'Account', compute="_compute_account_id", store=True)
    for_withholding = fields.Boolean(copy=False)

    # Service VAT Module Fields and Functions

    is_service = fields.Boolean("Service Tax")
    account_vat_service_id = fields.Many2one('account.account', "VAT Service Account",
                                             help="Set the account that will be set for reconciling "
                                                  "service re-class entries.")
