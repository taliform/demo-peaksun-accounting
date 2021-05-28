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
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CreateUnreleasedAml(models.TransientModel):
    _name = "create.unreleased.aml"
    _description = 'Create Unreleased Account Move Line'

    ref = fields.Char("Reference")
    date = fields.Date("Journal Entry Date", default=fields.Date.context_today)
    amount = fields.Monetary("Unreleased Amount")
    currency_id = fields.Many2one('res.currency', string='Currency')
    journal_id = fields.Many2one('account.journal', "Journal")
    bank_statement_id = fields.Many2one('account.bank.statement', "Bank Statement")
    cf_html_type_id = fields.Many2one('account.financial.html.report.line', string="Cash Flow Type",
                                      domain="[('cf_type','=',True)]")
    cf_html_section_id = fields.Many2one('account.financial.html.report.line', string="Section")
    is_cf_required = fields.Boolean(related='journal_id.req_cashflow', string='Required Cash Flow')
    credit_account_id = fields.Many2one('account.account', "Credit Account")
    debit_account_id = fields.Many2one('account.account', "Debit Account")

    @api.onchange('cf_html_type_id')
    def onchange_cf_type_id(self):
        self.cf_html_section_id = False

    def action_confirm(self):
        AccountMove = self.env['account.move']
        AccountMoveLine = self.env['account.move.line']

        ref = "Bank Statement: " + (self.ref or '')
        amount = self.amount
        cf_html_type_id = self.cf_html_type_id.id if self.cf_html_type_id else False
        cf_html_section_id = self.cf_html_section_id.id if self.cf_html_section_id else False

        # Create Journal Entry
        am_id = AccountMove.create({
            'ref': ref,
            'date': self.date,
            'journal_id': self.journal_id.id,
            'cf_html_type_id': cf_html_type_id,
            'cf_html_section_id': cf_html_section_id
        })

        # Create Debit line
        aml_val = {
            'move_id': am_id.id,
            'date': self.date,
            'account_id': self.debit_account_id.id,
            'credit': 0.0,
            'currency_id': '' if am_id.currency_id.display_name == 'PHP' else am_id.currency_id,
            'debit': amount,
            'name': ref,
            'statement_id': self.bank_statement_id.id,
        }
        AccountMoveLine.with_context({'check_move_validity': False}).create(aml_val)

        # Create Credit Line
        aml_val.update({
            'account_id': self.credit_account_id.id,
            'debit': 0.0,
            'credit': amount,
            'cf_html_section_id': cf_html_section_id,
        })
        AccountMoveLine.create(aml_val)

        am_id.post()
        self.bank_statement_id.unreleased_am_id = am_id
