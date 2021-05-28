# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Joshua <joshua@taliform.com>
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
from calendar import calendar, monthrange
from odoo import api, fields, models,_
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, date

class BankLoan(models.Model):
    _name = 'bank.loan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Bank Loan'

    _STATES = [('draft', 'Draft'),
               ('ongoing', 'Ongoing'),
               ('paid', 'Paid'),
               ('closed', 'Closed'),
               ('cancel', 'Cancelled')]

    _LOAN_STATUS = [
        ('new', 'New'),
        ('existing', 'Existing')
    ]
    _LOAN_TYPE = [
        ('regular', 'Regular Loan'),
        ('term', 'Term Loan')
    ]
    _INTEREST_PAYMENT = [
        ('advance', 'Advance'),
        ('arrears', 'Arrears')
    ]
    _LOAN_COMPUTATION = [
        ('diminishing', 'Diminishing Balance'),
        ('user', 'User Defined')
    ]
    _PAYMENT_SCHEDULE = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi', 'Semi-Annual'),
        ('year', 'Yearly'),
        ('days', 'Days in a Month')
    ]
    _LOAN_PAYMENT_TERMS = [
        ('monthly', '30 Days'),
        ('quarterly', '90 Days'),
        ('semi', '180 Days'),
        ('year', '360 Days'),
        ('days', '')
    ]

    # Res Config
    principal_account_id = fields.Many2one('account.account', string='Principal Account',
                                           default=lambda self: int(self.env['ir.config_parameter'].sudo()
                                                                    .get_param('bank_loan.principal_account_id')))
    penalty_account_id = fields.Many2one('account.account', string='Penalty Account',
                                         default=lambda self: int(self.env['ir.config_parameter'].sudo()
                                                                  .get_param('bank_loan.penalty_account_id'))
                                         )
    interest_account_id = fields.Many2one('account.account', string='Interest Account',
                                          default=lambda self: int(self.env['ir.config_parameter'].sudo()
                                                                   .get_param('bank_loan.interest_account_id'))
                                          )
    other_expense_account_id = fields.Many2one('account.account', string='Other Expense Account',
                                               default=lambda self: int(self.env['ir.config_parameter'].sudo()
                                                                .get_param('bank_loan.other_expense_account_id'))
                                               )
    prepaid_expense_account_id = fields.Many2one('account.account', string='Prepaid Expense Account',
                                                 default=lambda self: int(self.env['ir.config_parameter'].sudo()
                                                                    .get_param('bank_loan.prepaid_expense_account_id'))
                                                 )
    accrued_expense_account_id = fields.Many2one('account.account', string='Accrued Expense Account',
                                                 default=lambda self: int(self.env['ir.config_parameter'].sudo()
                                                                    .get_param('bank_loan.accrued_expense_account_id'))
                                                 )
    collection_journal_id = fields.Many2one('account.journal', string='Collection Journal',
                                            default=lambda self: int(self.env['ir.config_parameter'].sudo()
                                                                     .get_param('bank_loan.collection_journal_id'))
                                            )
    loan_journal_id = fields.Many2one('account.journal', string='Loan Journal',
                                      default=lambda self: int(self.env['ir.config_parameter'].sudo()
                                                               .get_param('bank_loan.loan_journal_id'))
                                      )
    adjusting_journal_id = fields.Many2one('account.journal', string='Adjusting Journal',
                                           default=lambda self: int(self.env['ir.config_parameter'].sudo()
                                                                    .get_param('bank_loan.adjusting_journal_id'))
                                           )
    withholding_tax_id = fields.Many2one('account.tax', string='Withholding Tax',
                                         default=lambda self: int(self.env['ir.config_parameter'].sudo()
                                                                  .get_param('bank_loan.withholding_tax_id'))
                                         )
    state = fields.Selection(_STATES, default='draft')
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.user.company_id.currency_id)

    # View
    loan_status = fields.Selection(_LOAN_STATUS, string='Loan Status', required=True)
    loan_type = fields.Selection(_LOAN_TYPE, string='Loan Type', required=True)
    bank_name_id = fields.Many2one('res.partner', string='Bank Name', required=True,
                                help='Indicate the partner who facilitate the loan application')
    promissory_note = fields.Char(required=True, help='Indicate the bank loan reference.')
    total_loan_amount = fields.Monetary(required=True, string='Total Loan Amount')
    date_granted = fields.Date(required=True, string='Date Granted',
                               help='Indicate the bank loan start date of the amortization which '
                                    'serves as a guide for the amortization schedule duration')
    maturity_date = fields.Date(required=True, string='Maturity Date',
                                help='Indicate the bank loan end date of the amortization '
                                     'which serves as a guide for the amortization schedule duration')
    interest_payment = fields.Selection(_INTEREST_PAYMENT, required=True,
                                        help='Indicate the appropriate amortization '
                                             'payment due based on the given choices.')
    loan_computation = fields.Selection(_LOAN_COMPUTATION, required=True,
                                        help=' Indicate the appropriate loan computation which serves as a guide for '
                                             'the generation of amortization schedules line.')
    period_principal_amount = fields.Monetary(required=True,
                                              help='Indicate the periodic amortization principal amount to be paid.')
    payment_schedule = fields.Selection(_PAYMENT_SCHEDULE, required=True, default='days',
                                        help='Indicate the periodic amortization duration which serves as a guide '
                                             'for the generation of amortization schedules line.')
    loan_payment_term = fields.Selection(_LOAN_PAYMENT_TERMS, default='days', compute='_get_loan_payment_term',
                                         store=True, required=True,
                                         help=' Automatically determine periodic amortization d'
                                              'ays duration based on the selected payment schedule.')

    loan_duration = fields.Integer(compute='_get_loan_duration',
                                   help='Compute the number of days of the loan duration based '
                                        'on the indicated date granted date up to the maturity date.')
    interest_rate = fields.Float(required=True, help='Indicate the loan interest rate which '
                                                     'serves as a guide for interest computation.')
    charges = fields.Monetary(required=True,
                              help='Indicate the loan’s other incidental charges incurred during the application.')
    outstanding_principal = fields.Monetary(compute='_get_outstanding_principal',
                                            help=' Indicate the bank loan principal amount.')
    total_interest_paid = fields.Monetary(compute='_get_next_payment_due', help='Indicate the total interest paid.')
    next_principal_payment = fields.Monetary(string="Next Principal Payment", compute='_get_next_payment_due',
                                             help='Indicate the next principal payment.')
    next_interest_due = fields.Monetary(string="Next Interest Due", compute='_get_next_payment_due',
                                        help='Indicate the next interest due.')
    next_due_date = fields.Date(string="Next Due Date", compute='_get_loan_duration',
                                help='Indicate the next interest due.')

    customer_invoice_id = fields.Many2one('account.move', string='Customer Invoice')
    invoice_status = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled')], relation='customer_invoice_id.state')

    loan_reference_id = fields.Many2one('bank.loan', domain="[('state', '=', 'cancel')]",
                                        help='Select appropriate previously cancelled loan payable with unpaid balance'
                                             ' due to the restructuring agreement.')
    payment_method_id = fields.Many2one(relation='loan_reference_id.customer_invoice_id.payment_id')
    outstanding_balance = fields.Float(compute='_get_outstanding_balance', string='Outstanding Balance')
    additional_loan_amount = fields.Monetary(compute='_get_next_payment_due',
                                             help='Indicate if there are additional principal amount to the '
                                                  'restructured loan aside from the outstanding principal amount.',
                                             store=True)

    name = fields.Char(string='Name', default='Draft Bank Loan', copy=False)
    loan_schedule_ids = fields.One2many('bank.loan.schedule.lines', 'bank_loan_id', string='Loan Schedule Lines')
    invoice_count = fields.Integer(compute='_get_invoice_count')
    is_recompute = fields.Boolean(default=False, readonly=True)

    @api.depends('loan_schedule_ids', 'total_loan_amount')
    def _get_outstanding_balance(self):
        LoanScheduleLines = self.env['bank.loan.schedule.lines']
        for rec in self:
            outstanding_bal = 0
            if rec.loan_schedule_ids and rec.total_loan_amount:
                paid_schedule_lines = LoanScheduleLines.search([
                    ('bank_loan_id', '=', rec.id),
                    ('bill_id', '!=', False),
                    ('bill_id.invoice_payment_state', '=', 'paid')
                ])
                outstanding_bal += rec.total_loan_amount - sum(paid_schedule_lines.mapped('principal_payment'))
            rec.outstanding_balance = outstanding_bal

    @api.model
    def create(self, values):
        '''
        @summary: This will add a reference number for every created record.
        '''
        values['name'] = self.env['ir.sequence'].get('bank.loan.ref')
        return super(BankLoan, self).create(values)

    def _get_outstanding_principal(self):
        for rec in self:
            principal_payment = 0
            for payment in rec.customer_invoice_id.payment_ids.filtered(lambda x: x.state == 'posted'):
                principal_payment += payment.amount
            rec.outstanding_principal = rec.total_loan_amount - principal_payment

    @api.depends('loan_schedule_ids', 'loan_reference_id')
    def _get_next_payment_due(self):
        for rec in self:
            rec.next_principal_payment = 0
            rec.next_interest_due = 0
            rec.next_due_date = 0
            total_payment_due = 0
            total_interest_due = 0
            next_due_date = []
            for amort in rec.loan_schedule_ids.filtered(lambda x: x.bill_id.invoice_payment_state != 'paid'):
                total_payment_due += amort.due_amount
                total_interest_due += amort.interest_due
                next_due_date.append(amort.payment_date)
            if total_payment_due > 0 and total_interest_due > 0 and next_due_date:
                rec.write({
                    'next_principal_payment': total_payment_due,
                    'next_interest_due': total_interest_due,
                    'next_due_date': next_due_date[0]
                })

            total_interest_paid = 0
            for amort in rec.loan_schedule_ids.filtered(lambda x: x.bill_id.invoice_payment_state == 'paid'):
                total_interest_paid += amort.interest_due
            rec.total_interest_paid = total_interest_paid

            loan_ref = rec.loan_reference_id
            if loan_ref:
                rec.additional_loan_amount += loan_ref.total_loan_amount

    def action_view_invoice(self):
        return {
            'name': _('Customer Invoice'),
            'view_mode': 'form',
            'view_id': self.env.ref('account.view_move_form').id,
            'res_model': 'account.move',
            'context': "{'type':'out_invoice'}",
            'type': 'ir.actions.act_window',
            'res_id': self.customer_invoice_id.id,
        }

    def _get_invoice_count(self):
        for rec in self:
            inv_count = 0
            if rec.customer_invoice_id:
                inv_count = len(rec.customer_invoice_id)
            rec.invoice_count = inv_count

    @api.depends('maturity_date', 'date_granted')
    def _get_loan_duration(self):
        for rec in self:
            rec.loan_duration = 0
            rec.next_due_date = 0
            maturity_date = rec.maturity_date
            date_granted = rec.date_granted
            if date_granted and maturity_date:
                day_diff = rec.get_day_difference(maturity_date, date_granted)
                rec.loan_duration = day_diff
                rec.next_due_date = maturity_date + timedelta(days=day_diff)

    def get_day_difference(self, date1, date2):
        mdate1 = datetime.strptime(str(date1), "%Y-%m-%d")
        rdate1 = datetime.strptime(str(date2), "%Y-%m-%d")
        return (mdate1.date() - rdate1.date()).days

    @api.depends('payment_schedule')
    def _get_loan_payment_term(self):
        for rec in self:
            if rec.payment_schedule:
                rec.loan_payment_term = rec.payment_schedule

    def generate_amortization_bill(self):
        AccountMove = self.env['account.move']
        bank_loan_records = self.env['bank.loan'].search([('state', '=', 'ongoing')])
        for rec in bank_loan_records:
            for line in rec.loan_schedule_ids:
                create_bill = False
                if line.line_no == 1 and not line.bill_id:
                    create_bill = True
                elif line.line_no > 1:
                    line_rec = line.search([('line_no', '=', line.line_no - 1),
                                            ('bill_id', '!=', False), ('bank_loan_id', '=', rec.id)])
                    if line_rec.bill_id.invoice_payment_state == 'paid':
                        create_bill = True
                if create_bill:
                    print(rec.bank_name_id.name)
                    bill_date = line.payment_date + timedelta(days=30)
                    principal_invoice_line = {
                        'name':  str(line.name) + "- Loan Payment Schedule Amount(Principal)",
                        'journal_id': rec.loan_journal_id.id,
                        'account_id': rec.principal_account_id.id,
                        'tax_line_id': rec.withholding_tax_id.id,
                        'price_unit': line.principal_payment,
                        'quantity': 1,
                    }
                    interest_invoice_line = {
                        'name': str(line.name) + "- Loan Payment Schedule Amount(Interest)",
                        'journal_id': rec.loan_journal_id.id,
                        'account_id': rec.interest_account_id.id,
                        'tax_line_id': rec.withholding_tax_id.id,
                        'price_unit': line.interest_due,
                        'quantity': 1,
                    }
                    penalty_invoice_line = {
                        'name': str(line.name) + "- Loan Payment Schedule Amount(Penalty)",
                        'journal_id': rec.loan_journal_id.id,
                        'account_id': rec.penalty_account_id.id,
                        'tax_line_id': rec.withholding_tax_id.id,
                        'price_unit': line.penalty,
                        'quantity': 1,
                    }

                    # Vendor Bill
                    bill_vals = {
                        'partner_id': rec.bank_name_id.id,
                        'ref': rec.name,
                        'journal_id': rec.loan_journal_id.id,
                        'invoice_date': bill_date,
                        'date': fields.Date.context_today(self),
                        'name': line.name + ' - Loan Payment Schedule',
                        'type': 'in_invoice'
                    }
                    bill_id = AccountMove.create(bill_vals)
                    bill_id.write({
                        'invoice_line_ids': [(0, 0, principal_invoice_line), (0, 0, interest_invoice_line),
                                             (0, 0, penalty_invoice_line)],
                    })
                    bill_id.post()
                    line.bill_id = bill_id

    def action_confirm(self):
        AccountInvoice = self.env['account.move']
        for rec in self:
            if not rec.loan_schedule_ids:
                raise ValidationError('Loan schedule should not be empty!')
            for line in rec.loan_schedule_ids:
                line.write({'state': 'ongoing'})

            inv_line_vals = {
                'name': "[" + str(rec.name) + "]",
                'journal_id': rec.collection_journal_id.id,
                'account_id': rec.principal_account_id,
                'price_unit': rec.total_loan_amount,
                'quantity': 1,
            }
            # Customer Invoice
            inv_vals = {
                'partner_id': rec.bank_name_id.id,
                'ref': rec.name,
                'journal_id': rec.collection_journal_id.id,
                'invoice_date': fields.Date.context_today(self),
                'invoice_line_ids': [(0, 0, inv_line_vals)],
                'date': fields.Date.context_today(self),
                'name': rec.name,
                'type': 'out_invoice'
            }
            invoice_id = AccountInvoice.create(inv_vals)
            rec.customer_invoice_id = invoice_id
            rec.state = 'ongoing'

    def load_initial_schedule(self):
        payment_sched_days = {
            'monthly': 30,
            'quarterly': 90,
            'semi': 180,
            'year': 360,
            'days': 1
        }
        BankLoanLines = self.env['bank.loan.schedule.lines']
        for rec in self:
            day_diff = rec.get_day_difference(rec.maturity_date, rec.date_granted)
            sched_days = payment_sched_days[rec.payment_schedule]
            if sched_days > day_diff:
                raise ValidationError(f'Payment schedule days must be lesser than the days between {rec.date_granted} '
                                      f'and {rec.maturity_date}!')
            else:
                i = 1
                loan_sched_count = int(day_diff / sched_days)
                curr_date = rec.date_granted
                loan_balance = rec.total_loan_amount
                principal_payment = loan_balance / loan_sched_count
                curr_payment = 0
                interest_rate = rec.interest_rate
                if rec.loan_schedule_ids:
                    rec.loan_schedule_ids.unlink()
                while i <= loan_sched_count:
                    prev_date = curr_date
                    curr_date = prev_date + timedelta(days=sched_days)
                    payment_date = prev_date
                    curr_out_principal = loan_balance - curr_payment
                    if rec.interest_payment == 'arrears':
                        payment_date = curr_date
                    if payment_sched_days[rec.payment_schedule] == 1:
                        curr_date = date(prev_date.year, prev_date.month,
                                                  monthrange(prev_date.year, prev_date.month)[1])
                    pay_term = rec.get_day_difference(curr_date, prev_date)
                    vals = {
                        'line_no': i,
                        'bank_loan_id': rec.id,
                        'period_from': prev_date,
                        'period_to': curr_date,
                        'payment_date': payment_date,
                        'term': pay_term,
                        'outstanding_principal': curr_out_principal,
                        'principal_payment': principal_payment,
                        'interest_due': curr_out_principal * (interest_rate / 100) * (pay_term / rec.loan_duration),
                    }
                    curr_date = curr_date + timedelta(days=1)
                    curr_payment += principal_payment
                    BankLoanLines.create(vals)
                    i += 1

    def action_recompute(self):
        BankLoanLines = self.env['bank.loan.schedule.lines']
        for rec in self:
            rec.is_recompute = True
            if rec.loan_computation == 'user':
                raise ValidationError('Loan computation must be set to "Diminishing Balance".')

            BankLoanLines.search([
                ('bank_loan_id', '=', rec.id),
                ('bill_id', '=', False)
            ]).unlink()
            print(rec)

    def recompute_schedule_lines(self):
        payment_sched_days = {
            'monthly': 30,
            'quarterly': 90,
            'semi': 180,
            'year': 360,
            'days': 1
        }
        BankLoanLines = self.env['bank.loan.schedule.lines']
        for rec in self:
            if rec.loan_schedule_ids:
                max_line_no = max(rec.loan_schedule_ids.mapped('line_no'))
                latest_billed_line_sched = rec.loan_schedule_ids.filtered(lambda x: x.line_no == max_line_no)[0]
                day_diff = rec.get_day_difference(rec.maturity_date, rec.date_granted)
                sched_days = payment_sched_days[rec.payment_schedule]

                if latest_billed_line_sched:
                    i = 1
                    loan_sched_count = int(day_diff / sched_days) - len(rec.loan_schedule_ids)
                    curr_date = latest_billed_line_sched.period_to + timedelta(days=1)
                    if loan_sched_count <= 0:
                        raise ValidationError('Payment loan term selected invalid!')
                    loan_balance = latest_billed_line_sched.outstanding_principal - latest_billed_line_sched.principal_payment
                    principal_payment = loan_balance / loan_sched_count
                    curr_payment = 0
                    interest_rate = rec.interest_rate
                    curr_line_no = max_line_no + 1
                    while i <= loan_sched_count:
                        prev_date = curr_date
                        curr_date = prev_date + timedelta(days=sched_days)
                        payment_date = prev_date
                        curr_out_principal = loan_balance - curr_payment
                        if rec.interest_payment == 'arrears':
                            payment_date = curr_date
                        if payment_sched_days[rec.payment_schedule] == 1:
                            curr_date = date(prev_date.year, prev_date.month,
                                             monthrange(prev_date.year, prev_date.month)[1])
                        pay_term = rec.get_day_difference(curr_date, prev_date)
                        vals = {
                            'line_no': curr_line_no,
                            'bank_loan_id': rec.id,
                            'period_from': prev_date,
                            'period_to': curr_date,
                            'payment_date': payment_date,
                            'term': pay_term,
                            'state': 'ongoing',
                            'outstanding_principal': curr_out_principal,
                            'principal_payment': principal_payment,
                            'interest_due': curr_out_principal * (interest_rate / 100) * (pay_term / rec.loan_duration),
                        }
                        curr_date = curr_date + timedelta(days=1)
                        curr_payment += principal_payment
                        BankLoanLines.create(vals)
                        curr_line_no += 1
                        i += 1
            else:
                self.load_initial_schedule()
            rec.is_recompute = False

    def cancel(self):
        paid_loan_schedules = []
        for rec in self:
            for line in rec.loan_schedule_ids:
                if line.bill_id.invoice_payment_state == 'paid':
                    paid_loan_schedules.append(rec.id)
                    line.write({'state': 'closed'})
            if len(paid_loan_schedules) == len(rec.loan_schedule_ids):
                rec.state = 'closed'
            else:
                raise ValidationError('Cannot close bank load record. \nAll Loan schedule lines must be paid first.')


