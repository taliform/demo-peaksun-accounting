# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2019 Synersys Consulting Inc.
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
from odoo import models, api, fields, _
from datetime import datetime
import json

class AccountAlphalistMap(models.Model):
    _name = 'account.alphalist.map'
    _description = 'Monthly Alphalist Payees'
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
        return _('Quarterly Alphalist Payees')

    @api.model
    def _get_report_name(self):
        return _('Quarterly Alphalist Payees')

    @api.model
    def get_report_type(self):
        return self.env.ref('tf_ph_bir.account_report_type_alphalist_map')
    
    def _get_templates(self):
        templates = super(AccountAlphalistMap, self)._get_templates()
        templates['line_template'] = 'tf_ph_bir.line_template_alphalist_map_report'
        return templates
    
    def _get_columns_name(self, options):
        columns = [
            {},
            {'name': _('Date'), 'class': 'date'},
            {'name': _('Return Period')},
            {'name': _('Journal')},
            {'name': _('Nature of Income Payment')},
            {'name': _('Tax Rate')},
            {'name': _('Tax Base'), 'class': 'number'},
            {'name': _('Tax Withheld'), 'class': 'number'}]

        return columns

    @api.model
    def get_company_data(self):
        user_id = self.env.uid
        company = self.env['res.users'].browse(user_id).company_id;
        company_data ={
            "company_tin": company.vat.replace("-", "")[0:9],
            "company_name": company.name,
            "date": f'{datetime.now().month}{datetime.now().year}'
        }

        return company_data

    @api.model
    def get_csv(self, options):
        alpha_type = 'MAP'
        ftype_code = '1601E'
        file_content = ''
        user_id = self.env.uid
        user_data = self.env['res.users'].browse(user_id)
        company = user_data.company_id
        company_name = company.name.upper() or ''
        company_vat = company.vat.replace('-', '')
        company_tin = company_vat[0:9] or ''
        company_branch_code = company_vat[9:13] or ''
        company_rdo_code = company.rdo_code
        company_data = list(filter(lambda data: data['level'] == 2, options['line_details_header']))
        return_period = datetime.now().strftime('%m/%Y')
        header_details = f"H{alpha_type}," \
                         f"H{ftype_code}," \
                         f"{company_tin}," \
                         f"{company_branch_code}," \
                         f'"{company_name}",' \
                         f"{return_period}," \
                         f"{company_rdo_code}\n"
        file_content += header_details
        total_amount_withheld = 0.0
        total_tax_base = 0.0
        seq = 0
        for detail in company_data:
            seq += 1
            detail_tin = '000-000-000'
            if detail['vat']:
                detail_tin = str(detail['vat']).replace('-', '')[0:9]
                detail_rdo = str(detail['vat']).replace('-', '')[9:13]

            atc = detail['company_details'][2]['name'].replace(' ', '')[0:5]
            tax_rate = format(float(detail['company_details'][3]['name']), '.2f')
            tax_base = detail['columns'][5]['name'].replace(',', '').replace(' Php', '').replace('$ ', '')
            actual_amt_wthld = detail['columns'][6]['name'].replace(',', '').replace(' Php', '').replace('$ ', '')

            first_name = detail['first_name'].upper() if detail['first_name'] else ''
            middle_name = detail['middle_name'].upper() if detail['middle_name'] else ''
            last_name = detail['last_name'].upper() if detail['last_name'] else ''

            detail_content = f'D{alpha_type},' \
                             f'D{ftype_code},' \
                             f'{seq},' \
                             f'{detail_tin},' \
                             f'{detail_rdo},' \
                             f'"{str(detail["name"]).upper()}",'\
                             f"{first_name},"\
                             f"{middle_name}," \
                             f"{last_name}," \
                             f"{return_period}," \
                             f"{atc}," \
                             f"{tax_rate}," \
                             f"{tax_base}," \
                             f"{actual_amt_wthld}\n"
            total_amount_withheld += float(actual_amt_wthld)
            total_tax_base += float(tax_base)
            file_content += detail_content


        control_details = f"C{alpha_type}," \
                          f"C{ftype_code}," \
                          f"{company_tin}," \
                          f"{company_branch_code},"\
                          f"{return_period}," \
                          f"{format(total_tax_base, '.2f')},"\
                          f"{format(total_amount_withheld, '.2f')}\n"

        file_content += control_details

        return file_content

    def get_report_filename(self, options):
        """The name that will be used for the file when downloading pdf,xlsx,..."""
        if 'export_csv' in options and options['export_csv']:
            options.pop('export_csv')
            company_data = self.get_company_data()
            return f"{company_data['company_tin']}{company_data['date']}1601E.dat"

        return self._get_report_name().lower().replace(' ', '_')

    def _get_reports_buttons(self):
        return [
            {'name': _('Print Preview'), 'sequence': 1, 'action': 'print_pdf', 'file_export_type': _('PDF')},
            {'name': _('Export (XLSX)'), 'sequence': 2, 'action': 'print_xlsx', 'file_export_type': _('XLSX')},
            {'name': _('Export (DAT.CSV)'), 'sequence': 3, 'action': 'tf_ph_bir_export_csv', 'file_export_type': _('CBS')},
            {'name': _('Save'), 'sequence': 10, 'action': 'open_report_export_wizard'},
        ]

    def tf_ph_bir_export_csv(self, options):
        options['export_csv'] = True
        action = {'type': 'ir_actions_account_report_download',
                  'name': 'testing.dat',
                  'data': {'model': self.env.context.get('model'),
                           'options': json.dumps(options),
                           'output_format': 'csv',
                           'financial_id': self.env.context.get('id'),
                           }
                  }
        return action


    @api.model
    def _get_taxwithheld(self, invoice_line, tax):
        return invoice_line.price_subtotal * -(tax.amount)

    @api.model
    def _get_lines(self, options, line_id=None):
        AccountMoveLine = self.env['account.move.line']
        ResPartner = self.env['res.partner']
        context = self.env.context
        date_from = context.get('date_from')
        date_to = context.get('date_to')
        unfold_all = context.get('print_mode') and not options.get('unfolded_lines')
        company_ids = self.env['res.company']
        partner_ids = partner_ids2 = []
        lines = []
        csv_details_data = []
        #Get selected company
        if context.get('company_ids', False):
            comp_ids = context.get('company_ids')
            for comp_id in comp_ids:
                comp_id = self.env['res.company'].browse(comp_id)
                company_ids += comp_id
                child_ids = self.env['res.company'].search([('parent_id','=',comp_id.id)])
                for child_id in child_ids: 
                    if child_id not in company_ids: company_ids += child_id

        domain = [('date', '<=', date_to),
                  ('date', '>=', date_from),
                  ('tax_line_id', '!=', False),
                  ('move_id.type', 'in', ('in_invoice', 'in_refund', 'in_receipt')),
                  ('move_id.state', '!=', 'draft')
                  ]
     
        move_line_ids = AccountMoveLine.search(domain)

        if line_id:
            line_id = int(line_id.split('_')[1]) or None
            if line_id: partner_ids = ResPartner.browse(line_id)
            
        elif options.get('partner_ids'):
            # If a default partner is set, we only want to load the line referring to it.
            partner_ids2 = options['partner_ids']
            for p_id in partner_ids2:
                p_id = ResPartner.browse(p_id)
                line_id = p_id.id
                if p_id not in partner_ids: partner_ids += p_id
                if line_id:
                    if 'partner_' + str(line_id) not in options.get('unfolded_lines', []):
                        options.get('unfolded_lines', []).append('partner_' + str(line_id))

            options.update({'partner_ids': list(dict.fromkeys(options['partner_ids']))})
        else:
            #Create partner list
            partner_ids = move_line_ids.mapped('partner_id')

        overall_tax_base = overall_tax_withheld = 0
        for partner_id in partner_ids:
            map_lines = []
            csv_data = []
            withholding_2306_ids = self.env['account.tax']
            withholding_2307_ids = self.env['account.tax']
            withholding_2307_ids = self.env['account.tax']

            for comp_id in company_ids:
                withholding_2306_ids += comp_id.withholding_2306_ids
                withholding_2307_ids += comp_id.withholding_2307_ids
                withholding_taxes = (withholding_2306_ids + withholding_2307_ids).filtered(lambda tax: tax.type_tax_use == 'purchase')
                
            partner_move_line_ids = move_line_ids.filtered(lambda m: m.partner_id == partner_id and m.tax_line_id in withholding_taxes)
            base_total = withheld_total = 0.0

            if partner_move_line_ids:
                taxes = []
                
                for tax_id in partner_move_line_ids.filtered(lambda v:v.tax_line_id in withholding_taxes).mapped('tax_line_id'):
                    if tax_id not in withholding_taxes:
                        continue
                    
                    tax_base_total = tax_withheld_total = 0.0
                    
                    for tax_move_line_id in partner_move_line_ids.filtered(lambda l: l.tax_line_id == tax_id):
                        if tax_move_line_id.company_id.id in company_ids.ids:
                            #For invoice line tax withheld
                            tax_withheld = (tax_move_line_id.debit * -1.0)  or tax_move_line_id.credit
                            tax_id = tax_move_line_id.tax_line_id

                            #Look for the Tax Base
                            tax_base = 0.0
                            base_aml_ids = tax_move_line_id.move_id.line_ids.filtered(lambda l: l.tax_ids & tax_id and l.move_id)
                            if base_aml_ids:
                                for base_aml_id in base_aml_ids:
                                    tax_base += base_aml_id.debit or -(base_aml_id.credit) 
                            else:
                                tax_base = tax_withheld / -(tax_id.amount / 100)
                                
                            #Total per Tax
                            tax_base_total += tax_base
                            tax_withheld_total += tax_withheld
                            
                            move_id = tax_move_line_id.move_id
                            return_period = datetime.strptime(str(move_id.date), '%Y-%m-%d').strftime('%m/%Y')
                            
                            if (tax_base + tax_withheld):
                                # Lines
                                columns = [{'name': v} for v in [
                                    tax_move_line_id.move_id.date,
                                    return_period,
                                    tax_move_line_id.move_id.journal_id.name,
                                    tax_id.name,
                                    str(-(tax_id.amount)) + '%',
                                    self.format_value(tax_base),
                                    self.format_value(tax_withheld)
                                ]]
    
                                caret_type = 'account.move'
                                partner_data = {
                                    'id': tax_move_line_id.id,
                                    'type': 'move_line_id',
                                    'caret_options': caret_type,
                                    'class': 'top-vertical-align',
                                    'move_id': tax_move_line_id.move_id.id,
                                    'parent_id': 'partner_' + str(partner_id.id),
                                    'name': tax_move_line_id.move_id.name,
                                    'vat_payee': tax_move_line_id.move_id.partner_id.vat,
                                    'registered_payee_name': tax_move_line_id.move_id.partner_id.name,
                                    'columns': columns,
                                    'level': 3,
                                }
                                csv_data.append(partner_data)
                                if 'partner_' + str(partner_id.id) in options.get('unfolded_lines') or unfold_all:
                                    if tax_id.name not in taxes or not taxes:
                                        map_lines.append({
                                            'id': 'initial_%s' % (partner_id.id),
                                            'class': 'o_account_reports_initial_balance',
                                            'name': "ATC - %s" % tax_id.description,
                                            'parent_id': 'partner_%s' % (partner_id.id,),
                                            'columns': [{'name': v} for v in ['', '', '', '', '', '', '']],
                                            'level': 3,
                                        })
                                        taxes.append(tax_id.name)
                                    map_lines.append(partner_data)

                    #Total per Partner
                    base_total += tax_base_total
                    withheld_total += tax_withheld_total
                    if 'partner_' + str(partner_id.id) in options.get('unfolded_lines') or unfold_all:      
                        if (tax_base_total + tax_withheld_total) or map_lines:
                            map_lines.append({
                                'id': 'total_' + str(tax_move_line_id.account_id.id),
                                'type': 'o_account_reports_domain_total',
                                'class': 'total',
                                'name': _('Total') + ': ' + tax_id.name,
                                'parent_id': 'partner_' + str(partner_id.id),
                                'columns': [{'name': v} for v in ['','', '', '', '', self.format_value(tax_base_total), self.format_value(tax_withheld_total)]],
                                'level': 4,
                            })
                    overall_tax_base += tax_base_total
                    overall_tax_withheld += tax_withheld_total
                            
                if (base_total + withheld_total) or map_lines:
                    #Partner Line
                    lines.append({
                            'id': 'partner_' + str(partner_id.id),
                            'name': partner_id.name,
                            'first_name': partner_id.first_name,
                            'middle_name': partner_id.middle_name,
                            'last_name': partner_id.last_name,
                            'vat': partner_id.vat,
                            'rdo': partner_id.rdo_code,
                            'columns': [{'name': v} for v in [
                                '',
                                '',
                                '',
                                '',
                                '',
                                self.format_value(base_total),
                                self.format_value(withheld_total)]],
                            'level': 2,
                            'return_period': return_period,
                            'unfoldable': True,
                            'unfolded': 'partner_' + str(partner_id.id) in options.get('unfolded_lines') or unfold_all,
                            'colspan': 1,
                            'company_details': [{'name': v} for v in [
                                tax_move_line_id.move_id.date,
                                return_period,
                                tax_id.name,
                                str(-(tax_id.amount)),
                            ]]
                        })

            lines += map_lines
            csv_details_data += csv_data

        if not line_id or partner_ids2:
            total_line = {
                'id': 'overall_map_partners_total',
                'name': _('Total'),
                'class': 'o_account_reports_domain_total',
                'level': 0,
                'columns': [{'name': ''}] * 5 +
                           [{'name': self.format_value(v)} for v in
                            [overall_tax_base,
                             overall_tax_withheld, ]],
            }
            lines.append(total_line)
        options['line_details_header'] = lines
        options['line_details_data'] = csv_details_data
        return lines
