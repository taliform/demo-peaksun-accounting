# -*- coding: utf-8 -*-
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
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, datetime

WHT_AGENT_CATEG = [('prv', 'Private'),
                   ('govt', 'Government')]


class BirMonthlyEwtReturn(models.Model):
    _name = 'bir.monthly.ewt.return'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'BIR 1601-EQ'

    _QUARTER = [
        ('1', '1st Quarter'),
        ('2', '2nd Quarter'),
        ('3', '3rd Quarter'),
        ('4', '4th Quarter')
    ]

    @api.depends('bir_1601e_line.tax_withheld')
    def _get_total_tax_withheld(self):
        total_wth = 0.00
        map_line_ids = self.bir_1601e_line.mapped('tax_withheld')
        for rec in map_line_ids:
            total_wth += rec
        self.total_tax_wth_printout = total_wth
        self.total_tax_wth = total_wth

        return True

    @api.depends('tax_remit_prev', 'adv_payments', 'first_month_quarter', 'second_month_quarter', 'over_remit_prev', 'other_payments')
    def _get_total_tax_cr(self):
        self.total_tax_cr = self.tax_remit_prev + self.adv_payments + self.first_month_quarter + self.second_month_quarter + self.over_remit_prev + self.other_payments
        return True
    
    @api.depends('total_tax_wth', 'total_tax_cr')
    def _get_tax_still_due(self):
        self.tax_due = self.total_tax_wth - self.total_tax_cr
        return True
    
    @api.depends('tax_due', 'surcharge', 'interest', 'compromise')
    def _get_total_amt_due(self):
        self.total_amt_due = self.tax_due + (self.surcharge + self.interest + self.compromise)
        return True

    def _get_company_id(self):
        """
        @summary: This will default Company Id on the form by
        getting the attached company_id of the current User. 
        """
        user_id = self.env.uid
        company_id = self.env['res.users'].browse(user_id).company_id.id
        return company_id
    
    @api.depends('company_id')
    def _get_address(self):
        address = ""
        for rec in self:
            company = rec.company_id
            if not company: self.company_address =  False
            else:
                if company.street: address += company.street
                if company.street2: address += ' ' + company.street2
                if company.city:
                    city = company.city
                    if 'city' in city or 'City' in city: address += ' ' + city
                    else: address += ' ' + city + ' City'
                if company.state_id: address += ' - ' + company.state_id.name
                rec.company_address = address

    name = fields.Char('Reference No.', track_visibility='onchange')
    period_from = fields.Date(string='From', track_visibility='onchange')
    period_to = fields.Date(string='To', track_visibility='onchange')    
    amended_return = fields.Boolean('Amended Return', track_visibility='onchange')
    no_of_sheet = fields.Char('No. of Sheet Attached', size=2, track_visibility='onchange')
    any_taxes_wth = fields.Boolean('Any Taxes Withheld?', track_visibility='onchange')
    company_id = fields.Many2one('res.company', string='Employer', default=_get_company_id, track_visibility='onchange')
    company_tin = fields.Char('TIN', related='company_id.vat', store=True)
    company_business_type = fields.Char('Business Type', related="company_id.partner_id.business_id.name")
    company_email = fields.Char('Email', related='company_id.email')
    company_phone = fields.Char('Phone No.', related='company_id.phone')
    company_street = fields.Char(related='company_id.street', string='Address', store=True)
    company_street2 = fields.Char(related='company_id.street2', store=True)
    company_city = fields.Char(related='company_id.city', store=True)
    company_state = fields.Char(related='company_id.state_id.name', store=True)
    company_zip_code = fields.Char('ZIP Code', related="company_id.zip", store=True)    
    company_address = fields.Text("Employer's Address", compute='_get_address', store=True)
    rdo_code = fields.Char(related='company_id.rdo_code', store=True)
    wth_agt_categ = fields.Selection(selection=WHT_AGENT_CATEG, string='Withholding Agent Category', track_visibility='onchange')
    spec_law = fields.Boolean('Special Law?', track_visibility='onchange')
    spec_txt = fields.Text('Specify Text', track_visibility='onchange')
    bir_1601e_line = fields.One2many('bir.monthly.ewt.return.line.printout', 'bir1601e_id')
    line_details_1601 = fields.One2many('bir.monthly.ewt.return.line', 'bir1601e_id', 'BIR 1601-EQ Line')
    total_tax_wth = fields.Float('Total Tax Required to be Withheld and Remitted', compute='_get_total_tax_withheld', store=True,
                                           track_visibility='onchange')
    total_tax_wth_printout = fields.Float(track_visibility='onchange')
    tax_remit_prev = fields.Float('Tax Remitted in Return Previously Filed')
    adv_payments = fields.Float('Advance Payments Made', track_visibility='onchange')
    first_month_quarter = fields.Float('1st Month Quarter', track_visibility='onchange')
    second_month_quarter = fields.Float('2nd Month Quarter', track_visibility='onchange')
    over_remit_prev = fields.Float('Over-remittance from Previous Quarter of the same taxable year', track_visibility='onchange')
    other_payments = fields.Float('Other Payments Made', track_visibility='onchange')
    total_tax_cr = fields.Float('Total Tax Credits/Payments', compute='_get_total_tax_cr', store=True, track_visibility='onchange')
    tax_due = fields.Float('Tax Still Due/(Overremittance)', compute='_get_tax_still_due', store=True, track_visibility='onchange')
    total_amt_due = fields.Float('Total Amount Still Due/(Overremittance)', compute='_get_total_amt_due', store=True, track_visibility='onchange')
    surcharge = fields.Float('Surcharge', track_visibility='onchange')
    interest = fields.Float('Interest', track_visibility='onchange')
    compromise = fields.Float('Compromise', track_visibility='onchange')
    auth_rep = fields.Many2one(related='company_id.authorized_rep_id', store=True, string='Authorized Representative', track_visibility='onchange')
    move_line_ids = fields.Many2many('account.move.line', string='Journal Items', copy=False)
    quarter = fields.Selection(_QUARTER, default='1', copy=False, string='Quarter')
    quarter_err = fields.Boolean(default=False)
    quarter_dates = {
        '1': ['-01-01', '-03-31'],
        '2': ['-04-01', '-06-30'],
        '3': ['-07-01', '-09-30'],
        '4': ['-10-01', '-12-31']
    }
    current_year = date.today().year
    date_validation_msg = fields.Char()

    @api.model
    def create(self, values):
        '''
        @summary: This will add a reference number for every created record.
        '''
        ref_name = self.env['ir.sequence'].get('bir.1601e.ref')
        values['name'] = ref_name
        return super(BirMonthlyEwtReturn, self).create(values)

    @api.onchange('no_of_sheet')
    def _onchange_numbers(self):
        if self.no_of_sheet and not self.no_of_sheet.isdigit():
            self.no_of_sheet = ''
            return {
                'warning': {
                    'title': _('Warning'),
                    'message': _('Invalid No. of Sheet Attached Format. Only numbers will accept.')
                }
            }

    @api.onchange('quarter')
    def _onchange_quarter(self):
        self.period_from = f'{self.current_year}{self.quarter_dates[self.quarter][0]}'
        self.period_to = f'{self.current_year}{self.quarter_dates[self.quarter][1]}'

    @api.onchange('period_from', 'period_to')
    def _onchange_period(self):
        date_from = self.convert_str_to_date(f'{self.period_from.year}{self.quarter_dates[self.quarter][0]}').date()
        date_to = self.convert_str_to_date(f'{self.period_to.year}{self.quarter_dates[self.quarter][1]}').date()
        quarter_string = dict(self._fields['quarter'].selection).get(self.quarter)
        self.date_validation_msg = ''
        if not date_from <= self.period_from <= date_to:
            self.quarter_err = True
            self.date_validation_msg += f'Period From not in {quarter_string}! '

        if not date_from <= self.period_to <= date_to:
            self.quarter_err = True
            self.date_validation_msg += f'Period To not in {quarter_string}!'
        elif date_from <= self.period_from <= date_to \
                and date_from <= self.period_to <= date_to:
            self.quarter_err = False

    @api.constrains('period_from', 'period_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_validation_msg:
                raise ValidationError(f'{self.date_validation_msg }')
            if rec.period_from.year != rec.period_to.year:
                raise ValidationError('Invalid Period Range. Both "Period From" and "Period To" does not belong on '
                                        'the same period of the year. Please check your date values before saving.')

    def convert_str_to_date(self, date_str):
        return datetime.strptime(date_str, '%Y-%m-%d')

    def generate(self):
        '''
        @summary: This will generate a BIR 1601-E Line records based on the ATC from journal entry lines. 
        '''
        AccountMoveLine = self.env['account.move.line']
        AccountTax = self.env['account.tax']
        date_from = self.period_from
        date_to = self.period_to
        company = self.env.user.company_id
        
        # Delete the BIR 1601E line first is the list has content to avoid duplicates.
        if len(self.line_details_1601) != 0:
            self.line_details_1601.unlink()
            self.bir_1601e_line.unlink()

        if len(self.company_tin) < 17:
            raise ValidationError('Company TIN must be 17 characters.')

        domain = [('date', '<=', date_to),
                  ('date', '>=', date_from),
                  ('move_id.state', '!=', 'draft'),
                  ('move_id.type', 'in', ('in_invoice', 'in_refund', 'in_receipt')),
                  ('tax_ids', '!=', False)]
        move_line_ids = AccountMoveLine.search(domain)
        smart_button_domain = [('date', '<=', date_to),
                              ('date', '>=', date_from),
                              ('move_id.state', '!=', 'draft'),
                              ('move_id.type', 'in', ('in_invoice', 'in_refund', 'in_receipt')),
                              ('tax_line_id', '!=', False)]
        move_line_smart_ids = AccountMoveLine.search(smart_button_domain)
        withholding_2307_ids = company.withholding_2307_ids
        vendor_move_line_ids = move_line_ids.filtered(lambda r: r.tax_ids & withholding_2307_ids)
        self.move_line_ids = move_line_smart_ids.filtered(lambda r: r.tax_line_id & withholding_2307_ids)
        
        for vendor_id in vendor_move_line_ids.mapped('tax_ids'):
            bir1601e_line = []
            bir1601e_line_printout = []
            tax_base = tax_withheld = 0    
            sign = 1
            
            for move_line in vendor_move_line_ids:
                if move_line.move_id:
                    sign = -1 if move_line.move_id.type == 'in_refund' else 1
                for tax in move_line.tax_ids:
                    if tax.id == vendor_id.id:
                        tax_base += move_line.debit or move_line.credit * sign
            
            rate = vendor_id.amount / 100
            tax_withheld = tax_base * -(rate)
            if vendor_id in withholding_2307_ids:
                bir1601e_vals = {'bir1601e_id': self.ids[0],
                                             'nature_inc': vendor_id.description,
                                             'atc': vendor_id.name,
                                             'tax_base': tax_base,
                                             'tax_rate':  str(-(vendor_id.amount)) + '%',
                                             'tax_withheld': tax_withheld}
                bir1601e_line.append((0, 0, bir1601e_vals))
                bir1601e_line_printout.append((0, 0, bir1601e_vals))
            # Set one2many values.
            if len(self.bir_1601e_line) <= 5:
                self.write({'bir_1601e_line': bir1601e_line_printout})
            self.write({'line_details_1601': bir1601e_line})
            self._get_total_amt_due()
            self._get_tax_still_due()
            self._get_total_tax_cr()
        return True

    def action_view_entry(self):
        action = self.env.ref('account.action_move_line_select_tax_audit')
        result = action.read()[0]
        result['context'] = {}
        
        if len(self.move_line_ids) > 1:
            result['domain'] = "[('id', 'in', " + str(self.move_line_ids.ids) + ")]"
        else:
            res = self.env.ref('account.view_move_line_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = self.move_line_ids.id or False
        return result

    def print_1601e(self):
        return self.env.ref('tf_ph_bir.report_bir_1601e').report_action(self)


class BirMonthlyEwtReturnLine(models.Model):
    _name = 'bir.monthly.ewt.return.line'
    _description = 'BIR 1601-EQ Line'
    
    bir1601e_id = fields.Many2one('bir.monthly.ewt.return', 'BIR 1601-EQ')
    nature_inc = fields.Char('Nature of Income Payment')
    atc = fields.Char('ATC')
    tax_base = fields.Float('Tax Base')
    tax_rate = fields.Char('Tax Rate')
    tax_withheld = fields.Float('Tax Required to be Withheld')


class BirMonthlyEwtReturnLinePrintout(models.Model):
    _name = 'bir.monthly.ewt.return.line.printout'

    bir1601e_id = fields.Many2one('bir.monthly.ewt.return', 'BIR 1601-EQ')
    nature_inc = fields.Char('Nature of Income Payment')
    atc = fields.Char('ATC')
    tax_base = fields.Float('Tax Base')
    tax_rate = fields.Char('Tax Rate')
    tax_withheld = fields.Float('Tax Required to be Withheld')