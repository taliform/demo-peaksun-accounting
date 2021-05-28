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

from datetime import timedelta

from odoo import models, fields
from odoo.tools import float_is_zero


class report_account_general_ledger(models.AbstractModel):
    _inherit = "account.general.ledger"

    def _group_by_account_id(self, options, line_id):
        accounts = {}
        results = self._do_query_group_by_account(options, line_id)
        initial_bal_date_to = fields.Date.from_string(self.env.context['date_from_aml']) + timedelta(days=-1)
        initial_bal_results = self.with_context(date_to=initial_bal_date_to.strftime('%Y-%m-%d'))\
            ._do_query_group_by_account(options, line_id)

        context = self.env.context

        last_day_previous_fy = self.env.user.company_id.compute_fiscalyear_dates(
            fields.Date.from_string(self.env.context['date_from_aml'])
        )['date_from'] + timedelta(days=-1)
        unaffected_earnings_per_company = {}

        for cid in context.get('company_ids', []):
            company = self.env['res.company'].browse(cid)
            unaffected_earnings_per_company[company] = \
                self.with_context(date_to=last_day_previous_fy.strftime('%Y-%m-%d'), date_from=False)\
                    ._do_query_unaffected_earnings(options, line_id, company)

        unaff_earnings_treated_companies = set()
        unaffected_earnings_type = self.env.ref('account.data_unaffected_earnings')

        for account_id, result in results.items():
            account = self.env['account.account'].browse(account_id)
            accounts[account] = result
            accounts[account]['initial_bal'] = initial_bal_results.get(account.id, {
                'balance': 0,
                'amount_currency': 0,
                'debit': 0,
                'credit': 0
            })

            if account.user_type_id == unaffected_earnings_type \
                    and account.company_id not in unaff_earnings_treated_companies:
                # add the benefit/loss of previous fiscal year to unaffected earnings accounts
                unaffected_earnings_results = unaffected_earnings_per_company[account.company_id]
                for field in ['balance', 'debit', 'credit']:
                    accounts[account]['initial_bal'][field] += unaffected_earnings_results[field]
                    accounts[account][field] += unaffected_earnings_results[field]
                unaff_earnings_treated_companies.add(account.company_id)
            # use query_get + with statement instead of a search in order to work in cash basis too
            aml_ctx = {}
            if context.get('date_from_aml'):
                aml_ctx = {
                    'strict_range': True,
                    'date_from': context['date_from_aml'],
                }
                
            if not context.get('print_mode'):
                # fetch the 81 first amls. The report only displays the first 80 amls.
                # We will use the 81st to know if there are more than 80 in which case a
                # link to the list view must be displayed.
                aml_ids = self.with_context(**aml_ctx)._do_query(options, account_id, group_by_account=False, limit=81)
                aml_ids = [x[0] for x in aml_ids]
            else:
                aml_ids = self.with_context(**aml_ctx)._do_query(options, account_id, group_by_account=False)
                aml_ids = [x[0] for x in aml_ids]
                
            accounts[account]['total_lines'] = len(aml_ids)
            offset = int(options.get('lines_offset', 0))
            if self.MAX_LINES:
                stop = offset + self.MAX_LINES
            else:
                stop = None
            if not context.get('print_mode'):
                aml_ids = aml_ids[offset:stop]

            accounts[account]['lines'] = self.env['account.move.line'].browse(aml_ids)

        # For each company, if the unaffected earnings account wasn't in the selection yet: add it manually
        user_currency = self.env.user.company_id.currency_id
        for cid in context.get('company_ids', []):
            company = self.env['res.company'].browse(cid)
            if company not in unaff_earnings_treated_companies and not float_is_zero(unaffected_earnings_per_company[company]['balance'], precision_digits=user_currency.decimal_places):
                unaffected_earnings_account = self.env['account.account'].search([
                    ('user_type_id', '=', unaffected_earnings_type.id), ('company_id', '=', company.id)
                ], limit=1)
                if unaffected_earnings_account and (not line_id or unaffected_earnings_account.id == line_id):
                    accounts[unaffected_earnings_account[0]] = unaffected_earnings_per_company[company]
                    accounts[unaffected_earnings_account[0]]['initial_bal'] = unaffected_earnings_per_company[company]
                    accounts[unaffected_earnings_account[0]]['lines'] = []
                    accounts[unaffected_earnings_account[0]]['total_lines'] = 0
        return accounts
