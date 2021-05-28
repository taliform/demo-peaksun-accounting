# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
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
from odoo import models, fields

TRANSACTION_TYPE = [('0', 'Purchase of Capital Goods'),
                    ('1', 'Purchase of Good Other than Capital Goods'),
                    ('2', 'Purchase of Services'),
                    ('3', 'Purchases Not Qualified for Input Tax'),
                    ('4', 'Others')]


class ExpenseCategory(models.Model):
    _name = 'expense.category'
    _description = 'Expense Category'
    _inherit = ['mail.thread']

    def _get_company_id(self):
        """
        @summary: This will default Company Id on the form by
        getting the attached company_id of the current User. 
        """
        company_id = self.env.user.company_id.id
        return company_id
    
    company_id = fields.Many2one('res.company', string='Company', default=_get_company_id, track_visibility='onchange')
    name = fields.Char(required=True, track_visibility='onchange')
    description = fields.Text(track_visibility='onchange')
    account_id = fields.Many2one('account.account', string='Account', track_visibility='onchange')
    transaction_type = fields.Selection(selection=TRANSACTION_TYPE, string='Transaction Type',
                                        track_visibility='onchange')

        
class ReplenishExpenseCategory(models.Model):
    _name = 'replenish.expense.category'
    _description = 'Replenish Expense Category'

    def _get_company_id(self):
        """
        @summary: This will default Company Id on the form by
        getting the attached company_id of the current User. 
        """
        company_id = self.env.user.company_id.id
        return company_id
    
    company_id = fields.Many2one('res.company', string='Company', default=_get_company_id, track_visibility='onchange')
    expense_category_id = fields.Many2one('expense.category', 'Expense Category', required=True)
    replenish_id = fields.Many2one('cash.replenishment', 'cash.replenishment', required=True, ondelete='cascade')
    amount = fields.Float(computed='_get_total_expense_category')

    def _get_total_expense_category(self):
        for rec in self:
            if rec.replenish_id and rec.replenish_id.replenishment_line_ids:
                for repl_line_id in rec.replenish_id.replenishment_line_ids:
                    if repl_line_id.invoice_line:
                        for inv_id in repl_line_id.invoice_line:
                            if inv_id.cash_transaction_id.expense_category_id.id == rec.expense_category_id.id:
                                rec.amount += inv_id.price_unit
