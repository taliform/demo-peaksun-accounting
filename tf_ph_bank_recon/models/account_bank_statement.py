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
from odoo import models, fields, api, _
from odoo.exceptions import Warning, ValidationError, UserError
from odoo.tools import datetime
from odoo.tools.misc import formatLang


class AccountBankStatementAdjustment(models.Model):
    _name = "account.bank.statement.adjustment"
    _description = 'Bank Statement Adjustment'

    name = fields.Char("Remarks")
    amount = fields.Monetary("Amount")
    abs_id = fields.Many2one('account.bank.statement', "Bank Statement", ondelete='cascade')
    currency_id = fields.Many2one(related='abs_id.currency_id')
    state = fields.Selection(related='abs_id.state')
    type = fields.Selection([('book', 'Book Errors'), ('bank', 'Bank Errors')], "Type")


class AccountBankStatementPayment(models.Model):
    _name = "account.bank.statement.payment"
    _description = 'Bank Statement Payment'

    bounced = fields.Boolean("Bounced")
    abs_id = fields.Many2one('account.bank.statement', "Bank Statement", ondelete='cascade')
    payment_id = fields.Many2one('account.payment', "Payment")
    bounce_date = fields.Date("Journal Date")
    name = fields.Char(related='payment_id.name')
    payment_date = fields.Date(related='payment_id.payment_date')
    amount = fields.Monetary(related='payment_id.amount', store=True)
    journal_id = fields.Many2one(related='payment_id.journal_id')
    partner_id = fields.Many2one(related='payment_id.partner_id', store=True)
    currency_id = fields.Many2one(related='payment_id.currency_id')
    unreleased_am_id = fields.Many2one(related='abs_id.unreleased_am_id')
    state = fields.Selection(related='payment_id.state', store=True)
    partner_type = fields.Selection(related='payment_id.partner_type')
    payment_type = fields.Selection(related='payment_id.payment_type')
    release_state = fields.Selection([('unreleased', 'Unreleased'), ('released', 'Released')],
                                     string="Release State", default='unreleased')

    def release(self):
        for rec in self:
            if rec.release_state == 'unreleased':
                rec.release_state = 'released'
                if rec.payment_id:
                    rec.payment_id.write({
                        'check_released': True,
                        'check_release_date': datetime.now()
                    })
            else:
                rec.release_state = 'unreleased'
                if rec.payment_id:
                    rec.payment_id.check_released = False

    def action_bounce_payment(self):
        self.ensure_one()
        self.payment_id.cancel()
        if self._context.get('bounce'):
            self.bounced = True
        self.abs_id._get_cash_transactions_total()

    def action_open_payment_bounce_wizard(self):
        self.ensure_one()
        return {
            'name': "Bounce Payment",
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.bank.statement.payment',
            'view_id': self.env.ref('tf_ph_bank_recon.view_account_payment_bounce').id,
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {'default_bounce_date': fields.Date.context_today(self),
                        'bounce': True},
        }

    def action_open_payment_cancel_wizard(self):
        self.ensure_one()
        return {
            'name': "Cancel Payment",
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.bank.statement.payment',
            'view_id': self.env.ref('tf_ph_bank_recon.view_account_payment_bounce').id,
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {'default_bounce_date': fields.Date.context_today(self),
                        'bounce': True},
        }


