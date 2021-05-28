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

from odoo import models, _


class report_account_coa(models.AbstractModel):
    _inherit = "account.coa.report"

    def _post_process(self, grouped_accounts, initial_balances, options, comparison_table):
        lines = []
        context = self.env.context
        company_id = context.get('company_id') or self.env.user.company_id
        title_index = ''
        sorted_accounts = sorted(grouped_accounts, key=lambda a: a.code)
        zero_value = ''
        sum_columns = [0, 0, 0, 0]
        for period in range(len(comparison_table)):
            sum_columns += [0, 0]
        for account in sorted_accounts:
            # skip accounts with all periods = 0 and no initial balance
            non_zero = False
            for p in range(len(comparison_table)):
                if not company_id.currency_id.is_zero(grouped_accounts[account][p]['balance']) \
                        or not company_id.currency_id.is_zero(initial_balances.get(account, 0)):
                    non_zero = True
            if not non_zero:
                continue

            initial_balance = initial_balances.get(account, 0.0)
            sum_columns[0] += initial_balance if initial_balance > 0 else 0
            sum_columns[1] += -initial_balance if initial_balance < 0 else 0
            cols = [
                {
                    'name': initial_balance > 0 and self.format_value(initial_balance) or zero_value,
                    'no_format_name': initial_balance > 0 and initial_balance or 0
                },
                {
                    'name': initial_balance < 0 and self.format_value(-initial_balance) or zero_value,
                    'no_format_name': initial_balance < 0 and abs(initial_balance) or 0,
                    'style': 'padding-right: 35px'
                },
            ]
            total_periods = 0
            for period in range(len(comparison_table)):
                amount = grouped_accounts[account][period]['balance']
                debit = grouped_accounts[account][period]['debit']
                credit = grouped_accounts[account][period]['credit']
                total_periods += amount
                cols += [
                    {
                        'name': debit > 0 and self.format_value(debit) or zero_value,
                        'no_format_name': debit > 0 and debit or 0
                    },
                    {
                        'name': credit > 0 and self.format_value(credit) or zero_value,
                        'no_format_name': credit > 0 and abs(credit) or 0,
                        'style': 'padding-right: 35px'
                    }
                ]
                # In sum_columns, the first 2 elements are the initial balance's Debit and Credit
                # index of the credit of previous column generally is:
                p_indice = period * 2 + 1
                sum_columns[(p_indice) + 1] += debit if debit > 0 else 0
                sum_columns[(p_indice) + 2] += credit if credit > 0 else 0

            total_amount = initial_balance + total_periods
            sum_columns[-2] += total_amount if total_amount > 0 else 0
            sum_columns[-1] += -total_amount if total_amount < 0 else 0
            cols += [
                {
                    'name': total_amount > 0 and self.format_value(total_amount) or zero_value,
                    'no_format_name': total_amount > 0 and total_amount or 0
                },
                {
                    'name': total_amount < 0 and self.format_value(-total_amount) or zero_value,
                    'no_format_name': total_amount < 0 and abs(total_amount) or 0
                },
            ]
            name = account.code + " " + account.name
            lines.append({
                'id': account.id,
                'name': len(name) > 40 and not context.get('print_mode') and name[:40] + '...' or name,
                'title_hover': name,
                'columns': cols,
                'unfoldable': False,
                'caret_options': 'account.account',
            })
        lines.append({
            'id': 'grouped_accounts_total',
            'name': _('Total'),
            'class': 'total',
            'columns': [{'name': self.format_value(v)} for v in sum_columns],
            'level': 1,
        })
        return lines
