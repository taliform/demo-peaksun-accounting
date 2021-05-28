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

from odoo import models, fields, api, _
from datetime import datetime, timedelta
from dateutil import parser
from odoo.exceptions import ValidationError
import calendar as cal


class AccountAccountType(models.Model):
    _inherit = 'account.account.type'
    
    report_type = fields.Selection(selection=[('pl', 'Profit & Loss'), ('bs', 'Balance Sheet')], string='Report Type')


class TfPhTrialBalance(models.Model):
    _name = 'tf.ph.trial.balance'
    _inherit = 'mail.thread'
    _description = 'PH Trial Balance'
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id,
                                 track_visibility='onchange')
    name = fields.Char(string='Reference/Description', default="Trial Balance", readonly=True,
                       track_visibility='onchange')
    cut_off_date = fields.Date(string="Cut Off Date", required=True, track_visibility='onchange')
    closing_date = fields.Date(string='Closing Date', required=True, help="The closing date should be greater than "
                                                                          "the cut-off date by 15 days or less.",
                               track_visibility='onchange')
    trial_balance_line_ids = fields.One2many('tf.ph.trial.balance.lines', 'trial_balance_id',
                                             string='Trial Balance Lines', readonly=True)
    unadjusted_debit_total = fields.Float(string='Unadjusted Debit', readonly=True)
    unadjusted_credit_total = fields.Float(string='Unadjusted Credit', readonly=True)
    adjustments_debit_total = fields.Float(string='Adjustments Debit', readonly=True)
    adjustments_credit_total = fields.Float(string='Adjustments Credit', readonly=True)
    adjusted_debit_total = fields.Float(string='Adjusted Debit', readonly=True)
    adjusted_credit_total = fields.Float(string='Adjusted Credit', readonly=True)
    bs_debit_total = fields.Float(string='Balance Sheet Debit', readonly=True)
    bs_credit_total = fields.Float(string='Balance Sheet Credit', readonly=True)
    pl_debit_total = fields.Float(string='Profit & Lost Debit', readonly=True)
    pl_credit_total = fields.Float(string='Profit & Lost Credit', readonly=True)

    @api.constrains('cut_off_date', 'company_id')
    def _check_cutoff_date(self):
        #Checking same cut off date and same company
        for rec in self:
            trial_ids = self.search([('cut_off_date', '=', rec.cut_off_date),
                                     ('company_id', '=', rec.company_id.id)])
            if len(trial_ids) > 1:
                raise ValidationError(_('The Cut Off date has already been used.'))

    @api.constrains('cut_off_date', 'closing_date')
    def _check_dates(self):
        for rec in self:
            if rec.cut_off_date and rec.closing_date:
                close_period_start = datetime.strptime(str(rec.closing_date), '%Y-%m-%d')
                cut_off_date = datetime.strptime(str(rec.cut_off_date), '%Y-%m-%d')
                
                # Closing Date must be greater than the Cut Off date.
                if close_period_start < cut_off_date:
                    raise ValidationError(_('Closing Date (%s) should be greater than the Cut-off Date (%s).'
                                            % (close_period_start.date(), cut_off_date.date())))
    
                day_difference = (close_period_start - cut_off_date).days
                # Closing Date must be greater than 15 days or less than the Cut-Off Date. 
                if day_difference > 15:
                    raise ValidationError(_('Closing Date (%s) should be greater than the Cut-off Date (%s) by 15 or less number of days.' 
                                            'Difference is %d.' % (close_period_start.date(), cut_off_date.date(), day_difference)))
    
    @api.model
    def create(self, values):
        # Initialize Variables
        cut_off_date = values.get('cut_off_date')
        if cut_off_date:
            # Put Cut Off Date Name on Trial Balance Name
            values.update({'name': 'Trial Balance as of ' + datetime.strftime(parser.parse(cut_off_date).date(), '%B %d, %Y')})
        result = super(TfPhTrialBalance, self).create(values)
        return result

    def write(self, vals):
        # Validate Dates
        closing_date = vals.get('closing_date', self.closing_date)
        cut_off_date = vals.get('cut_off_date', self.cut_off_date)
        # If Cut off Date has been updated, update Trial Balance name
        if cut_off_date and cut_off_date != self.cut_off_date:
            vals.update({'name': 'Trial Balance as of ' + datetime.strftime(parser.parse(cut_off_date).date(), '%B %d, %Y')})
        result = super(TfPhTrialBalance, self).write(vals)
        return result

    def load_accounts(self):
        '''
        @note: This function loads the accounts and sorts them by code.
        '''
        Account = self.env['account.account']
        # Search Accounts first where the Account Type's Report Type is 'Balance Sheet' and 'Profit and Loss'
        # and sort them by code.
        accounts = Account.search([('user_type_id.report_type', '=', 'bs')]).sorted(lambda a: a.code)
        accounts = accounts | Account.search([('user_type_id.report_type', '=', 'pl')]).sorted(lambda a: a.code)
        
        return accounts

    def view_details(self):
        return {
            'name': self.name,
            'view_mode': 'tree',
            'view_type': 'form',
            'res_model': 'tf.ph.trial.balance.lines',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'domain': [('trial_balance_id', '=', self.id)]
            }

    def load_balances(self):
        # Initialize variables
        tb_lines_obj = self.env['tf.ph.trial.balance.lines']
        move_line_obj = self.env['account.move.line']
        # Delete current records
        if self.trial_balance_line_ids.ids != []:
            self.trial_balance_line_ids.unlink()
        
        # Load Accounts
        accounts = self.load_accounts()
    
        for account in accounts:
            # Get the last day of the Fiscal Year being set on the Account settings.
            year = False
            company = self.env['res.users'].browse(self._uid).company_id
            fiscal_last_month = int(company.fiscalyear_last_month)
            fiscal_last_day = company.fiscalyear_last_day
            selected_yr = fields.Date.from_string(self.cut_off_date).year
            
            if self.cut_off_date.month <= fiscal_last_month:
                year = self.cut_off_date.year - 1
            else:
                year = self.cut_off_date.year
            max_days = cal.monthrange(year, fiscal_last_month)[1]
            
            if fiscal_last_day > max_days:
                raise ValidationError(_('%s is an invalid day value for the month of %s and for the year %s. \
                                   Please go to Accounting > Configuration > Settings and look for the Fiscal Year section.')
                                    % (fiscal_last_day, cal.month_name[fiscal_last_month], year))
            
            date_str = str(fiscal_last_month) + ' ' + str(fiscal_last_day) + ' ' + str(year)
            last_date = (parser.parse(date_str) + timedelta(days=1)).date()
            cut_off_plus1_str = str(self.cut_off_date)
            cut_off_plus1 = (parser.parse(cut_off_plus1_str) + timedelta(days=1)).date()
            print(cut_off_plus1)
            print(cut_off_plus1_str)
            # Get Unadjusted Move lines
            unadjusted_query = """
                                SELECT sum(credit) as unadjusted_cr,
                                       sum(debit) as unadjusted_dr
                                FROM account_move_line
                                WHERE move_id in (SELECT id 
                                                  FROM account_move
                                                  WHERE state = 'posted')
                                AND date < '%s'
                                AND account_id = %s
            """ % (cut_off_plus1, account.id)
            self._cr.execute(unadjusted_query)
            unadjusted = self._cr.dictfetchall()
            
            unadjusted_deb = unadjusted_cre = 0.0
            if unadjusted[0]['unadjusted_dr'] or unadjusted[0]['unadjusted_cr']:
                if (unadjusted[0]['unadjusted_dr'] - unadjusted[0]['unadjusted_cr']) >= 0.0:
                    unadjusted_deb = (unadjusted[0]['unadjusted_dr'] - unadjusted[0]['unadjusted_cr'])
                    unadjusted_cre = 0.0
                else:
                    unadjusted_cre = abs(unadjusted[0]['unadjusted_dr'] - unadjusted[0]['unadjusted_cr'])
                    unadjusted_deb = 0.0
            
            # Get Adjustments Move lines
            adjustments_query = """
                                SELECT sum(credit) as adjustments_cr,
                                       sum(debit) as adjustments_dr
                                FROM account_move_line
                                WHERE move_id in (SELECT id 
                                                  FROM account_move
                                                  WHERE state = 'posted')
                                AND date >= '%s'
                                AND date <= '%s'
                                AND account_id = %s
            """ % (cut_off_plus1, self.closing_date, account.id)
            self._cr.execute(adjustments_query)
            adjustments = self._cr.dictfetchall()
            
            adjustments_deb = adjustments_cre = 0.0
            if adjustments[0]['adjustments_dr'] or adjustments[0]['adjustments_cr']:
                if (adjustments[0]['adjustments_dr'] - adjustments[0]['adjustments_cr']) >= 0.0:
                    adjustments_deb = (adjustments[0]['adjustments_dr'] - adjustments[0]['adjustments_cr'])
                    adjustments_cre = 0.0
                else:
                    adjustments_cre = abs(adjustments[0]['adjustments_dr'] - adjustments[0]['adjustments_cr'])
                    adjustments_deb = 0.0
            
            # Create Trial Balance Line
            tb_lines_obj.create({'account_id': account.id,
                                 'trial_balance_id': self.id,
                                 'unadjusted_debit': unadjusted_deb,
                                 'unadjusted_credit': unadjusted_cre,
                                 'adjustments_debit': adjustments_deb,
                                 'adjustments_credit': adjustments_cre
                                 })
            
        tb_line_ids = self.trial_balance_line_ids
        self.unadjusted_debit_total = sum(tb_line_ids.mapped('unadjusted_debit'))
        self.unadjusted_credit_total = sum(tb_line_ids.mapped('unadjusted_credit'))
        self.adjustments_debit_total = sum(tb_line_ids.mapped('adjustments_debit'))
        self.adjustments_credit_total = sum(tb_line_ids.mapped('adjustments_credit'))
        self.adjusted_debit_total = sum(tb_line_ids.mapped('adjusted_debit'))
        self.adjusted_credit_total = sum(tb_line_ids.mapped('adjusted_credit'))
        self.bs_debit_total = sum(tb_line_ids.mapped('bs_debit'))
        self.bs_credit_total = sum(tb_line_ids.mapped('bs_credit'))
        self.pl_debit_total = sum(tb_line_ids.mapped('pl_debit'))
        self.pl_credit_total = sum(tb_line_ids.mapped('pl_credit'))
    
    
