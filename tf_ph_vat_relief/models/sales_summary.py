# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
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
from odoo import models, api, fields, _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as OE_DFORMAT
from datetime import datetime


class AccountSalesSummary(models.AbstractModel):
    _name = 'account.sales.summary'
    _description = 'Sales Summary Report'
    _inherit = 'account.report'

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

    @api.model
    def get_title(self):
        return _('Sales Summary')

    @api.model
    def _get_report_name(self):
        return _('Sales Summary')

    @api.model
    def get_report_type(self):
        return self.env.ref('tf_ph_vat_relief.account_report_type_sales_summary')

    def _get_templates(self):
        templates = super(AccountSalesSummary, self)._get_templates()
        templates['line_template'] = 'account_reports.line_template_partner_ledger_report'
        return templates

    def _get_columns_name(self, options):
        columns = [
            {},
            {'name': _('Total Sales    '), 'class': 'number'},
            {'name': _('Exempt'), 'class': 'number'},
            {'name': _('Zero Rated'), 'class': 'number'},
            {'name': _('Gross Taxable'), 'class': 'number'},
            {'name': _('Taxable (Net of VAT)'), 'class': 'number'},
            {'name': _('VAT Rate'), 'style': 'text-align:center'},
            {'name': _('Amount of Output Tax'), 'class': 'number'}]

        return columns

    @api.model
    def get_month(self, string_date):
        return datetime.strptime(string_date, OE_DFORMAT).month

    @api.model
    def get_paid_invoices(self, paid_invoice_ids, month_index):
        month_inv_ids = self.env['account.move']
        for inv_id in paid_invoice_ids:
            if inv_id.payment_ids.filtered(lambda p: self.get_month(str(p.payment_date)) == month_index):
                month_inv_ids += inv_id

        return month_inv_ids

    @api.model
    def _get_lines(self, options, line_id=None):
        AccountInvoice = self.env['account.move']
        ResPartner = self.env['res.partner']
        context = self.env.context
        date_from = context.get('date_from')
        date_to = context.get('date_to')
        unfold_all = options.get('unfolded_lines')
        company_ids = self.env['res.company']
        partner_ids = partner_ids2 = []
        lines = []

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
            12: 'December',
        }

        # Get selected company
        if context.get('company_ids', False):
            comp_ids = context.get('company_ids')
            for comp_id in comp_ids:
                comp_id = self.env['res.company'].browse(comp_id)
                company_ids += comp_id

        # Search for invoices
        invoice_ids = AccountInvoice.search([
            ('state', 'in', ['posted', 'cancel']),
            ('invoice_date', '<=', date_to),
            ('invoice_date', '>=', date_from),
            ('type', 'in', ('out_invoice', 'out_receipt', 'out_refund')),
            ('company_id', 'child_of', company_ids.ids),
            ('service_vat_ids', '=', False),
        ])

        svc_vat_ids = AccountInvoice.search([
            ('type', '=', 'entry'),
            ('date', '<=', date_to),
            ('date', '>=', date_from),
            ('svc_vat_id', '!=', False),
            ('vat_invoice_rel_id', '!=', False),
        ])

        invoice_ids = invoice_ids | svc_vat_ids.mapped('vat_invoice_rel_id').filtered(
            lambda s: s.type in ['out_invoice', 'out_receipt', 'out_refund'])

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

            options.update({
                'partner_ids': list(dict.fromkeys(options['partner_ids']))
            })
        else:
            # Create partner list
            partner_ids = invoice_ids.mapped('partner_id')

        for partner_id in partner_ids:
            # print("partner: ", partner_id.name)
            # Initialize
            partner_lines = []
            partner_exempt_total = partner_zero_rated_total = partner_taxable_total = \
                partner_gross_sales_total = partner_output_tax_total = partner_vat_total = 0.0

            # Filter Invoice Per Partner
            partner_invoice_ids = invoice_ids.filtered(lambda s: s.partner_id == partner_id)

            if partner_invoice_ids:
                # Go through all months
                for month_index in range(1, 13):
                    month_lines = []
                    month_name = month_added = False
                    month_exempt_total = month_zero_rated_total = month_taxable_total \
                        = month_gross_sales_total = month_output_tax_total = month_vat_total = 0.0

                    # Invoices that are not service vat
                    date_invoice_ids = partner_invoice_ids \
                        .filtered(lambda p: (self.get_month(str(p.invoice_date)) == month_index and
                                             not p.service_vat_ids))

                    # Invoices that are service vat and paid
                    for svc_inv_id in partner_invoice_ids.filtered(lambda p: p.service_vat_ids):
                        if svc_inv_id.mapped('payment_ids').filtered(
                                lambda p: self.get_month(str(p.payment_date)) == month_index):
                            date_invoice_ids = date_invoice_ids | svc_inv_id

                    # Get paid invoices with the payment date and month_index
                    paid_invoice_ids = self.get_paid_invoices(
                        partner_invoice_ids.filtered(lambda p: p.invoice_payment_state == 'paid'), month_index
                    )
                    month_invoice_ids = date_invoice_ids | paid_invoice_ids

                    # print("month_invoice_ids: ", month_invoice_ids)
                    for month_invoice_id in month_invoice_ids:
                        # print("invoice name: ", month_invoice_id.name)
                        exempt_total = zero_rated_total = taxable_total = gross_sales_total \
                            = output_tax_total = vat_total = 0.0
                        sign = -1 if month_invoice_id.type == 'out_refund' else 1
                        vat_tax_id = ''

                        # Filter out invoice lines without taxes as they arent reported to BIR
                        invoice_line_ids = month_invoice_id.invoice_line_ids.filtered(lambda l: l.tax_ids)

                        # Get Taxes (based from invoice's company_id)
                        vat_tax_ids = month_invoice_id.company_id.vat_tax_ids
                        withholding_2306 = month_invoice_id.company_id.withholding_2306_ids
                        withholding_2307 = month_invoice_id.company_id.withholding_2307_ids
                        vat_exempt_tax_ids = month_invoice_id.company_id.vat_exempt_tax_ids
                        zero_rated_tax_ids = month_invoice_id.company_id.zero_rated_tax_ids
                        withholding_tax_ids = (withholding_2306 + withholding_2307)
                        sales_withholding = self.env['account.tax'].search([
                            ('type_tax_use', '=', 'sale'),
                            ('for_withholding', '=', True)
                        ])
                        withholding_tax_ids += sales_withholding
                        # print("invoice_line_ids: ", invoice_line_ids)
                        for invoice_line_id in invoice_line_ids:
                            tax_id = invoice_line_id.tax_ids.filtered(lambda l: l not in withholding_tax_ids)
                            exempt = zr = vat = withheld = svt_partial = False

                            if tax_id and len(tax_id) == 1:
                                tax_amount = (tax_id._compute_amount(
                                    invoice_line_id.price_unit * invoice_line_id.quantity,
                                    invoice_line_id.price_unit,
                                    quantity=invoice_line_id.quantity
                                ) * sign)
                                subtotal = invoice_line_id.price_subtotal * sign
                                subtotal_mod = 0.0
                                tax_amount_mod = 0.0
                                svc_paid = False

                                if tax_id.is_service:
                                    # If Service Vat, Check if Service VAT is paid
                                    svc_payment_move_ids = month_invoice_id.service_vat_ids
                                    svc_month_pay_ids = svc_payment_move_ids.filtered(
                                        lambda s: self.get_month(str(s.date)) == month_index)
                                    svc_paid = month_invoice_id.state == 'posted' and svc_month_pay_ids
                                    if svc_paid:
                                        for svt_id in svc_month_pay_ids:
                                            payment_id = svt_id.line_ids.mapped('payment_id')
                                            output_tax_total += svt_id.line_ids.mapped('credit')[1]
                                            if payment_id:
                                                if payment_id.wht_tax_id:
                                                    payment_ratio = (
                                                            (payment_id.amount + payment_id.wht_amount)
                                                            / month_invoice_id.amount_total
                                                    )
                                                elif payment_id.payment_withholding_ids:
                                                    wht_amount = sum(
                                                        payment_id.payment_withholding_ids.mapped('wht_amount')
                                                    )
                                                    payment_ratio = (
                                                            (payment_id.amount + wht_amount)
                                                            / month_invoice_id.amount_total
                                                    )
                                                else:
                                                    payment_ratio = (
                                                            payment_id.amount
                                                            / month_invoice_id.amount_total
                                                    )
                                                subtotal_mod += payment_ratio * subtotal
                                                tax_amount_mod += payment_ratio * tax_amount
                                                svt_partial = True

                                    subtotal = subtotal_mod
                                    tax_amount = tax_amount_mod
                                gross_sales_total += subtotal
                                # print("gross_sales_total: ", gross_sales_total)

                                # Check if tax indicated in the invoice line is present in the
                                # user's company's vat exempt and zero rated taxes
                                if tax_id in vat_exempt_tax_ids:
                                    exempt = True
                                if tax_id in zero_rated_tax_ids:
                                    zr = True
                                if tax_id in withholding_tax_ids:
                                    withheld = True
                                if tax_id in vat_tax_ids or tax_id.is_service:
                                    vat = True

                                # If tax is present, do the necessary increments
                                if exempt:
                                    exempt_total += subtotal
                                elif zr:
                                    zero_rated_total += subtotal
                                elif vat:
                                    vat_total += subtotal
                                    if tax_id.amount > 0.0:
                                        vat_tax_id = str(tax_id.amount) + "%"
                                if not exempt and not zr and not withheld and not tax_id.is_service:
                                    taxable_total += subtotal + tax_amount
                                    output_tax_total += tax_amount
                                elif tax_id.is_service and svc_paid:
                                    taxable_total += subtotal * 1.12
                                    output_tax_total += tax_amount

                        # Month Lines
                        columns = [
                            {'name': v} for v in [
                                self.format_value(gross_sales_total),
                                self.format_value(exempt_total),
                                self.format_value(zero_rated_total),
                                self.format_value(taxable_total),
                                self.format_value(vat_total),
                                vat_tax_id,
                                self.format_value(output_tax_total)
                            ]
                        ]

                        caret_type = 'account.invoice.out'
                        # print("unfolded_lines: ", options.get('unfolded_lines'))
                        # print("unfold_all: ", unfold_all)
                        if unfold_all or 'partner_' + str(partner_id.id) in options.get('unfolded_lines'):
                            if (gross_sales_total + exempt_total + zero_rated_total
                                    + taxable_total + vat_total + output_tax_total):
                                # Month Name
                                month_name = _(month_list.get(month_index))
                                if not month_added:
                                    month_lines.append({
                                        'id': 'initial_%s' % str(month_invoice_id.id),
                                        'class': 'o_account_reports_initial_balance',
                                        'name': month_name,
                                        'parent_id': 'partner_%s' % (partner_id.id,),
                                        'columns': [{'name': v} for v in ['', '', '', '', '', '', '']],
                                        'level': 3,
                                    })
                                    month_added = True

                                # If invoice, 'id' should the move_line_id of the invoice
                                move_line_ids = self.env['account.move.line'].search([
                                    ('move_id', '=', month_invoice_id.id)
                                ])

                                month_lines.append({
                                    'id': move_line_ids[0].id,
                                    'caret_options': caret_type,
                                    'class': 'top-vertical-align',
                                    'parent_id': 'partner_' + str(partner_id.id),
                                    'name': month_invoice_id.display_name,
                                    'columns': columns,
                                    'level': 4,
                                })

                        # Sum Totals for the month
                        month_vat_total += vat_total
                        month_exempt_total += exempt_total
                        month_zero_rated_total += zero_rated_total
                        month_taxable_total += taxable_total
                        month_output_tax_total += output_tax_total
                        month_gross_sales_total += gross_sales_total

                    if 'partner_' + str(partner_id.id) in options.get('unfolded_lines') or unfold_all:
                        if (month_exempt_total + month_zero_rated_total
                            + month_taxable_total + month_gross_sales_total
                            + month_output_tax_total + month_vat_total) \
                                or month_lines:
                            # Total of Month Lines
                            columns = [
                                {'name': v} for v in [
                                    self.format_value(month_gross_sales_total),
                                    self.format_value(month_exempt_total),
                                    self.format_value(month_zero_rated_total),
                                    self.format_value(month_taxable_total),
                                    self.format_value(month_vat_total),
                                    '',
                                    self.format_value(month_output_tax_total)
                                ]
                            ]

                            # Month Name
                            month_name = _(month_list.get(month_index))
                            month_lines.append({
                                'id': 'total_' + str(month_invoice_id.id),
                                'type': 'o_account_reports_domain_total',
                                'class': 'total',
                                'name': _('Total') + ': ' + month_name,
                                'parent_id': 'partner_' + str(partner_id.id),
                                'columns': columns,
                                'level': 4,
                            })

                    partner_lines += month_lines

                    partner_vat_total += month_vat_total
                    partner_exempt_total += month_exempt_total
                    partner_zero_rated_total += month_zero_rated_total
                    partner_taxable_total += month_taxable_total
                    partner_gross_sales_total += month_gross_sales_total
                    partner_output_tax_total += month_output_tax_total

                if (partner_vat_total + partner_exempt_total + partner_zero_rated_total
                    + partner_taxable_total + partner_gross_sales_total
                    + partner_output_tax_total) \
                        or partner_lines:
                    # Partner Lines
                    columns = [
                        {'name': v} for v in [
                            self.format_value(partner_gross_sales_total),
                            self.format_value(partner_exempt_total),
                            self.format_value(partner_zero_rated_total),
                            self.format_value(partner_taxable_total),
                            self.format_value(partner_vat_total),
                            '',
                            self.format_value(partner_output_tax_total)
                        ]
                    ]

                    lines.append({
                        'id': 'partner_' + str(partner_id.id),
                        'name': partner_id.name,
                        'columns': columns,
                        'level': 2,
                        'unfoldable': True,
                        'unfolded': 'partner_' + str(partner_id.id) in options.get('unfolded_lines') or unfold_all,
                        'colspan': 1,
                    })
                    if 'partner_' + str(partner_id.id) in options.get('unfolded_lines') or unfold_all:
                        # First Line
                        partner_vat = 'TIN: ' + partner_id.vat if partner_id.vat else ''
                        address = 'Address: ' + partner_id.with_context({
                            'show_address_only': True
                        }).name_get()[0][1].replace('\n', ', ') if partner_id.street else ''

                        if address:
                            lines.append({
                                'id': 'initial_%s' % (partner_id.id,),
                                'class': 'o_account_reports_initial_balance',
                                'name': address,
                                'parent_id': 'partner_%s' % (partner_id.id,),
                                'columns': [{'name': v} for v in ['', '', '', '', '', '', '']],
                                'level': 3,
                            })
                        if partner_vat:
                            lines.append({
                                'id': 'initial_%s' % (partner_id.id,),
                                'class': 'o_account_reports_initial_balance',
                                'name': partner_vat,
                                'parent_id': 'partner_%s' % (partner_id.id,),
                                'columns': [{'name': v} for v in ['', '', '', '', '', '', '']],
                                'level': 3
                            })
            # print("partner_line: ", partner_lines)
            lines += partner_lines
        return lines
