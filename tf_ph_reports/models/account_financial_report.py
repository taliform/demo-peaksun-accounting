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

import ast

from odoo import models


class AccountFinancialReportLine(models.Model):
    _inherit = "account.financial.html.report.line"

    def _get_with_statement(self, financial_report):
        """ This function allow to define a WITH statement as prologue to the usual queries returned by query_get().
            It is useful if you need to shadow a table entirely and let the query_get work normally although you're
            fetching rows from your temporary table (built in the WITH statement) instead of the regular tables.

            @returns: the WITH statement to prepend to the sql query and the parameters used in that WITH statement
            @rtype: tuple(char, list)
        """
        sql = ''
        params = []

        # Cashflow Statement
        # ------------------
        # The cash flow statement has a dedicated query because because we want to make
        # a complex selection of account.move.line,
        # but keep simple to configure the financial report lines.
        if financial_report == self.env.ref('tf_ph_reports.account_financial_report_cashsummary0'):
            # Get all available fields from account_move_line, to build the 'select' part of the query
            replace_columns = {
                'date': 'ref.date',
                'debit': 'CASE WHEN \"account_move_line\".debit > 0 '
                         'THEN ref.matched_percentage * \"account_move_line\".debit ELSE 0 END AS debit',
                'credit': 'CASE WHEN \"account_move_line\".credit > 0 '
                          'THEN ref.matched_percentage * \"account_move_line\".credit ELSE 0 END AS credit',
                'balance': 'ref.matched_percentage * \"account_move_line\".balance AS balance'
            }
            columns = []
            columns_2 = []
            
            # Update sequence
            parent_ids = self.env['account.financial.html.report.line'].search([
                ('code', 'in', ['OP', 'IN', 'FI'])
            ])
            section_ids = self.env['account.financial.html.report.line'].search([
                ('parent_id.code', 'in', ['OP', 'IN', 'FI'])
            ])
            for parent_id in parent_ids:
                if parent_id.code == "OP":
                    seq_ctr = 1
                elif parent_id.code == "IN":
                    seq_ctr = 2
                else:
                    seq_ctr = 3
                for section_id in section_ids.filtered(lambda l: l.parent_id == parent_id).sorted(key=lambda x: x.id):
                    seq_ctr += 1
                    section_id.sequence = seq_ctr
                    
            user_types = self.env['account.account.type'].search([
                ('type', 'in', ('receivable', 'payable'))
            ])
            if not user_types:
                return sql, params
            
            for name, field in self.env['account.move.line']._fields.items():
                if not(field.store and field.type not in ('one2many', 'many2many')):
                    continue
                columns.append('\"account_move_line\".\"%s\"' % name)
                if name in replace_columns:
                    columns_2.append(replace_columns.get(name))
                else:
                    columns_2.append('\"account_move_line\".\"%s\"' % name)
                    
            select_clause_1 = ', '.join(columns)
            select_clause_2 = ', '.join(columns_2)

            # Get moves having a line using a bank account in one of the selected journals.
            if self.env.context.get('journal_ids'):
                bank_journals = self.env['account.journal'].browse(self.env.context.get('journal_ids'))
            else:
                bank_journals = self.env['account.journal'].search([
                    ('type', 'in', ('bank', 'cash'))
                ])
            bank_accounts = bank_journals.mapped('default_debit_account_id') \
                            + bank_journals.mapped('default_credit_account_id')

            self._cr.execute('SELECT DISTINCT(move_id) FROM account_move_line WHERE account_id IN %s', [tuple(bank_accounts.ids)])
            bank_move_ids = tuple([r[0] for r in self.env.cr.fetchall()])

            # Avoid crash if there's no bank moves to consider
            if not bank_move_ids:
                return '''
                WITH account_move_line AS (
                    SELECT \"account_move_line\".id, \"account_move_line\".date, \"account_move_line\".name, \"account_move_line\".debit_cash_basis, \"account_move_line\".credit_cash_basis, \"account_move_line\".move_id, \"account_move_line\".account_id, \"account_move_line\".journal_id, \"account_move_line\".balance_cash_basis, \"account_move_line\".amount_residual, \"account_move_line\".partner_id, \"account_move_line\".reconciled, \"account_move_line\".company_id, \"account_move_line\".company_currency_id, \"account_move_line\".amount_currency, \"account_move_line\".balance, \"account_move_line\".user_type_id, \"account_move_line\".tax_line_id, \"account_move_line\".move_id, \"account_move_line\".credit, \"account_move_line\".tax_exigible, \"account_move_line\".debit, \"account_move_line\".cf_html_section_id
                    FROM account_move_line
                    WHERE False)''', []

            # Fake domain to always get the join to the account_move_line__move_id table.
            fake_domain = [('move_id.id', '!=', None)]
            sub_tables, sub_where_clause, sub_where_params = self.env['account.move.line']\
                ._query_get(domain=fake_domain)
            tables, where_clause, where_params = self.env['account.move.line']\
                ._query_get(domain=fake_domain + ast.literal_eval(self.domain))

            # Get moves having a line using a bank account.
            bank_journals = self.env['account.journal'].search([('type', 'in', ('bank', 'cash'))])
            bank_accounts = bank_journals.mapped('default_debit_account_id') \
                            + bank_journals.mapped('default_credit_account_id')
            q = '''SELECT DISTINCT(\"account_move_line\".move_id)
                    FROM ''' + tables + '''
                    WHERE account_id IN %s
                    AND ''' + sub_where_clause
            p = [tuple(bank_accounts.ids)] + sub_where_params
            self._cr.execute(q, p)
            bank_move_ids = tuple([r[0] for r in self.env.cr.fetchall()])

            # Only consider accounts related to a bank/cash journal, not all liquidity accounts
            if self.code in ('CASHEND', 'CASHSTART'):
                return '''
                WITH account_move_line AS (
                    SELECT \"account_move_line\".id, \"account_move_line\".date, \"account_move_line\".name, \"account_move_line\".debit_cash_basis, \"account_move_line\".credit_cash_basis, \"account_move_line\".move_id, \"account_move_line\".account_id, \"account_move_line\".journal_id, \"account_move_line\".balance_cash_basis, \"account_move_line\".amount_residual, \"account_move_line\".partner_id, \"account_move_line\".reconciled, \"account_move_line\".company_id, \"account_move_line\".company_currency_id, \"account_move_line\".amount_currency, \"account_move_line\".balance, \"account_move_line\".user_type_id, \"account_move_line\".tax_line_id, \"account_move_line\".move_id, \"account_move_line\".credit, \"account_move_line\".tax_exigible, \"account_move_line\".debit, \"account_move_line\".cf_html_section_id
                    FROM account_move_line
                    WHERE account_id in %s)''', [tuple(bank_accounts.ids)]

            # Avoid crash if there's no bank moves to consider
            if not bank_move_ids:
                return '''
                WITH account_move_line AS (
                    SELECT \"account_move_line\".id, \"account_move_line\".date, \"account_move_line\".name, \"account_move_line\".debit_cash_basis, \"account_move_line\".credit_cash_basis, \"account_move_line\".move_id, \"account_move_line\".account_id, \"account_move_line\".journal_id, \"account_move_line\".balance_cash_basis, \"account_move_line\".amount_residual, \"account_move_line\".partner_id, \"account_move_line\".reconciled, \"account_move_line\".company_id, \"account_move_line\".company_currency_id, \"account_move_line\".amount_currency, \"account_move_line\".balance, \"account_move_line\".user_type_id, \"account_move_line\".tax_line_id, \"account_move_line\".move_id, \"account_move_line\".credit, \"account_move_line\".tax_exigible, \"account_move_line\".debit, \"account_move_line\".cf_html_section_id
                    FROM account_move_line
                    WHERE False)''', []

            # The following query is aliasing the account.move.line table to consider only the journal
            # entries where, at least, one line is touching a liquidity account. Counterparts are either
            # shown directly if they're not reconciled (or not reconciliable),
            # either replaced by the accounts of the entries they're reconciled with.
            sql = """WITH account_move_line AS (
              SELECT \"account_move_line\".id, \"account_move_line\".date, \"account_move_line\".name, \"account_move_line\".debit_cash_basis, \"account_move_line\".credit_cash_basis, \"account_move_line\".move_id, \"account_move_line\".account_id, \"account_move_line\".journal_id, \"account_move_line\".balance_cash_basis, \"account_move_line\".amount_residual, \"account_move_line\".partner_id, \"account_move_line\".reconciled, \"account_move_line\".company_id, \"account_move_line\".company_currency_id, \"account_move_line\".amount_currency, \"account_move_line\".balance, \"account_move_line\".user_type_id, \"account_move_line\".tax_line_id, \"account_move_line\".move_id, \"account_move_line\".credit, \"account_move_line\".tax_exigible, \"account_move_line\".debit, \"account_move_line\".cf_html_section_id
               FROM """ + tables + """
               WHERE (\"account_move_line\".journal_id IN (SELECT id FROM account_journal WHERE type in ('cash', 'bank'))
                 OR \"account_move_line\".move_id NOT IN (SELECT DISTINCT move_id FROM account_move_line WHERE user_type_id IN %s))
                 AND """ + where_clause + """
              UNION ALL
              (
               WITH payment_table AS (
                 SELECT aml.move_id, \"account_move_line\".date, CASE WHEN aml.balance = 0 THEN 0 ELSE part.amount / ABS(aml.balance) END as matched_percentage
                   FROM account_partial_reconcile part LEFT JOIN account_move_line aml ON aml.id = part.debit_move_id, """ + tables + """
                   WHERE part.credit_move_id = "account_move_line".id
                    AND "account_move_line".user_type_id IN %s
                    AND """ + where_clause + """
                 UNION ALL
                 SELECT aml.move_id, \"account_move_line\".date, CASE WHEN aml.balance = 0 THEN 0 ELSE part.amount / ABS(aml.balance) END as matched_percentage
                   FROM account_partial_reconcile part LEFT JOIN account_move_line aml ON aml.id = part.credit_move_id, """ + tables + """
                   WHERE part.debit_move_id = "account_move_line".id
                    AND "account_move_line".user_type_id IN %s
                    AND """ + where_clause + """
               )
               SELECT aml.id, ref.date, aml.name,
                 CASE WHEN aml.debit > 0 THEN ref.matched_percentage * aml.debit ELSE 0 END AS debit_cash_basis,
                 CASE WHEN aml.credit > 0 THEN ref.matched_percentage * aml.credit ELSE 0 END AS credit_cash_basis,
                 aml.move_id, aml.account_id, aml.journal_id,
                 ref.matched_percentage * aml.balance AS balance_cash_basis,
                 aml.amount_residual, aml.partner_id, aml.reconciled, aml.company_id, aml.company_currency_id, aml.amount_currency, aml.balance, aml.user_type_id, aml.tax_line_id, aml.move_id, aml.credit, aml.tax_exigible, aml.debit, aml.cf_html_section_id
                FROM account_move_line aml
                RIGHT JOIN payment_table ref ON aml.move_id = ref.move_id
                WHERE journal_id NOT IN (SELECT id FROM account_journal WHERE type in ('cash', 'bank'))
                  AND aml.move_id IN (SELECT DISTINCT move_id FROM account_move_line WHERE user_type_id IN %s)
              )
            ) """ 
            params = [tuple(user_types.ids)] + where_params + [tuple(user_types.ids)] + where_params + [tuple(user_types.ids)] + where_params + [tuple(user_types.ids)]
        elif self.env.context.get('cash_basis'):
            # Cash basis option
            # -----------------
            # In cash basis, we need to show amount on income/expense accounts,
            # but only when they're paid AND under the payment date in the reporting, so
            # we have to make a complex query to join aml from the invoice (for the account),
            # aml from the payments (for the date) and partial reconciliation
            # (for the reconciled amount).
            user_types = self.env['account.account.type'].search([('type', 'in', ('receivable', 'payable'))])
            if not user_types:
                return sql, params

            # Get all columns from account_move_line using the psql metadata table
            # in order to make sure all columns from the account.move.line model
            # are present in the shadowed table.
            sql = "SELECT column_name FROM information_schema.columns WHERE table_name='account_move_line'"
            self.env.cr.execute(sql)
            columns = []
            columns_2 = []

            replace_columns = {
                'date': 'ref.date',
                'debit_cash_basis': 'CASE WHEN aml.debit > 0 '
                                    'THEN ref.matched_percentage * aml.debit ELSE 0 END AS debit_cash_basis',
                'credit_cash_basis': 'CASE WHEN aml.credit > 0 '
                                     'THEN ref.matched_percentage * aml.credit ELSE 0 END AS credit_cash_basis',
                'balance_cash_basis': 'ref.matched_percentage * aml.balance AS balance_cash_basis'
            }
            for field in self.env.cr.fetchall():
                field = field[0]
                columns.append("\"account_move_line\".\"%s\"" % (field,))
                if field in replace_columns:
                    columns_2.append(replace_columns.get(field))
                else:
                    columns_2.append('aml.\"%s\"' % (field,))
        
            select_clause_1 = ', '.join(columns)
            select_clause_2 = ', '.join(columns_2)

            # we use query_get() to filter out unrelevant journal items to have a shadowed table as small as possible
            tables, where_clause, where_params = self.env['account.move.line']._query_get(domain=self._get_aml_domain())
            sql = """WITH account_move_line AS (
              SELECT """ + select_clause_1 + """
               FROM """ + tables + """
               WHERE (\"account_move_line\".journal_id IN (SELECT id FROM account_journal WHERE type in ('cash', 'bank'))
                 OR \"account_move_line\".move_id NOT IN (SELECT DISTINCT move_id FROM account_move_line WHERE user_type_id IN %s))
                 AND """ + where_clause + """
              UNION ALL
              (
               WITH payment_table AS (
                 SELECT aml.move_id, \"account_move_line\".date,
                        CASE WHEN (aml.balance = 0 OR sub_aml.total_per_account = 0)
                            THEN 0
                            ELSE part.amount / ABS(sub_aml.total_per_account)
                        END as matched_percentage
                   FROM account_partial_reconcile part
                   LEFT JOIN account_move_line aml ON aml.id = part.debit_move_id
                   LEFT JOIN (SELECT move_id, account_id, ABS(SUM(balance)) AS total_per_account
                                FROM account_move_line
                                GROUP BY move_id, account_id) sub_aml
                            ON (aml.account_id = sub_aml.account_id AND sub_aml.move_id=aml.move_id)
                   LEFT JOIN account_move am ON aml.move_id = am.id, """ + tables + """
                   WHERE part.credit_move_id = "account_move_line".id
                    AND "account_move_line".user_type_id IN %s
                    AND """ + where_clause + """
                 UNION ALL
                 SELECT aml.move_id, \"account_move_line\".date,
                        CASE WHEN (aml.balance = 0 OR sub_aml.total_per_account = 0)
                            THEN 0
                            ELSE part.amount / ABS(sub_aml.total_per_account)
                        END as matched_percentage
                   FROM account_partial_reconcile part
                   LEFT JOIN account_move_line aml ON aml.id = part.credit_move_id
                   LEFT JOIN (SELECT move_id, account_id, ABS(SUM(balance)) AS total_per_account
                                FROM account_move_line
                                GROUP BY move_id, account_id) sub_aml
                            ON (aml.account_id = sub_aml.account_id AND sub_aml.move_id=aml.move_id)
                   LEFT JOIN account_move am ON aml.move_id = am.id, """ + tables + """
                   WHERE part.debit_move_id = "account_move_line".id
                    AND "account_move_line".user_type_id IN %s
                    AND """ + where_clause + """
               )
               SELECT """ + select_clause_2 + """
                FROM account_move_line aml
                RIGHT JOIN payment_table ref ON aml.move_id = ref.move_id
                WHERE journal_id NOT IN (SELECT id FROM account_journal WHERE type in ('cash', 'bank'))
                  AND aml.move_id IN (SELECT DISTINCT move_id FROM account_move_line WHERE user_type_id IN %s)
              )
            ) """
            params = [tuple(user_types.ids)] \
                     + where_params \
                     + [tuple(user_types.ids)] \
                     + where_params \
                     + [tuple(user_types.ids)] \
                     + where_params \
                     + [tuple(user_types.ids)]
        return sql, params
