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
from math import copysign

from odoo import models, api, fields, _, release
from datetime import datetime
import json


class AccountAlphalistSawt(models.Model):
    _inherit = 'account.alphalist.sawt'
    
    filter_reconciled = True

    @api.model
    def _get_lines(self, options, line_id=None):
        AccountMoveLine = self.env['account.move.line']
        ResPartner = self.env['res.partner']
        context = self.env.context
        date_from = context.get('date_from')
        date_to = context.get('date_to')
        return_period = datetime.strptime(date_from, '%Y-%m-%d').strftime('%m/%Y')
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
        
        domain = [['date', '<=',date_to],
                  ['date', '>=',date_from],
                  ['tax_line_id', '!=', False],
                  '|',['move_id','=',False],
                  ['move_id.type','in',('out_invoice', 'out_refund', 'out_receipt')]]

        if options.get('reconciled'):
            domain += [('reconcile_id', '!=', False)]
    
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
            
        for partner_id in partner_ids:
            sawt_lines = []
            csv_data = []
            partner_move_line_ids = move_line_ids.filtered(lambda m: m.partner_id == partner_id)
            base_total = withheld_total = 0.0

            if partner_move_line_ids:
                taxes = []
                
                for tax_id in partner_move_line_ids.filtered(lambda v:v.tax_line_id.type_tax_use == 'sale' and v.tax_line_id.amount < 0.0).mapped('tax_line_id'):                   
                    tax_base_total = tax_withheld_total = 0.0

                    for tax_move_line_id in partner_move_line_ids.filtered(lambda l: l.tax_line_id == tax_id):
                        if tax_move_line_id.company_id.id in company_ids.ids:
                            #For invoice line tax withheld
                            tax_withheld = tax_move_line_id.debit or (tax_move_line_id.credit * -1.0)
                            tax_id = tax_move_line_id.tax_line_id
                            
                            #Look for the Tax Base
                            tax_base = 0.0
                            base_aml_ids = tax_move_line_id.move_id.line_ids.filtered(lambda l: l.tax_ids & tax_id and l.move_id)
                            if base_aml_ids:
                                for base_aml_id in base_aml_ids:
                                    tax_base +=  base_aml_id.credit or -(base_aml_id.debit)
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
                                    tax_id.name,
                                    str(-(tax_id.amount)) + '%',
                                    self.format_value(tax_base),
                                    self.format_value(tax_withheld)]]
                                
                                caret_type = 'account.move'

                                partner_data = {
                                        'id': tax_move_line_id.id,
                                        'type': 'move_line_id',
                                        'caret_options': caret_type,
                                        'class': 'top-vertical-align',
                                        'move_id': tax_move_line_id.move_id.id,
                                        'parent_id': 'partner_' + str(partner_id.id),
                                        'name': tax_move_line_id.move_id.name,
                                        'first_name': tax_move_line_id.move_id.partner_id.first_name,
                                        'middle_name': tax_move_line_id.move_id.partner_id.middle_name,
                                        'last_name': tax_move_line_id.move_id.partner_id.last_name,
                                        'vat_payee': tax_move_line_id.move_id.partner_id.vat,
                                        'registered_payee_name': tax_move_line_id.move_id.partner_id.name,
                                        'columns': columns,
                                        'level': 3,
                                    }
                                csv_data.append(partner_data)
                                if 'partner_' + str(partner_id.id) in options.get('unfolded_lines') or unfold_all:   
                                    if tax_id.name not in taxes or not taxes:
                                        sawt_lines.append({
                                            'id': 'initial_%s' % (partner_id.id),
                                            'class': 'o_account_reports_initial_balance',
                                            'name': "ATC - %s"%tax_id.description,
                                            'parent_id': 'partner_%s' % (partner_id.id,),
                                            'columns': [{'name': v} for v in ['', '', '']],
                                            'level': 3,
                                        })
                                        taxes.append(tax_id.name)
                                    sawt_lines.append(partner_data)
                            
                    #Total per Partner
                    base_total += tax_base_total
                    withheld_total += tax_withheld_total
                    if 'partner_' + str(partner_id.id) in options.get('unfolded_lines') or unfold_all:   
                        if (tax_base_total + tax_withheld_total) or sawt_lines:
                            sawt_lines.append({
                                'id': 'total_' + str(tax_move_line_id.account_id.id),
                                'type': 'o_account_reports_domain_total',
                                'class': 'total',
                                'name': _('Total') + ': ' + tax_id.name,
                                'parent_id': 'partner_' + str(partner_id.id),
                                'columns': [{'name': v} for v in ['', '', '', '', self.format_value(tax_base_total), self.format_value(tax_withheld_total)]],
                                'level': 4,
                            })
                
                if (base_total + withheld_total) or sawt_lines:
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
                
            lines += sawt_lines
            csv_details_data += csv_data

        options['line_details_header'] = lines
        options['line_details_data'] = csv_details_data
        return lines
