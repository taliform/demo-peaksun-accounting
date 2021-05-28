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

    principal_account_id = fields.Many2one('account.account', string='Principal Account',
                                           config_parameter='bank_loan.principal_account_id')
    penalty_account_id = fields.Many2one('account.account', string='Penalty Account',
                                         config_parameter='bank_loan.penalty_account_id')
    interest_account_id = fields.Many2one('account.account', string='Interest Account',
                                          config_parameter='bank_loan.interest_account_id')
    other_expense_account_id = fields.Many2one('account.account', string='Other Expense Account',
                                               config_parameter='bank_loan.other_expense_account_id')
    prepaid_expense_account_id = fields.Many2one('account.account', string='Prepaid Expense Account',
                                                 config_parameter='bank_loan.prepaid_expense_account_id')
    accrued_expense_account_id = fields.Many2one('account.account', string='Accrued Expense Account',
                                                 config_parameter='bank_loan.accrued_expense_account_id')

    collection_journal_id = fields.Many2one('account.journal', string='Collection Journal',
                                            config_parameter='bank_loan.collection_journal_id')
    loan_journal_id = fields.Many2one('account.journal', string='Loan Journal',
                                      config_parameter='bank_loan.loan_journal_id')
    adjusting_journal_id = fields.Many2one('account.journal', string='Adjusting Journal',
                                           config_parameter='bank_loan.adjusting_journal_id')
    withholding_tax_id = fields.Many2one('account.tax', string='Withholding Tax',
                                         config_parameter='bank_loan.withholding_tax_id')