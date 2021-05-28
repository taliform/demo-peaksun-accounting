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
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    disbursement_projected_date = fields.Date("Projected Date")
    disbursement_projected_bank_id = fields.Many2one(
        'account.journal', "Projected Bank Account",
        domain="[('type','=','bank'),('for_undeposited_payment','=',False)]")


class AccountJournal(models.Model):
    _inherit = "account.journal"

    for_undeposited_payment = fields.Boolean(
        "Undeposited Payment Journal", help="Indicates whether the Journal is used as an Undeposited Payment Journal")


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    for_undeposited_payment = fields.Boolean(related='journal_id.for_undeposited_payment')
    is_transferred = fields.Boolean("Transferred", copy=False)
    counter_in_transfer_id = fields.Many2one(
        'account.payment', "Counterpart Internal Transfer",
        help="Indicates the payment record's counterpart internal transfer record")
    transfer_projected_date = fields.Date("Projected Date")
    transfer_projected_bank_id = fields.Many2one(
        'account.journal', "Projected Bank Account",
        domain="[('type','=','bank'),('for_undeposited_payment','=',False)]")

    def post(self):
        res = super(AccountPayment, self).post()
        """
        Setting undeposited payments to transferred is put in the post function in case of manual posting 
        instead of using the batch validation .
        """
        self.mapped('counter_in_transfer_id').write({'is_transferred': True})
        return res