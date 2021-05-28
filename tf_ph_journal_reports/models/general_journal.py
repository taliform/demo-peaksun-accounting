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


class AccountGeneralJournalSummary(models.AbstractModel):
    _name = 'account.general.journal.summary'
    _description = 'General Journal Summary'
    _inherit = 'account.journal.summary'

    filter_unfold_all = True

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
        return _('General Journal Report')

    def _get_report_name(self):
        return _("General Journal Report")

    def _get_templates(self):
        templates = super(AccountGeneralJournalSummary, self)._get_templates()
        templates['line_template'] = 'account_reports.line_template'
        return templates

    @api.model
    def _get_lines(self, options, line_id=None):
        AccountJournal = self.env['account.journal']
        context = self.env.context
        ctx_journal_ids = context.get('journal_ids')
        selected_partner_ids = context.get('partner_ids')
        partner_categories = context.get('partner_categories')
        date_from = context.get('date_from')
        date_to = context.get('date_to')
        unfold_all = context.get('print_mode') and not options.get('unfolded_lines', [])
        company_ids = parent_company_ids = self.env['res.company']
        tjournal = journal_ids = partner_ids2 = []
        lines = []

        # Get selected company
        if context.get('company_ids', False):
            comp_ids = context.get('company_ids')
            for comp_id in comp_ids:
                comp_id = self.env['res.company'].browse(comp_id)
                company_ids += comp_id

        AccountMoveLine = self.env['account.move.line']

        domain = [
            # ('move_id.type', '!=', 'entry'),
            ('date', '<=', date_to),
            ('date', '>=', date_from),
            ('parent_state', '=', 'posted'),
            ('company_id', 'child_of', company_ids.ids)]

        if selected_partner_ids:
            domain.append(('partner_id', 'in', selected_partner_ids.ids))
        if ctx_journal_ids:
            domain.append(('journal_id', 'in', ctx_journal_ids))
        if partner_categories:
            domain.append(('partner_id.category_id', 'in', partner_categories.ids))

        mv_line_ids = AccountMoveLine.search(domain, order='date asc')

        if line_id:
            line_id = int(line_id.split('_')[1]) or None
            journal_ids = AccountJournal.browse(line_id)

        elif options.get('partner_ids'):
            # If a default partner is set, we only want to load the line referring to it.
            partner_ids2 = options['partner_ids']
            domain = [
                ('type', '=', 'entry'),
                ('date', '<=', date_to), 
                ('date', '>=', date_from), 
                ('parent_state', '=', 'posted')]
            
            if partner_ids2:  
                domain.append(('partner_id', 'in', partner_ids2))
            if ctx_journal_ids:
                domain.append(('journal_id', 'in', ctx_journal_ids))
                
            mv_line_ids = AccountMoveLine.search(domain, order='date asc')
            journal_ids = mv_line_ids.mapped('journal_id')
        else:
            journal_ids = mv_line_ids.mapped('journal_id')

        if mv_line_ids:
            for journal_id in journal_ids:
                journal_debit = journal_credit = 0.00
                journal_mv_line_ids = mv_line_ids.filtered(lambda j: j.journal_id == journal_id)

                journal_debit = sum(journal_mv_line_ids.mapped('debit'))
                journal_credit = sum(journal_mv_line_ids.mapped('credit'))

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

                for line_id in journal_mv_line_ids:
                    if 'journal_' + str(journal_id.id) in options.get('unfolded_lines') or unfold_all:
                        columns = [
                            str(line_id.move_id.name),
                            str(line_id.ref or ''),
                            str(line_id.partner_id.name or ''),
                            str(line_id.name),
                            str(line_id.account_id.name),
                            self.format_value(line_id.debit),
                            self.format_value(line_id.credit),
                            str(line_id.analytic_account_id.name or ''),
                            str(line_id.full_reconcile_id.name or ''),
                            self.format_value(line_id.amount_currency),
                        ]

                        lines.append({
                            'id': 'move_' + str(line_id.id),
                            'type': 'line',
                            'name': line_id.date,
                            'class': 'date',
                            'columns': [{'name': v} for v in columns],
                            'parent_id': 'journal_' + str(journal_id.id),
                            'colspan': 1,
                            'level': 3,
                            'unfoldable': False,
                        })
        return lines