class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    unreleased_am_id = fields.Many2one('account.move', "Journal Entry",
                                       help="Journal entry created for the unreleased outstanding payments.")
    balance_start_copy = fields.Monetary(string="Starting Balance (Copy)", related='balance_start')
    locked_amount = fields.Monetary(string="Locked Amount")
    locked = fields.Boolean('Locked')

    summary_unadjusted_balance = fields.Monetary(compute='_get_unadjusted_balance', string="Unadjusted Balance (Book)",
                                                 store=True)
    summary_cash_transactions_total = fields.Monetary(compute="_get_cash_transactions_total",
                                                      string="Additional Cash Transaction", store=True)
    summary_unreleased_outstanding_total = fields.Monetary(related='unreleased_outstanding_total',
                                                           string="Unreleased Check")
    summary_cancel_intransit_total = fields.Char(compute='_get_summary_cancel_intransit_total',
                                                 string="Bounced Checks-Collections")
    summary_cancel_outstanding_total = fields.Monetary(related='cancel_outstanding_total',
                                                       string="Bounced Check-Disbursements")
    summary_adjustment_book_total = fields.Monetary(compute='_get_book_adjustments', string="Book Error", store=True)
    summary_book_total = fields.Monetary(compute="_get_book_summary_total", string="Book Total")

    summary_balance_end_real = fields.Monetary(related='balance_end_real', string="Unadjusted Balance (Bank)")
    summary_intransit_total = fields.Monetary(related='intransit_total', string="Deposit in Transit")
    summary_outstanding_total = fields.Char(compute='_get_summary_outstanding_total', string="Outstanding Checks")
    summary_adjustment_bank_total = fields.Monetary(compute='_get_bank_adjustments', string="Bank Error", store=True)
    summary_bank_total = fields.Monetary(compute="_get_bank_summary_total", string="Bank Total")

    book_error_ids = fields.One2many('account.bank.statement.adjustment', 'abs_id', 'Book Errors',
                                     domain=[('type', '=', 'book')], states={'confirm': [('readonly', True)]})
    bank_error_ids = fields.One2many('account.bank.statement.adjustment', 'abs_id', 'Bank Errors',
                                     domain=[('type', '=', 'bank')], states={'confirm': [('readonly', True)]})

    intransit_payment_ids = fields.One2many('account.bank.statement.payment', 'abs_id', 'In-Transit Payments',
                                            domain=[
                                                ('payment_id.payment_type', '=', 'inbound'),
                                                '|', ('state', 'not in', ['reconciled', 'cancelled']),
                                                '&', ('state', '=', 'cancelled'), ('bounced', '=', True)
                                            ])
    outstanding_payment_ids = fields.One2many('account.bank.statement.payment', 'abs_id', 'Outstanding Payments',
                                              domain=[
                                                  ('payment_id.payment_type', '=', 'outbound'),
                                                  '|', ('state', 'not in', ['reconciled', 'cancelled']),
                                                  '&', ('state', '=', 'cancelled'), ('bounced', '=', True)])

    intransit_total = fields.Monetary('In-Transit Total', compute='_get_field_computations', store=True)
    outstanding_total = fields.Monetary('Outstanding Checks Total', compute='_get_field_computations', store=True)

    cancel_intransit_total = fields.Monetary('Bounced Total (In Transit)', compute='_get_field_computations',
                                             store=True)
    cancel_outstanding_total = fields.Monetary('Bounced Total (Outstanding)', compute='_get_field_computations',
                                               store=True)

    all_intransit_total = fields.Monetary('Payments Total (In Transit)', compute='_get_field_computations', store=True)
    all_outstanding_total = fields.Monetary('Payments Total (Outstanding)', compute='_get_field_computations',
                                            store=True)

    released_outstanding_total = fields.Monetary('Released Total', compute='_get_field_computations', store=True)
    unreleased_outstanding_total = fields.Monetary('Unreleased Total', compute='_get_field_computations', store=True)

    @api.model
    def create(self, vals):
        journal_obj = self.env['account.journal']
        if not vals.get('name', False):
            name = "Bank Reconciliation"
            journal_id = vals.get('journal_id', False)
            if journal_id:
                journal_id = journal_obj.browse(journal_id)
                name += " - %s" % journal_id.name
            date = vals.get('date', fields.Date.today())
            if date:
                name += " - %s" % date
            vals.update({'name': name})
        res = super(AccountBankStatement, self).create(vals)
        return res

    def _balance_check(self):
        for stmt in self:

            difference = stmt.difference
            unreleased_posted_outstanding = self.env['account.bank.statement.payment'].search([
                ('id', 'in', stmt.outstanding_payment_ids.ids),
                ('state', '=', 'posted'),
                ('release_state', '=', 'unreleased')
            ])
            if unreleased_posted_outstanding and not stmt.unreleased_am_id:
                raise UserError('There are outstanding unreleased payments without a journal entry.\n')

            if stmt.journal_type == 'bank':
                difference = stmt.summary_book_total - stmt.summary_bank_total

            if not stmt.currency_id.is_zero(difference):
                if stmt.journal_type == 'cash':
                    if stmt.difference < 0.0:
                        account = stmt.journal_id.loss_account_id
                        name = _('Loss')
                    else:
                        # statement.difference > 0.0
                        account = stmt.journal_id.profit_account_id
                        name = _('Profit')
                    if not account:
                        raise UserError(_('There is no account defined on the journal %s for %s '
                                          'involved in a cash difference.') % (stmt.journal_id.name, name))

                    values = {
                        'statement_id': stmt.id,
                        'account_id': account.id,
                        'amount': difference,
                        'name': _("Cash difference observed during the counting (%s)") % name,
                    }
                    self.env['account.bank.statement.line'].create(values)
                else:
                    book_balance = formatLang(self.env, stmt.summary_book_total, currency_obj=stmt.currency_id)
                    bank_balance = formatLang(self.env, stmt.summary_bank_total, currency_obj=stmt.currency_id)
                    raise UserError(_('The balances are not even !\nThe book balance (%s) is different '
                                      'from the bank balance. (%s)') % (book_balance, bank_balance))
        return True

    @api.depends('date', 'locked', 'journal_id')
    def _get_unadjusted_balance(self):
        for rec in self:
            if not rec.locked:
                journal_id = rec.journal_id
                account_ids = journal_id.default_debit_account_id | journal_id.default_credit_account_id
                move_ids = self.env['account.move.line'].search([
                    ('account_id', 'in', account_ids.ids),
                    ('date', '<=', rec.date),
                    ('move_id.state', '=', 'posted')
                ])
                rec.summary_unadjusted_balance = sum(move_ids.mapped('balance'))
            else:
                rec.summary_unadjusted_balance = rec.locked_amount

    @api.depends('line_ids', 'line_ids.journal_entry_ids',
                 'intransit_payment_ids', 'outstanding_payment_ids',
                 'intransit_payment_ids.partner_id', 'intransit_payment_ids.amount', 'intransit_payment_ids.state',
                 'outstanding_payment_ids.partner_id', 'outstanding_payment_ids.amount',
                 'outstanding_payment_ids.state')
    def _get_cash_transactions_total(self):
        """  sum of all Transactions record where there is no related
        payment record found in In-Transit and Outstanding """

        for rec in self:
            transactions_per_partner = rec.line_ids.mapped('partner_id')

            for partner in transactions_per_partner:
                partner_intransits = rec.intransit_payment_ids \
                    .filtered(lambda x: x.partner_id == partner and x.state != 'cancelled')
                partner_outstandings = rec.outstanding_payment_ids \
                    .filtered(lambda x: x.partner_id == partner and x.state != 'cancelled')

                intransit_payments = partner_intransits.mapped('payment_id')
                outstanding_payments = partner_outstandings.mapped('payment_id')

                intransit_payments_grouped = intransit_payments.read_group(
                    [('id', 'in', intransit_payments.ids)],
                    ['amount'],
                    ['communication']
                )
                outstanding_payments_grouped = intransit_payments.read_group(
                    [('id', 'in', outstanding_payments.ids)],
                    ['amount'],
                    ['communication']
                )

                intransit_amounts = [d['amount'] for d in intransit_payments_grouped if 'amount' in d]
                outstanding_amounts = [d['amount'] for d in outstanding_payments_grouped if 'amount' in d]

            #     for transaction in rec.line_ids.filtered(lambda x: x.partner_id == partner and not x.journal_entry_ids):
            #         transaction_amount_abs = abs(transaction.amount)
            #         if transaction.amount > 0.0:
            #             if transaction_amount_abs not in intransit_amounts:
            #                 print('1', transaction.name)
            #                 transaction.chk_additional = True
            #             else:
            #                 intransit_amounts.remove(transaction_amount_abs)
            #                 print('2', transaction.name)
            #                 transaction.chk_additional = False
            #         else:
            #             if transaction_amount_abs not in outstanding_amounts:
            #                 print('3', transaction.name)
            #                 transaction.chk_additional = True
            #             else:
            #                 outstanding_amounts.remove(transaction_amount_abs)
            #                 print('4', transaction.name)
            #                 transaction.chk_additional = False
            #
            # for no_partner in rec.line_ids.filtered(lambda x: not x.partner_id and not x.journal_entry_ids):
            #     print('forloop', no_partner.name)
            #     no_partner.additional = True

            rec.summary_cash_transactions_total = sum([line.amount if line.chk_additional else 0 for line in rec.line_ids])

    @api.depends('cancel_intransit_total', 'currency_id', 'currency_id.symbol')
    def _get_summary_cancel_intransit_total(self):
        for rec in self:
            rec.summary_cancel_intransit_total = "(%s%s)" % (rec.currency_id.symbol, format(rec.cancel_intransit_total,
                                                                                            ',.2f'))

    @api.depends('outstanding_total', 'currency_id', 'currency_id.symbol')
    def _get_summary_outstanding_total(self):
        for rec in self:
            rec.summary_outstanding_total = "(%s%s)" % (rec.currency_id.symbol, format(rec.outstanding_total, ',.2f'))

    @api.model
    def _get_payments(self, date_to, journal_id):
        domain = [('payment_date', '<=', date_to),
                  ('journal_id', '=', journal_id),
                  ('state', 'not in', ['draft'])]
        return self.env['account.payment'].search(domain)

    @api.depends('bank_error_ids', 'bank_error_ids.amount')
    def _get_bank_adjustments(self):
        for rec in self:
            rec.summary_adjustment_bank_total = sum(rec.bank_error_ids.mapped('amount'))

    @api.depends('book_error_ids', 'book_error_ids.amount')
    def _get_book_adjustments(self):
        for rec in self:
            rec.summary_adjustment_book_total = sum(rec.book_error_ids.mapped('amount'))

    #     @api.depends('summary_unadjusted_balance','summary_cash_transactions_total','unreleased_outstanding_total','cancel_intransit_total','cancel_outstanding_total','book_error_ids','book_error_ids.amount')
    def _get_book_summary_total(self):
        for rec in self:
            rec.summary_book_total = rec.summary_unadjusted_balance + rec.summary_cash_transactions_total + rec.unreleased_outstanding_total - rec.cancel_intransit_total + rec.cancel_outstanding_total + rec.summary_adjustment_book_total

    #     @api.depends('balance_end_real','intransit_total','outstanding_total','bank_error_ids','bank_error_ids.amount')
    def _get_bank_summary_total(self):
        for rec in self:
            rec.summary_bank_total = rec.balance_end_real + rec.intransit_total - rec.outstanding_total + rec.summary_adjustment_bank_total

    @api.depends('outstanding_payment_ids', 'outstanding_payment_ids.state', 'outstanding_payment_ids.release_state',
                 'intransit_payment_ids', 'intransit_payment_ids.state', 'intransit_payment_ids.state',
                 'outstanding_payment_ids.bounced', 'intransit_payment_ids.bounced',
                 'outstanding_payment_ids.amount', 'intransit_payment_ids.amount')
    def _get_field_computations(self):
        for rec in self.filtered(lambda s: s.journal_id and s.date):
            outstanding_payment_ids = rec.outstanding_payment_ids
            intransit_payment_ids = rec.intransit_payment_ids

            cancel_intransit_payment_ids = intransit_payment_ids.filtered(lambda x: x.state == 'cancelled')
            cancel_outstanding_payment_ids = outstanding_payment_ids.filtered(lambda x: x.state == 'cancelled')
            posted_intransit_payment_ids = intransit_payment_ids - cancel_intransit_payment_ids
            posted_outstanding_payment_ids = outstanding_payment_ids - cancel_outstanding_payment_ids

            released_outstanding_ids = posted_outstanding_payment_ids.filtered(lambda x: x.release_state == 'released')
            unreleased_outstanding_ids = posted_outstanding_payment_ids - released_outstanding_ids

            cancel_intransit_total = sum(cancel_intransit_payment_ids.filtered(
                lambda x: x.payment_id.payment_type == 'inbound' and x.bounced).mapped('amount'))
            cancel_outstanding_total = sum(cancel_outstanding_payment_ids.filtered(
                lambda x: x.payment_id.payment_type == 'outbound' and x.bounced).mapped('amount'))

            all_intransit_total = sum(intransit_payment_ids.mapped('amount'))
            all_outstanding_total = sum(outstanding_payment_ids.mapped('amount'))
            unreleased_outstanding_total = sum(unreleased_outstanding_ids.mapped('amount'))
            outstanding_total = all_outstanding_total - (cancel_outstanding_total + unreleased_outstanding_total)
            intransit_total = all_intransit_total - cancel_intransit_total

            rec.all_intransit_total = all_intransit_total
            rec.all_outstanding_total = all_outstanding_total
            rec.cancel_intransit_total = cancel_intransit_total
            rec.cancel_outstanding_total = cancel_outstanding_total
            rec.outstanding_total = outstanding_total
            rec.intransit_total = intransit_total

            rec.released_outstanding_total = sum(released_outstanding_ids.mapped('amount'))
            rec.unreleased_outstanding_total = unreleased_outstanding_total
            rec.adusted_book_balance = rec.balance_end_real + outstanding_total - intransit_total

    def action_lock(self):
        for rec in self:
            rec.write({'locked_amount': rec.summary_unadjusted_balance,
                       'locked': True})

    def action_update_unadjusted_balance(self):
        for rec in self:
            rec._get_unadjusted_balance()

    def action_unlock(self):
        self.write({'locked': False})

    def open_create_unreleased_aml_wizard(self):
        self.ensure_one()

        return {
            'name': "Journal Entry Creation for Unreleased Outstanding Payments",
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'create.unreleased.aml',
            'view_id': self.env.ref('tf_ph_bank_recon.view_create_unreleased_aml_form').id,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {
                'default_ref': self.name + " for Unreleased Checks." if self.name else "For Unreleased Checks",
                'default_bank_recon_id': self.id,
                'default_bank_statement_id': self.id,
                'default_journal_id': self.journal_id.id,
                'default_currency_id': self.currency_id.id,
                'default_amount': self.unreleased_outstanding_total,
                'default_debit_account_id': self.journal_id.default_debit_account_id.id,
                'default_credit_account_id': self.journal_id.default_credit_account_id.id,
            },
        }

    def load_payments(self):
        self.ensure_one()
        self_id = self.id
        statement_date = fields.Date.from_string(self.date)
        abs_payment_model = self.env['account.bank.statement.payment']
        existing_payment_ids = self.intransit_payment_ids | self.outstanding_payment_ids
        all_payment_ids = self._get_payments(statement_date, self.journal_id.id)
        new_payment_ids = all_payment_ids.filtered(lambda x: x not in existing_payment_ids.mapped('payment_id'))

        for outstanding_payment in self.outstanding_payment_ids:
            if outstanding_payment.payment_id and outstanding_payment.payment_id.check_released:
                outstanding_payment.release_state = 'released'

        for payment_id in new_payment_ids.mapped('id'):
            abs_payment_model.create({
                'abs_id': self_id,
                'payment_id': payment_id
            })

        self._get_cash_transactions_total()


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    chk_additional = fields.Boolean('Additional Cash Transaction', default=True, copy=False)
