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
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as OE_DFORMAT
from datetime import datetime


class AccountPartnerJournalSummary(models.AbstractModel):
    _name = 'account.partner.journal.summary'
    _description = 'Partner Journal Summary Report'
    _inherit = 'account.report'

    filter_date = {'date_from': '', 'date_to': '', 'filter': 'this_year'}
    filter_unfold_all = True
    filter_partner = True
    filter_journals = True

    # filter_journals_type = [{'id': 'sale', 'name': _('Sale'), 'type': 'sale', 'selected': False}, {'id': 'purchase', 'name': _('Purchase'), 'type': 'purchase', 'selected': False}]

    def _get_company_id(self):
        """
        @summary: This will default Company Id on the form by
        getting the attached company_id of the current User. 
        """
        user_id = self.env.uid
        company_id = self.env['res.users'].browse(user_id).company_id.id
        return company_id

    company_id = fields.Many2one('res.company', string='Company', default=_get_company_id, track_visibility='onchange')

    def _get_columns_name(self, options):
        columns = [
            {},
            {'name': _('Invoice Date'), 'class': 'date'},
            {'name': _('Due Date'), 'class': 'date'},
            {'name': _('Description'), 'class': 'text'},
            {'name': _('Reference/Document No./Invoice'), 'class': 'text'},
            {'name': _('Gross Amount'), 'class': 'number'},
            {'name': _('VAT'), 'class': 'number'},
            {'name': _('Net Sales (Net of VAT)'), 'class': 'number'},
            {'name': _('Amount Due'), 'class': 'number'},
            {'name': _('Status'), 'class': 'text'},
        ]
        return columns

    @api.model
    def get_month(self, string_date):
        return datetime.strptime(string_date, OE_DFORMAT).month

    @api.model
    def _get_lines(self, options, line_id=None):
        ResPartner = self.env['res.partner']
        context = self.env.context
        date_from = context.get('date_from')
        date_to = context.get('date_to')
        selected_partner_ids = context.get('partner_ids')
        partner_categories = context.get('partner_categories')
        ctx_journal_ids = context.get('journal_ids')
        journal_type = context.get('journal_type')
        unfold_all = context.get('print_mode') and not options.get('unfolded_lines', [])
        company_ids = self.env['res.company']
        lines = []

        month_list = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'}

        # Get selected company
        if context.get('company_ids', False):
            comp_ids = context.get('company_ids')
            for comp_id in comp_ids:
                comp_id = self.env['res.company'].browse(comp_id)
                company_ids += comp_id

        AccountInvoice = self.env['account.move']
        domain = [('state', 'in', ['posted', 'cancel']),
                  ('type', '!=', 'entry'),
                  ('invoice_date', '<=', date_to),
                  ('invoice_date', '>=', date_from),
                  ('journal_id.type', '=', journal_type),
                  ('company_id', 'child_of', company_ids.ids)]

        if selected_partner_ids:
            domain.append(('partner_id', 'in', selected_partner_ids.ids))
        if ctx_journal_ids:
            domain.append(('journal_id', 'in', ctx_journal_ids))
        if partner_categories:
            domain.append(('partner_id.category_id', 'in', partner_categories.ids))

        invoice_ids = AccountInvoice.search(domain)

        partner_ids = []
        if line_id:
            line_id = int(line_id.split('_')[1]) or None
            if line_id:
                partner_ids = ResPartner.browse(line_id)

        elif options.get('partner_ids'):
            # If a default partner is set, we only want to load the line referring to it.
            partner_ids2 = options['partner_ids']
            for p_id in partner_ids2:
                p_id = ResPartner.browse(p_id)
                line_id = p_id.id
                if p_id not in partner_ids:
                    partner_ids += p_id
                if line_id:
                    if 'partner_' + str(line_id) not in options.get('unfolded_lines', []):
                        options.get('unfolded_lines', []).append('partner_' + str(line_id))

            options.update({'partner_ids': list(dict.fromkeys(options['partner_ids']))})
        else:
            # Create partner list
            partner_ids = invoice_ids.mapped('partner_id')

        if invoice_ids:
            for partner_id in partner_ids:
                partner_lines = []
                partner_gross = partner_vat = partner_net = partner_due = 0.00
                partner_invoice_ids = invoice_ids.filtered(lambda inv: inv.partner_id == partner_id)

                if partner_invoice_ids:
                    # Go through all months
                    for month_index in range(1, 13):
                        month_lines = []
                        month_added = account_id = False
                        month_gross = month_vat = month_net = month_due = 0.0
                        month_name = _(month_list.get(month_index))
                        date_invoice_ids = partner_invoice_ids.filtered(
                            lambda p: self.get_month(str(p.invoice_date)) == month_index)

                        for invoice_id in date_invoice_ids:
                            # account_id = invoice_id.account_id.id
                            columns = [
                                str(invoice_id.invoice_date),
                                str(invoice_id.invoice_date_due),
                                invoice_id.name,
                                invoice_id.ref,
                                self.format_value(invoice_id.amount_untaxed + invoice_id.vat_tax),
                                self.format_value(invoice_id.vat_tax),
                                self.format_value(invoice_id.amount_untaxed),
                                self.format_value(invoice_id.amount_residual),
                                str(invoice_id.state).capitalize()]

                            # If invoice, 'id' should the move_line_id of the invoice
                            move_line_ids = self.env['account.move.line'].search([('move_id', '=', invoice_id.id)])
                            caret_type = 'account.invoice.in' if invoice_id.type in (
                            'in_refund', 'in_invoice') else 'account.invoice.out'
                            if 'partner_' + str(partner_id.id) in options.get('unfolded_lines') or unfold_all:
                                if not month_added:
                                    month_lines.append({
                                        'id': 'initial_%s' % str(invoice_id.id),
                                        'class': 'o_account_reports_initial_balance',
                                        'name': month_name,
                                        'parent_id': 'partner_%s' % (partner_id.id,),
                                        'columns': '',
                                        'level': 3,
                                    })
                                    month_added = True

                                month_lines.append({
                                    'id': move_line_ids[0].id,
                                    'name': str(invoice_id.name),
                                    'caret_options': caret_type,
                                    'columns': [{'name': v} for v in columns],
                                    'parent_id': 'partner_%s' % (partner_id.id),
                                    'colspan': 1,
                                    'level': 3,
                                })

                            month_gross += invoice_id.amount_untaxed + invoice_id.vat_tax
                            month_vat += invoice_id.vat_tax
                            month_net += invoice_id.amount_untaxed
                            month_due += invoice_id.amount_residual

                        if 'partner_' + str(partner_id.id) in options.get('unfolded_lines') or unfold_all:
                            if month_gross + month_vat + month_net + month_due:
                                # Total of Month Lines
                                columns = ['', '', '', '',
                                           self.format_value(month_gross),
                                           self.format_value(month_vat),
                                           self.format_value(month_net),
                                           self.format_value(month_due),
                                           '']

                                month_lines.append({
                                    'id': 'total_' + str(partner_id.name) or 0,
                                    'type': 'o_account_reports_domain_total',
                                    'class': 'total',
                                    'name': _('Total') + ': ' + month_name,
                                    'parent_id': 'partner_' + str(partner_id.id),
                                    'columns': [{'name': v} for v in columns],
                                    'level': 4,
                                })

                        partner_lines += month_lines

                        partner_gross += month_gross
                        partner_vat += month_vat
                        partner_net += month_net
                        partner_due += month_due

                    # Partner Lines
                    if partner_gross + partner_due:
                        partner_columns = ['', '', '', '',
                                           self.format_value(partner_gross),
                                           self.format_value(partner_vat),
                                           self.format_value(partner_net),
                                           self.format_value(partner_due),
                                           '']
                        lines.append({
                            'id': 'partner_' + str(partner_id.id),
                            'type': 'line',
                            'name': partner_id.name,
                            'columns': [{'name': v} for v in partner_columns],
                            'level': 2,
                            'unfoldable': True,
                            'unfolded': 'partner_' + str(partner_id.id) in options.get('unfolded_lines') or unfold_all,
                            'colspan': 1,
                        })

                    if 'partner_' + str(partner_id.id) in options.get('unfolded_lines') or unfold_all:
                        # First Line
                        partner_vat = 'TIN: ' + partner_id.vat if partner_id.vat else ''
                        address = 'Address: ' + partner_id.with_context({'show_address_only': True}).name_get()[0][
                            1].replace('\n', ', ') if partner_id.street else ''

                        if address:
                            lines.append({
                                'id': 'initial_%s' % (partner_id.id),
                                'class': 'o_account_reports_initial_balance',
                                'name': address,
                                'parent_id': 'partner_%s' % (partner_id.id,),
                                'columns': '',
                                'level': 3,
                            })
                        if partner_vat:
                            lines.append({
                                'id': 'initial_%s' % (partner_id.id),
                                'class': 'o_account_reports_initial_balance',
                                'name': partner_vat,
                                'parent_id': 'partner_%s' % (partner_id.id,),
                                'columns': '',
                                'level': 3
                            })

                    lines += partner_lines

        return lines