class BankLoanScheduleLines(models.Model):
    _name = 'bank.loan.schedule.lines'
    _description = 'Bank Loan Schedule Lines'

    _STATES = [('draft', 'Draft'),
               ('ongoing', 'Ongoing'),
               ('closed', 'Closed')]

    def _get_ref(self):
        for rec in self:
            rec.reference = ''
            bill_id = rec.bill_id
            if bill_id.payment_ids:
                payment = bill_id.payment_ids[0]
                if payment.partner_type == 'supplier':
                    rec.reference = f'{payment.name}'

    state = fields.Selection(_STATES, string='Status', default='draft')
    bank_loan_id = fields.Many2one('bank.loan', string='Bank Loan')
    loan_computation = fields.Selection(related='bank_loan_id.loan_computation')
    line_no = fields.Integer(string='No.', readonly=True)
    line_editable = fields.Boolean(default=True)
    period_from = fields.Date(help='Start date of the periodic amortization.', readonly=True)
    period_to = fields.Date(help='End date of the periodic amortization.', readonly=True)
    payment_date = fields.Date(help='Depend on the interest payment option')
    term = fields.Integer(help='Period To less Period From date ')
    outstanding_principal = fields.Float(help='Current principal balance.')
    principal_payment = fields.Float(help='Periodic amortization duration')
    interest_rate = fields.Float(relation='bank_loan_id.interest_rate')
    interest_due = fields.Float(help='Interest amount per amortization ')
    penalty = fields.Float(help='Add-on charges on per amortization lines.')
    due_amount = fields.Float(compute='_get_due_amount', help='Total amortization line payable ')
    bill_id = fields.Many2one('account.move', string='Supplier Invoice No.',
                              domain="[('type', 'in', ('in_invoice', 'in_refund', 'in_receipt'))]")
    payment_ref = fields.Many2one(relation='bill_id.payment_id', string='Payment Reference')
    name = fields.Char(string='Name', default='Draft Loan Schedule Line', copy=False)
    reference = fields.Char('Payment Reference', compute='_get_ref')

    @api.model
    def create(self, values):
        '''
        @summary: This will add a reference number for every created record.
        '''
        values['name'] = self.env['ir.sequence'].get('bank.loan.line.ref')
        return super(BankLoanScheduleLines, self).create(values)

    @api.depends('principal_payment', 'interest_due', 'penalty', 'payment_ref')
    def _get_due_amount(self):
        for rec in self:
            total_payment = 0
            bill = rec.bill_id
            if bill and bill.payment_ids:
                total_payment += sum(bill.payment_ids.filtered(lambda x: x.state == 'posted').mapped('amount'))
            rec.due_amount = abs((rec.principal_payment + rec.interest_due + rec.penalty) - total_payment)

    def _compute_lines(self):
        for rec in self:
            rec.line_no = len(rec.bank_loan_id.loan_schedule_ids)
