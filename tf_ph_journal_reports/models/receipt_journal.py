# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Andrian Jim Toscano Cubillas <andrian.cubillas@synersysph.com.ph>
# V13 Porting: Bamboo <martin@taliform.com>
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

from odoo import models, api, fields, _


class AccountReceiptJournalSummary(models.AbstractModel):
    _name = 'account.receipt.journal.summary'
    _description = 'Cash Receipt Journal Summary'
    _inherit = 'account.journal.summary'

    #     filter_journal_type = [{'id': 'cash', 'name': _('Cash'), 'type': 'cash', 'selected': False}, {'id': 'bank', 'name': _('Bank'), 'type': 'bank', 'selected': False}]

    def _get_company_id(self):
        """
        @summary: This will default Company Id on the form by
        getting the attached company_id of the current User. 
        """
        user_id = self.env.uid
        company_id = self.env['res.users'].browse(user_id).company_id.id
        return company_id

    company_id = fields.Many2one('res.company', string='Company', default=_get_company_id, track_visibility='onchange')

    @api.model
    def get_title(self):
        return _('Cash Receipt Journal Report')

    def _get_report_name(self):
        return _("Cash Receipt Journal Report")

    def _set_context(self, options):
        ctx = super(AccountReceiptJournalSummary, self)._set_context(options)
        ctx['journal_type'] = ['cash', 'bank']
        return ctx

    def _get_templates(self):
        templates = super(AccountReceiptJournalSummary, self)._get_templates()
        templates['line_template'] = 'account_reports.line_template'
        return templates

    @api.model
    def _get_lines(self, options, line_id=None):
        AccountJournal = self.env['account.journal']
        context = self.env.context
        ctx_journal_ids = context.get('journal_ids')
        journal_type = context.get('journal_type')
        selected_partner_ids = context.get('partner_ids')
        partner_categories = context.get('partner_categories')
        date_from = context.get('date_from')
        date_to = context.get('date_to')
        unfold_all = context.get('print_mode') and not options.get('unfolded_lines', [])
        company_ids = self.env['res.company']
        partner_ids2 = []
        lines = []

        # Get selected company
        if context.get('company_ids', False):
            comp_ids = context.get('company_ids')
            for comp_id in comp_ids:
                comp_id = self.env['res.company'].browse(comp_id)
                company_ids += comp_id

        domain = [
            ('type', '=', 'entry'),
            ('payment_id.payment_date', '<=', date_to),
            ('payment_id.payment_date', '>=', date_from),
            ('payment_id.payment_type', '=', 'inbound'),
            ('parent_state', 'in', ['posted', 'reconciled']),
            ('journal_id.type', 'in', journal_type),
            ('company_id', 'child_of', company_ids.ids)]

        if selected_partner_ids:
            domain.append(('partner_id', 'in', selected_partner_ids.ids))
        if ctx_journal_ids:
            domain.append(('journal_id', 'in', ctx_journal_ids))
        if partner_categories:
            domain.append(('partner_id.category_id', 'in', partner_categories.ids))

        AccountMoveLine = self.env['account.move.line']
        move_ids = AccountMoveLine.search(domain, order='date asc')

        if line_id:
            line_id = int(line_id.split('_')[1]) or None
            journal_ids = AccountJournal.browse(line_id)

        elif options.get('partner_ids'):
            # If a default partner is set, we only want to load the line referring to it.
            partner_ids2 = options['partner_ids']
            domain = [('payment_id.payment_date', '<=', date_to), ('payment_id.payment_date', '>=', date_from),
                      ('payment_id.payment_type', '=', 'inbound'), ('parent_state', 'in', ['posted', 'reconciled']),
                      ('journal_id.type', 'in', journal_type)]
            if partner_ids2:
                domain.append(('partner_id', 'in', partner_ids2))
            if ctx_journal_ids:
                domain.append(('journal_id', 'in', ctx_journal_ids))
            move_ids = AccountMoveLine.search(domain, order='date asc')
            journal_ids = move_ids.mapped('journal_id')
        else:
            journal_ids = move_ids.mapped('journal_id')

        if move_ids:
            for journal_id in journal_ids:
                journal_debit = journal_credit = 0.00
                journal_move_ids = move_ids.filtered(lambda j: j.journal_id == journal_id)

                journal_debit = sum(journal_move_ids.mapped('debit'))
                journal_credit = sum(journal_move_ids.mapped('credit'))

                if journal_debit + journal_credit:
                    journal_columns = ['', '', '', '', '',
                                       self.format_value(journal_debit), self.format_value(journal_credit), '', '', '']
                    lines.append({
                        'id': 'journal_' + str(journal_id.id),
                        'type': 'line',
                        'name': journal_id.name,
                        'columns': [{'name': v} for v in journal_columns],
                        'colspan': 1,
                        'level': 2,
                        'unfoldable': True,
                        'unfolded': 'journal_' + str(journal_id.id) in options.get('unfolded_lines') or unfold_all,
                    })

                for move in journal_move_ids:
                    if 'journal_' + str(journal_id.id) in options.get('unfolded_lines') or unfold_all:
                        columns = [
                            str(move.move_id.name),
                            str(move.ref or ''),
                            str(move.partner_id.name or ''),
                            str(move.name),
                            str(move.account_id.name),
                            self.format_value(move.debit),
                            self.format_value(move.credit),
                            str(move.analytic_account_id.name or ''),
                            str(move.full_reconcile_id.name or ''),
                            self.format_value(move.amount_currency),
                        ]

                        lines.append({
                            'id': 'move_' + str(move.id),
                            'type': 'line',
                            'name': move.date,
                            'class': 'date',
                            'columns': [{'name': v} for v in columns],
                            'parent_id': 'journal_' + str(journal_id.id),
                            'colspan': 1,
                            'level': 3,
                            'unfoldable': False,
                        })
        return lines