class TfPhTrialBalanceLines(models.Model):
    _name = 'tf.ph.trial.balance.lines'
    _description = 'PH Trial Balance Lines'

    @api.depends('unadjusted_debit', 'unadjusted_credit', 'adjustments_debit', 'adjustments_credit')
    def _compute_amount(self):
        for line in self:
            '''
            @note: This function will used for computed fields
            '''
            
            unadjusted_debit = unadjusted_credit = bs_debit = bs_credit = pl_debit = pl_credit = 0.0
            debit_diff = line.unadjusted_debit + line.adjustments_debit
            credit_diff = line.unadjusted_credit + line.adjustments_credit
            adjusted_debit = debit_diff
            adjusted_credit = credit_diff

            # Balance Sheet
            if line.account_id.user_type_id.report_type == 'bs':
                if (debit_diff - credit_diff) >= 0.0:
                    bs_debit = debit_diff - credit_diff
                    bs_credit = 0.0
                else:
                    bs_credit = abs(debit_diff - credit_diff)
                    bs_debit = 0.0
             
            # Profit and Loss
            elif line.account_id.user_type_id.report_type == 'pl':
                if (debit_diff - credit_diff) >= 0.0:
                    pl_debit = debit_diff - credit_diff
                    pl_credit = 0.0
                else:
                    pl_credit = abs(debit_diff - credit_diff)
                    pl_debit = 0.0
            
            line.adjusted_debit = adjusted_debit 
            line.adjusted_credit = adjusted_credit
            line.bs_debit = bs_debit
            line.bs_credit = bs_credit
            line.pl_debit = pl_debit
            line.pl_credit = pl_credit
    
    trial_balance_id = fields.Many2one('tf.ph.trial.balance', readonly=True, ondelete="cascade")
    account_id = fields.Many2one('account.account', readonly=True, string='Account Title')
    unadjusted_debit = fields.Float(string='Unadjusted DR', readonly=True, track_visibility='onchange')
    unadjusted_credit = fields.Float(string='Unadjusted CR', readonly=True, track_visibility='onchange')
    adjustments_debit = fields.Float(string='Adjustments DR', readonly=True, track_visibility='onchange')
    adjustments_credit = fields.Float(string='Adjustments CR', readonly=True, track_visibility='onchange')
    adjusted_debit = fields.Float(string='Adjusted DR', readonly=True, track_visibility='onchange', compute='_compute_amount', store=True)
    adjusted_credit = fields.Float(string='Adjusted CR', readonly=True, track_visibility='onchange', compute='_compute_amount', store=True)
    bs_debit = fields.Float(string='Bal Sheet DR', readonly=True, compute='_compute_amount', track_visibility='onchange', store=True)
    bs_credit = fields.Float(string='Bal Sheet CR', readonly=True, compute='_compute_amount', track_visibility='onchange', store=True)
    pl_debit = fields.Float(string='P&L Debit', readonly=True, compute='_compute_amount', track_visibility='onchange', store=True)
    pl_credit = fields.Float(string='P&L Credit', readonly=True, compute='_compute_amount', track_visibility='onchange', store=True)
