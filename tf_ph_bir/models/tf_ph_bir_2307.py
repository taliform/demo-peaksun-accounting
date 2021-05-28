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
from datetime import datetime as dt

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as OE_DFORMAT

BIR_STATE = [
    ('draft', 'Draft'),
    ('validate', 'Validate')
]


class BirCreditableTaxWithheld(models.Model):
    _name = 'bir.creditable.tax.withheld'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'BIR 2307'

    def _set_state(self):
        """
        @summary: This will set the Address State for the Payee and Payor Information.
        """
        for rec in self:
            company_state_id = rec.company_id.state_id

            if company_state_id:
                rec.company_state = company_state_id.name
            else:
                rec.company_state = None

    def _get_company_id(self):
        """
        @summary: This will default Company Id on the form by
        getting the attached company_id of the current User. 
        """
        user_id = self.env.uid
        company_id = self.env['res.users'].browse(user_id).company_id.id
        return company_id

    @api.depends('partner_id')
    def _get_partner_address(self):
        address = ""
        for rec in self:
            partner = rec.partner_id
            if not partner:
                self.partner_address = False
            else:
                if partner.street:
                    address += partner.street
                if partner.street2:
                    address += ' ' + partner.street2
                if partner.city:
                    city = partner.city
                    if 'city' in city or 'City' in city:
                        address += ' ' + city
                    else:
                        address += ' ' + city + ' City'
                if partner.state_id:
                    address += ' - ' + partner.state_id.name
                rec.partner_address = address

    @api.depends('company_id')
    def _get_comp_address(self):
        address = ""
        for rec in self:
            company = rec.company_id
            if not company:
                self.company_address = False
            else:
                if company.street:
                    address += company.street
                if company.street2:
                    address += ' ' + company.street2
                if company.city:
                    city = company.city
                    if 'city' in city or 'City' in city:
                        address += ' ' + city
                    else:
                        address += ' ' + city + ' City'
                if company.state_id:
                    address += ' - ' + company.state_id.name
                rec.company_address = address

    state = fields.Selection(BIR_STATE, string='State', default='draft', track_visibility='onchange')
    period_from = fields.Date(string='From', track_visibility='onchange')
    period_to = fields.Date(string='To', track_visibility='onchange')
    partner_id = fields.Many2one('res.partner', string='Vendor', domain=[('vat', '!=', False)],
                                 help="Contains a list of Suppliers only with valid TIN.",
                                 track_visibility='onchange')
    partner_tin = fields.Char(string='Vendor TIN', related='partner_id.vat', store=True)
    partner_street = fields.Char(string='Vendor Address', related='partner_id.street', store=True)
    partner_street2 = fields.Char(string='Vendor Street 2', related='partner_id.street2', store=True)
    partner_city = fields.Char(string='Vendor City', related='partner_id.city', store=True)
    partner_zip = fields.Char(string='Vendor Zip', related='partner_id.zip', store=True)
    partner_state = fields.Char(compute='_get_state', store=True)
    partner_address = fields.Text("Partner Address", compute='_get_partner_address', store=True)
    foreign_address = fields.Text('Foreign Address', track_visibility='onchange')
    foreign_zip = fields.Char('Foreign ZIP Code', track_visibility='onchange')
    company_id = fields.Many2one('res.company', string='Company', default=_get_company_id, track_visibility='onchange')
    company_tin = fields.Char(string='TIN', related='company_id.vat', store=True)
    company_street = fields.Char(related='company_id.street', string='Address', store=True)
    company_street2 = fields.Char(related='company_id.street2', store=True)
    company_city = fields.Char(related='company_id.city', store=True)
    company_zip = fields.Char(related='company_id.zip', store=True)
    company_state = fields.Char(compute='_get_state', store=True)
    company_address = fields.Text("Employer's Address", compute='_get_comp_address', store=True)
    vat_only = fields.Boolean('Compute VAT Only')
    auth_rep = fields.Many2one(related='company_id.authorized_rep_id', store=True, string='Authorized Representative',
                               track_visibility='onchange')
    name = fields.Char('Reference No.', track_visibility='onchange')
    line_ids = fields.One2many('bir.creditable.tax.withheld.line', 'bir_cred_tax_with_id', string='BIR 2307 Line')
    line_ids2 = fields.One2many(string='BIR 2307 Line 2', related='line_ids')
    move_line_ids = fields.Many2many('account.move.line', relation='bir_2307_move_lines', string='Journal Entries',
                                     copy=False)
    move_line_ids2 = fields.Many2many('account.move.line', relation='bir_2307_move_lines2', string='Journal Entries 2',
                                      copy=False)
    amount_total1 = fields.Float('Total1', compute='_get_totals', copy=False)
    amount_total2 = fields.Float('Total2', compute='_get_totals', copy=False)
    amount_total3 = fields.Float('Total3', compute='_get_totals', copy=False)
    amount_grand_total = fields.Float('Grand Total', compute='_get_totals', copy=False)
    tax_withheld_total = fields.Float('Tax Withheld Total', compute='_get_totals', copy=False)

    def _get_totals(self):
        for rec in self:
            rec.amount_total1 = sum(rec.line_ids.mapped('total_1'))
            rec.amount_total2 = sum(rec.line_ids.mapped('total_2'))
            rec.amount_total3 = sum(rec.line_ids.mapped('total_3'))
            rec.amount_grand_total = sum(rec.line_ids.mapped('total'))
            rec.tax_withheld_total = sum(rec.line_ids.mapped('tax_withheld'))

    def unlink(self):
        # Prevent deletion of requests not in draft state
        if self.filtered(lambda rec: rec.state != 'draft'):
            raise ValidationError(_("You may only delete a BIR 2307 record in 'Draft' state."))
        res = super(BirCreditableTaxWithheld, self).unlink()
        return res

    def _get_date_ids(self, period_from, period_to):
        """
        @summary: Gets all the dates between the given 
        Period From and Period To dates.
        """
        start_date = dt.strptime(str(period_from), OE_DFORMAT)
        end_date = dt.strptime(str(period_to), OE_DFORMAT)

        date_diff = (end_date - start_date).days
        date_ids = []
        date_ids.append(period_from)

        for x in range(1, date_diff):
            date_id = start_date + relativedelta(days=x)
            date_ids.append(str(date_id.date()))

        date_ids.append(period_to)

        return date_ids

    def _get_month_quarter(self, month):
        """
        @summary: Returns the number of Quarter where the month belongs to.
        Quarter values ranges from 1 to 4.
        """
        quarter = 0
        if month in [1, 2, 3]:
            quarter = 1
        if month in [4, 5, 6]:
            quarter = 2
        if month in [7, 8, 9]:
            quarter = 3
        if month in [10, 11, 12]:
            quarter = 4

        return quarter

    def get_quarter_position(self, month):
        """
        @summary:: This function gets the corresponding position of the given
        month within its quarter. Position values can only be 1, 2 or 3
        """
        position = 0
        if int(month) in (1, 4, 7, 10):
            position = 1
        if int(month) in (2, 5, 8, 11):
            position = 2
        if int(month) in (3, 6, 9, 12):
            position = 3
        return position

    @api.constrains('period_from', 'period_to')
    def _check_period_from_to(self):
        for rec in self:
            date_from = dt.strptime(str(rec.period_from), OE_DFORMAT)
            date_to = dt.strptime(str(rec.period_to), OE_DFORMAT)
            qtr_start = rec._get_month_quarter(int(date_from.month))
            qtr_end = rec._get_month_quarter(int(date_to.month))
            if date_to > date_from:
                if qtr_start != qtr_end:
                    raise ValidationError(_('Unparalleled Quarter. Both "Period From" and "Period To" '
                                            'does not belong on the same quarter of the year. '
                                            'Please check your date values before saving.'))
            else:
                raise ValidationError(_('Invalid Period Range. Your "Period To" is less than your "Period From". '
                                        'Please check your date values before saving.'))

    @api.constrains('foreign_zip')
    def _check_foreign_zip(self):
        for rec in self:
            if rec.foreign_zip:
                if len(rec.foreign_zip) != 4:
                    raise ValidationError(_('Invalid ZIP Code! ZIP Code value must be 4 digits.'))

    @api.model
    def create(self, vals):
        """
        @summary: Create a reference number automatically upon creation of record.
        This will also validate if 'Period From' and 'Period To' belongs to the same
        Quarter of the year.
        """
        sequence_obj = self.env['ir.sequence']
        res = super(BirCreditableTaxWithheld, self).create(vals)

        ref_id = sequence_obj.next_by_code('bir.2307.ref')
        res.name = ref_id
        return res

    def compute_line(self):
        """
        @summary: This will compute the 1st, 2nd or 3rd Month of the Quarter
        depending on the given Periods(From and To), Tax Id and Supplier.
        """
        AccountTax = self.env['account.tax']

        AccountMove = self.env['account.move']
        AccountMoveLine = self.env['account.move.line']

        posted_invoices = AccountMove.search([('state', '!=', 'draft')])
        for rec in self:
            period_from = rec.period_from
            period_to = rec.period_to
            partner_id = rec.partner_id.id
            company = self.env.user.company_id
            withholding_2307_ids = company.withholding_2307_ids
            tax_ids = []
            # Get date range of Period From and Period To.
            date_ids = self._get_date_ids(period_from, period_to)
            m1 = m2 = m3 = 0
            m1q = m2q = m3q = 0
            for date in date_ids:
                month = int(dt.strptime(str(date), OE_DFORMAT).month)
                if m1 == 0:
                    m1 = month
                    m1q = self.get_quarter_position(month)

                if m2 == 0 and m1 > 0:
                    if month != m1:
                        m2 = month
                        m2q = self.get_quarter_position(month)

                if m3 == 0 and m1 > 0 and m2 > 0:
                    if month not in (m1, m2):
                        m3 = month
                        m3q = self.get_quarter_position(month)

            if not rec.vat_only:
                for line in rec.line_ids:
                    line.unlink()

                move_line_ids = AccountMoveLine.search([
                    ('partner_id', '=', partner_id),
                    ('date', 'in', date_ids),
                    ('tax_line_id', 'in', withholding_2307_ids.ids),
                    ('chk_2307', '!=', True),
                    ('move_id', 'in', posted_invoices.ids)
                ])
                move_line_ids2 = AccountMoveLine.search([
                    ('partner_id', '=', partner_id),
                    ('date', 'in', date_ids),
                    ('tax_ids', 'in', withholding_2307_ids.ids),
                    ('chk_2307', '!=', True),
                    ('move_id', 'in', posted_invoices.ids)
                ])
                # Check if existing in the other records
                bir_ext = self.search([
                    ('move_line_ids2', 'in', move_line_ids2.ids),
                    ('id', '!=', self.id)
                ])
                # raise ValidationError(str(move_line_ids) + ' - ' + str(move_line_ids2) + ' - ' + str(bir_ext))
                if not bir_ext:
                    rec.move_line_ids = move_line_ids
                    rec.move_line_ids2 = move_line_ids2

                    for tax_id in move_line_ids2:
                        for taxes in tax_id.tax_ids:
                            if taxes.id not in tax_ids and taxes.id in withholding_2307_ids.ids:
                                tax_ids.append(taxes.id)

                    for tax_id in tax_ids:
                        vals = {
                            'withholding_tax_id': tax_id,
                            'bir_cred_tax_with_id': rec.id
                        }
                        rec.line_ids.create(vals)

                    for tax in rec.line_ids:
                        if not move_line_ids2:
                            for line in rec.line_ids:
                                line.unlink()
                        else:
                            total_withheld = 0.0
                            m1_amount = m2_amount = m3_amount = withheld = 0.00
                            m1pr_amt = m2pr_amt = m3pr_amt = withheld_pr = 0.00
                            for move_line in move_line_ids2.filtered(lambda l: l.credit > 0.0 or l.debit > 0.0):
                                for tax_lines in move_line.tax_ids:
                                    if tax_lines == tax.withholding_tax_id:
                                        line_month = int(dt.strptime(str(move_line.date), OE_DFORMAT).month)
                                        tax_pct = tax.withholding_tax_id.amount / 100
                                        if move_line.journal_id.type == 'purchase':
                                            if move_line.credit != 0.00:
                                                amount = move_line.credit * tax_pct
                                                qtr_amount = amount
                                                if line_month == m1:
                                                    m1_amount += abs(qtr_amount / tax_pct)
                                                if line_month == m2:
                                                    m2_amount += abs(qtr_amount / tax_pct)
                                                if line_month == m3:
                                                    m3_amount += abs(qtr_amount / tax_pct)
                                                withheld += qtr_amount

                                            if move_line.debit != 0.00:
                                                amount = move_line.debit * tax_pct
                                                qtr_amount = amount
                                                if line_month == m1:
                                                    m1pr_amt += (qtr_amount / tax_pct)
                                                if line_month == m2:
                                                    m2pr_amt += (qtr_amount / tax_pct)
                                                if line_month == m3:
                                                    m3pr_amt += (qtr_amount / tax_pct)
                                                withheld_pr += qtr_amount

                                    total_withheld = abs(withheld_pr - withheld)

                            # For month 1
                            if m1q == 1:
                                vals = {
                                    'month1': m1pr_amt,
                                    'month1_pr': m1_amount,
                                    'total_1': m1pr_amt - m1_amount,
                                    'tax_withheld': total_withheld
                                }
                                tax.write(vals)
                            elif m1q == 2:
                                vals = {
                                    'month2': m1pr_amt,
                                    'month2_pr': m1_amount,
                                    'total_2': m1pr_amt - m1_amount,
                                    'tax_withheld': total_withheld
                                }
                                tax.write(vals)
                            elif m1q == 3:
                                vals = {
                                    'month3': m1pr_amt,
                                    'month3_pr': m1_amount,
                                    'total_3': m1pr_amt - m1_amount,
                                    'tax_withheld': total_withheld
                                }
                                tax.write(vals)

                            # For Month 2
                            if m2q == 1:
                                vals = {
                                    'month1': m2pr_amt,
                                    'month1_pr': m2_amount,
                                    'total_1': m2pr_amt - m2_amount,
                                    'tax_withheld': total_withheld
                                }
                                tax.write(vals)
                            elif m2q == 2:
                                vals = {'month2': m2pr_amt,
                                        'month2_pr': m2_amount,
                                        'total_2': m2pr_amt - m2_amount,
                                        'tax_withheld': total_withheld
                                        }
                                tax.write(vals)
                            elif m2q == 3:
                                vals = {'month3': m2pr_amt,
                                        'month3_pr': m2_amount,
                                        'total_3': m2pr_amt - m2_amount,
                                        'tax_withheld': total_withheld
                                        }
                                tax.write(vals)

                            # For Month 3
                            if m3q == 1:
                                vals = {
                                    'month1': m3pr_amt,
                                    'month1_pr': m3_amount,
                                    'total_1': m3pr_amt - m3_amount,
                                    'tax_withheld': total_withheld
                                }
                                tax.write(vals)
                            elif m3q == 2:
                                vals = {
                                    'month2': m3_amount,
                                    'month2_pr': m3_amount,
                                    'total_2': m3pr_amt - m3_amount,
                                    'tax_withheld': total_withheld
                                }
                                tax.write(vals)
                            elif m3q == 3:
                                vals = {
                                    'month3': m3pr_amt,
                                    'month3_pr': m3_amount,
                                    'total_3': m3pr_amt - m3_amount,
                                    'tax_withheld': total_withheld
                                }
                                tax.write(vals)

    def validate_state(self):
        AccountMoveLine = self.env['account.move.line']
        for rec in self:
            period_from = rec.period_from
            period_to = rec.period_to
            partner_id = rec.partner_id.id
            date_ids = self._get_date_ids(period_from, period_to)
            partner_zip = rec.partner_id.zip
            company_zip = rec.company_id.zip
            partner_vat = rec.partner_id.vat
            company_vat = rec.company_id.vat

            if partner_zip:
                if len(partner_zip) != 4:
                    raise ValidationError(_("Invalid ZIP Code!\n"
                                            "ZIP Code of '%s' must be 4 digits.") % rec.partner_id.name)
            if company_zip:
                if len(company_zip) != 4:
                    raise ValidationError(_("Invalid ZIP Code!\n"
                                            "ZIP Code of '%s' must be 4 digits.") % rec.company_id.name)

            if partner_vat and len(partner_vat) != 17:
                raise ValidationError('Partner TIN must be 17 characters.')

            if company_vat and len(company_vat) != 17:
                raise ValidationError('Company TIN must be 17 characters.')

            tax_ids = []
            for line in rec.line_ids:
                tax_ids.append(line.withholding_tax_id.id)
            move_line_ids = AccountMoveLine.search([
                ('partner_id', '=', partner_id),
                ('date', 'in', date_ids),
                ('tax_ids', 'in', tax_ids),
                ('chk_2307', '!=', True),
                ('move_id.state', '!=', 'draft')
            ])
            if len(rec.line_ids) != 0:
                for move_line in move_line_ids:
                    move_line.chk_2307 = True

            rec.state = 'validate'

    def action_view_entry(self):
        action = self.env.ref('account.action_move_line_select_tax_audit')
        result = action.read()[0]
        result['context'] = {}
        move_line_ids = self.move_line_ids2
        if len(move_line_ids) > 1:
            result['domain'] = "[('id', 'in', " + str(move_line_ids.ids) + ")]"
            move_line_ids._compute_wht_tax_amount()
            move_line_ids._compute_tax_base_amount()

        else:
            res = self.env.ref('account.view_move_line_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = move_line_ids.id or False

        return result

    def print_2307(self):
        """
        @summary: This is a button that allows a user to print a report after being validated.
        """
        return self.env.ref('tf_ph_bir.report_bir_2307').report_action(self)


class BirCreditableTaxWithheldLine(models.Model):
    _name = 'bir.creditable.tax.withheld.line'
    _description = 'BIR 2307 Line'

    bir_cred_tax_with_id = fields.Many2one('bir.creditable.tax.withheld', 'BIR 2307')
    withholding_tax_id = fields.Many2one('account.tax', 'ATC')
    withholding_tax_desc = fields.Char(string='Tax Name', related='withholding_tax_id.description')
    month1 = fields.Float('1st Month (Qtr)')
    month2 = fields.Float('2nd Month (Qtr)')
    month3 = fields.Float('3rd Month (Qtr)')
    month1_pr = fields.Float('1st Month Purchase Refund')
    month2_pr = fields.Float('2nd Month Purchase Refund')
    month3_pr = fields.Float('3rd Month Purchase Refund')
    total_1 = fields.Float('1st Total')
    total_2 = fields.Float('2nd Total')
    total_3 = fields.Float('3rd Total')
    total = fields.Float('Grand Total', compute='_compute_total')
    tax_withheld = fields.Float('Tax Withheld (Qtr)')

    def _compute_total(self):
        """
        @summary: Automatically computes Total on a line.
        """
        total = 0.00
        for rec in self:
            total = rec.total_1 + rec.total_2 + rec.total_3
            rec.total = total
