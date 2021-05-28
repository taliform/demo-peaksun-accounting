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
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    payment_date = fields.Date(string='Payment Date', copy=False,
                               help="The date when the Invoice transitioned from Open to Paid.")

    def _get_aml_for_register_payment(self):
        """ Get the aml to consider to reconcile in register payment """
        self.ensure_one()
        return self.line_ids.filtered(
            lambda r: not r.reconciled and r.account_id.internal_type in ('payable', 'receivable'))

    def register_payment(self, payment_line, writeoff_acc_id=False, writeoff_journal_id=False):
        """ Reconcile payable/receivable lines from the invoice with payment_line """
        line_to_reconcile = self.env['account.move.line']
        for inv in self:
            line_to_reconcile += inv._get_aml_for_register_payment()
        return (line_to_reconcile + payment_line).reconcile(writeoff_acc_id, writeoff_journal_id)

    def assign_outstanding_credit(self, credit_aml_id):
        """ Assigning the outstanding credit payment against invoice in case of Payment Adjustment is selected. """

        self.ensure_one()
        credit_aml = self.env['account.move.line'].browse(credit_aml_id)
        if not credit_aml.currency_id and self.currency_id != self.company_id.currency_id:
            amount_currency = self.company_id.currency_id._convert(credit_aml.balance, self.currency_id,
                                                                   self.company_id,
                                                                   credit_aml.date or fields.Date.today())
            credit_aml.with_context(allow_amount_currency=True, check_move_validity=False).write({
                'amount_currency': amount_currency,
                'currency_id': self.currency_id.id})
        if credit_aml.payment_id:
            credit_aml.payment_id.write({'invoice_ids': [(4, self.id, None)]})

        res = self.register_payment(credit_aml)

        if self._context.get('adjust_payment', False):
            invoice_id = self._context.get('invoice_id')
            amount = self._context.get('amount')
            credit_aml = self.env['account.move.line'].browse(credit_aml_id)
            company = self.company_id
            currency = self.currency_id

            if not credit_aml.currency_id and currency != company.currency_id:
                credit_aml.with_context(allow_amount_currency=True).write({
                    'amount_currency': company.currency_id.with_context(date=credit_aml.date).compute(amount, currency),
                    'currency_id': currency.id
                })

            if credit_aml.payment_id:
                credit_aml.payment_id.write({
                    'invoice_ids': [(4, invoice_id, None)]
                })

            return self.register_payment(credit_aml)

        return res

    def action_invoice_paid(self):
        res = super(AccountMove, self).action_invoice_paid()
        if self.payment_ids:
            max_date = max(self.payment_ids.mapped('payment_date'))
            self.write({
                'payment_date': max_date
            })
        return res

    # Service VAT Module Fields and Functions

    vat_invoice_rel_id = fields.Many2one('account.move') # RCE Journal reference to Invoice
    vat_payment_id = fields.Many2one('account.payment') # RCE Journal reference to Payment
    svc_vat_id = fields.Many2one('account.tax', string="Service VAT")
    vat_payment_ref_ids = fields.Many2many('account.payment', 'move_vat_payment_rel', 'move_id', 'payment_id',
                                           string="Payment Ref") # Invoice Reference to Payments
    service_vat_ids = fields.One2many('account.move', 'vat_invoice_rel_id', string='Service VATs')
    payment_ids = fields.Many2many('account.payment',
                                   'account_invoice_payment_rel', 'invoice_id', 'payment_id',
                                   string="Payments", copy=False, readonly=True)
    payment_move_line_ids = fields.Many2many('account.move.line', string='Payment Move Lines',
                                             compute='_compute_payments', store=True)

    @api.depends('line_ids.amount_residual')
    def _compute_payments(self):
        for rec in self:
            payment_lines = set()

            # Get Account
            if rec.partner_id:
                if rec.is_sale_document(include_receipts=True):
                    account = rec.partner_id.commercial_partner_id.property_account_receivable_id
                elif rec.is_purchase_document(include_receipts=True):
                    account = rec.partner_id.commercial_partner_id.property_account_payable_id
                else:
                    account = None
            else:
                if rec.is_sale_document(include_receipts=True):
                    account = rec.journal_id.default_credit_account_id
                elif rec.is_purchase_document(include_receipts=True):
                    account = rec.journal_id.default_debit_account_id
                else:
                    account = None
                    
            if account:
                for line in rec.line_ids.filtered(lambda l: l.account_id.id == account.id):
                    payment_lines.update(line.mapped('matched_credit_ids.credit_move_id.id'))
                    payment_lines.update(line.mapped('matched_debit_ids.debit_move_id.id'))

            rec.payment_move_line_ids = self.env['account.move.line'].browse(list(payment_lines)).sorted()


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    withholding_tax_id = fields.Many2one('account.tax', string='Withholding Tax', ondelete='cascade')

    def _check_reconcile_validity(self):
        # Perform all checks on lines
        company_ids = set()
        all_accounts = []
        for line in self:
            company_ids.add(line.company_id.id)
            all_accounts.append(line.account_id)

            # If not from Payment Adjustment
            if line.payment_id:
                if not line.payment_id.payment_method_type == 'adjustment':
                    if line.reconciled:
                        raise UserError(_('You are trying to reconcile some entries that are already reconciled.'))
            else:
                if line.reconciled:
                    raise UserError(_('You are trying to reconcile some entries that are already reconciled.'))

        if len(company_ids) > 1:
            raise UserError(_('To reconcile the entries company should be the same for all entries.'))
        if len(set(all_accounts)) > 1:
            raise UserError(_('Entries are not from the same account.'))
        if not (all_accounts[0].reconcile or all_accounts[0].internal_type == 'liquidity'):
            raise UserError(_('Account %s (%s) does not allow reconciliation. '
                              'First change the configuration of this account to allow it.') % (
                                all_accounts[0].name, all_accounts[0].code))

    def _create_writeoff(self, writeoff_vals):
        res = super(AccountMoveLine, self)._create_writeoff(writeoff_vals)

        if res._name == 'account.move.line':
            line_ids = res.move_id.line_ids
        elif res._name == 'account.move':
            line_ids = res.line_ids

        if writeoff_vals[0].get('withholding_tax_id', False):
            wht_id = writeoff_vals[0]['withholding_tax_id']['id']
            wht_tax_id = self.env['account.tax'].browse(wht_id)

            for line_id in line_ids:
                if line_id.account_id == wht_tax_id.account_id:
                    line_id.write({
                        'tax_line_id': wht_id
                    })

        return res

    def prepare_move_lines_for_reconciliation_widget(self, target_currency=False, target_date=False):
        move_lines = super(AccountMoveLine, self).prepare_move_lines_for_reconciliation_widget(
            target_currency=target_currency, target_date=target_date)

        for move_line in move_lines:
            move_line_id = self.browse(move_line.get('id', False))
            if move_line_id:
                invoice_id = move_line_id.invoice_id
                base_amount = invoice_id.amount_untaxed if invoice_id else 0.0
                move_line.update({
                    'tax_line_id': move_line_id.tax_line_id.ids,
                    'base_amount': base_amount
                })

        return move_lines

    @api.model
    def _compute_amount_fields(self, amount, src_currency, company_currency):
        """ Helper function to compute value for fields debit/credit/amount_currency based on an amount and the currencies given in parameter"""
        amount_currency = False
        currency_id = False
        date = self.env.context.get('date') or fields.Date.today()
        company = self.env.context.get('company_id')
        company = self.env['res.company'].browse(company) if company else self.env.user.company_id
        if src_currency and src_currency != company_currency:
            amount_currency = amount
            amount = src_currency._convert(amount, company_currency, company, date)
            currency_id = src_currency.id
        debit = amount > 0 and amount or 0.0
        credit = amount < 0 and -amount or 0.0
        return debit, credit, amount_currency, currency_id

    # Service VAT Module Fields and Functions

    def reconcile(self, writeoff_acc_id=False, writeoff_journal_id=False):
        res = super(AccountMoveLine, self).reconcile(writeoff_acc_id=writeoff_acc_id,
                                                     writeoff_journal_id=writeoff_journal_id)

        wh_aml_ids = self.filtered(lambda x: x.type == 'entry' and not x.payment_id)
        other_amounts = sum(wh_aml_ids.mapped('balance'))

        # filter account.move from journal entries and vendor bills (manual generation if vendor bills)
        invoice_ids = self.filtered(lambda l: l.type not in ['entry', 'in_invoice']).mapped('move_id')
        payment_ids = self.mapped('payment_id')
        # mark vendor payments if valid for future reclass
        payment_ids.is_vendor_valid_for_reclass()

        if invoice_ids and payment_ids:
            payment_ids.create_reclass_entry(invoice_ids, other_amounts)
        return res