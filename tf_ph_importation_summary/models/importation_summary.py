# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# v13 Porting: Bamboo <martin@taliform.com>
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
from odoo import models, fields, api, _
from odoo.tools.misc import formatLang
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as OE_DFORMAT
from datetime import datetime


class AccountImportationSummary(models.AbstractModel):
    _name = 'account.importation.summary'
    _inherit = 'account.report'
    _description = "Summary List of Importation Report"

    filter_date = {'date_from': '', 'date_to': '', 'filter': 'this_year'}
    filter_unfold_all = True
    filter_partner = True

    def _get_company_id(self):
        """
        @summary: This will default Company Id on the form by
        getting the attached company_id of the current User. 
        """
        user_id = self.env.uid
        company_id = self.env['res.users'].browse(user_id).company_id.id
        return company_id

    company_id = fields.Many2one('res.company', string='Company', default=_get_company_id, track_visibility='onchange')

    def _format(self, value):
        if self.env.context.get('no_format'):
            return value
        currency_id = self.env.user.company_id.currency_id
        if currency_id.is_zero(value):
            # don't print -0.0 in reports
            value = abs(value)
        res = formatLang(self.env, value, currency_obj=currency_id)
        return res

    def _get_templates(self):
        templates = super(AccountImportationSummary, self)._get_templates()
        templates['line_template'] = 'account_reports.line_template'
        return templates

    def _get_columns_name(self, options):
        return [
            {},
            {'name': _('Reference'), 'class': 'text'},
            {'name': _('Import Entry Declaration Number'), 'class': 'text'},
            {'name': _('Assessment/Release Date'), 'class': 'text'},
            {'name': _('Date of Importation'), 'class': 'text'},
            {'name': _('Vendor'), 'class': 'text'},
            {'name': _('Country of Origin'), 'class': 'text'},
            {'name': _('Dutiable Value (PHP)'), 'class': 'number'},
            {'name': _('All Charges'), 'class': 'number'},
            {'name': _('Landed Cost'), 'class': 'number'},
            {'name': _('Taxable'), 'class': 'number'},
            {'name': _('Exempt'), 'class': 'number'},
            {'name': _('VAT Paid'), 'class': 'number'},
            {'name': _('OR #'), 'class': 'text'},
            {'name': _('Date of VAT Payment'), 'class': 'text'},
        ]

    @api.model
    def _get_report_name(self):
        return _('Summary List of Importation')

    @api.model
    def get_month(self, string_date):
        return datetime.strptime(str(string_date), OE_DFORMAT).month

    @api.model
    def _get_lines(self, options, line_id=None):
        ResPartner = self.env['res.partner']
        StockLandedCost = self.env['stock.landed.cost']
        context = self.env.context
        date_from = context.get('date_from')
        date_to = context.get('date_to')
        unfold_all = context.get('print_mode') and not options.get('unfolded_lines', [])
        lines = []
        company_ids = self.env['res.company']
        partner_ids = partner_ids2 = []

        month_list = {
            1: 'January',
            2: 'February',
            3: 'March',
            4: 'April',
            5: 'May',
            6: 'June',
            7: 'July',
            8: 'August',
            9: 'September',
            10: 'October',
            11: 'November',
            12: 'December'}

        # Get selected company
        if context.get('company_ids', False):
            comp_ids = context.get('company_ids')
            for comp_id in comp_ids:
                comp_id = self.env['res.company'].browse(comp_id)
                company_ids += comp_id

        domain = [('state', '=', 'done'),
                  ('date', '<=', date_to),
                  ('date', '>=', date_from),
                  ('company_id', 'child_of', company_ids.ids),
                  ('local_boolean', '=', False)]

        lc_ids = StockLandedCost.search(domain)

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
            partner_ids = lc_ids.mapped('partner_id')

        if lc_ids:
            for partner_id in partner_ids:
                partner_lines = []
                partner_dutiable_amt = partner_amount_taxable = partner_amount_exempt = partner_all_charges = partner_vat_paid = partner_total_amount = 0.0
                partner_lc_ids = lc_ids.filtered(lambda l: l.partner_id == partner_id)

                # Go through all months
                for month_index in range(1, 13):
                    month_dutiable_amt = month_amount_taxable = month_amount_exempt = month_all_charges = month_vat_paid = month_total_amount = 0.0
                    month_lc_ids = partner_lc_ids.filtered(lambda p: self.get_month(p.date) == month_index)
                    month_lines = []

                    for month_lc_id in month_lc_ids:
                        lc_id = month_lc_id
                        if 'partner_' + str(partner_id.id) in options.get('unfolded_lines') or unfold_all:
                            month_lines.append({
                                'id': lc_id.id,
                                'type': 'landed_cost_id',
                                'lc_id': lc_id.id,
                                'parent_id': 'partner_%s' % (partner_id.id),
                                'action': ['stock.landed.cost', lc_id.id, _('View Landed Cost'),
                                           lc_id.get_formview_id()],
                                'name': '',
                                'columns': [{'name': v} for v in
                                            [lc_id.name, lc_id.import_number, str(lc_id.assessment_date or ''),
                                             str(lc_id.importation_date or ''), lc_id.partner_id.name,
                                             lc_id.country_id.name,
                                             self.format_value(lc_id.dutiable_amt),
                                             self.format_value(lc_id.all_charges),
                                             self.format_value(lc_id.total_amount),
                                             self.format_value(lc_id.amount_taxable),
                                             self.format_value(lc_id.amount_exempt), self.format_value(lc_id.vat_paid),
                                             lc_id.official_receipt, str(lc_id.vat_payment_date or ''),
                                             ]],
                                'colspan': 1,
                                'level': 3,
                            })

                        # Sum Totals for the month
                        month_dutiable_amt += month_lc_id.dutiable_amt
                        month_amount_taxable += month_lc_id.amount_taxable
                        month_amount_exempt += month_lc_id.amount_exempt
                        month_all_charges += month_lc_id.all_charges
                        month_vat_paid += month_lc_id.vat_paid
                        month_total_amount += month_lc_id.total_amount

                    if 'partner_' + str(partner_id.id) in options.get('unfolded_lines') or unfold_all:
                        if (
                                month_dutiable_amt + month_amount_taxable + month_amount_exempt + month_all_charges + month_vat_paid + month_total_amount):
                            month_name = _(month_list.get(month_index))
                            month_lines[:0] = [{
                                'id': partner_id.id,
                                'type': 'initial_balance',
                                'name': month_name,
                                'parent_id': 'partner_' + str(partner_id.id),
                                'columns': [{'name': v} for v in
                                            ['', '', '', '', '', '', '', '', '', '', '', '', '', '']],
                                'level': 4,
                            }]

                            month_lines.append({
                                'id': partner_id.id,
                                'type': 'o_account_reports_domain_total',
                                'name': '%s Total' % (month_name),
                                'parent_id': 'partner_' + str(partner_id.id),
                                'columns': [{'name': v} for v in ['', '', '', '', '', '',
                                                                  self.format_value(month_dutiable_amt),
                                                                  self.format_value(month_all_charges),
                                                                  self.format_value(month_total_amount),
                                                                  self.format_value(month_amount_taxable),
                                                                  self.format_value(month_amount_exempt),
                                                                  self.format_value(month_vat_paid), '', '']],
                                'level': 4,
                            })
                    partner_dutiable_amt += month_dutiable_amt
                    partner_amount_taxable += month_amount_taxable
                    partner_amount_exempt += month_amount_exempt
                    partner_all_charges += month_all_charges
                    partner_vat_paid += month_vat_paid
                    partner_total_amount += month_total_amount

                    partner_lines += month_lines

                # Create Partner Lines
                if partner_dutiable_amt + partner_amount_taxable + partner_amount_exempt + partner_all_charges + partner_vat_paid:
                    partner_vat = 'TIN: ' + partner_id.vat if partner_id.vat else ''
                    address = 'Address: ' + partner_id.with_context({'show_address_only': True}).name_get()[0][
                        1].replace('\n', ', ') if partner_id.street else ''
                    lines.append({
                        'id': 'partner_' + str(partner_id.id),
                        'type': 'line',
                        'name': partner_id.name,
                        'columns': [{'name': v} for v in ['', '', '', '', '', '',
                                                          self.format_value(partner_dutiable_amt),
                                                          self.format_value(partner_all_charges),
                                                          self.format_value(partner_total_amount),
                                                          self.format_value(partner_amount_taxable),
                                                          self.format_value(partner_amount_exempt),
                                                          self.format_value(partner_vat_paid), '', '']],
                        'level': 2,
                        'unfoldable': True,
                        'unfolded': 'partner_' + str(partner_id.id) in options.get('unfolded_lines') or unfold_all,
                        'colspan': 1,
                    })
                    if 'partner_' + str(partner_id.id) in options.get('unfolded_lines') or unfold_all:
                        if address:
                            lines.append({
                                'id': 'initial_%s' % (partner_id.id),
                                'type': 'initial_balance',
                                'name': address,
                                'parent_id': 'partner_%s' % (partner_id.id),
                                'columns': [{'name': v} for v in
                                            ['', '', '', '', '', '', '', '', '', '', '', '', '', '']],
                                'level': 3,
                            })
                        if partner_vat:
                            lines.append({
                                'id': 'initial_%s' % (partner_id.id),
                                'type': 'initial_balance',
                                'name': partner_vat,
                                'parent_id': 'partner_%s' % (partner_id.id),
                                'columns': [{'name': v} for v in
                                            ['', '', '', '', '', '', '', '', '', '', '', '', '', '']],
                                'level': 3,
                            })
                lines += partner_lines

        #         else: raise ValidationError(('No existing Landed Cost records for the selected period.'))
        return lines
