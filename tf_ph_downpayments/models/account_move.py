# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Bamboo <martin@taliform.com>
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
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_customer_advance = fields.Boolean('Customer Advance')
    is_downpayment = fields.Boolean("Supplier Downpayment")
    total_downpayment = fields.Monetary(related='amount_total', string="Total Down Payment")
    remaining_downpayment = fields.Monetary(string="Remaining Down Payment", _compute='_get_remaining_downpayment',
                                            store=True)
    downpayment_ids = fields.One2many('account.payment', 'dp_id', "Downpayments")

    def action_release_dp(self):
        for rec in self:
            pay_term_line_ids = rec.line_ids.filtered(
                lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
            partials = pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped('matched_credit_ids')
            for partial in partials:
                counterpart_lines = partial.debit_move_id + partial.credit_move_id
                counterpart_line = counterpart_lines.filtered(lambda line: line.id not in self.line_ids.ids)
                payment_id = counterpart_line.payment_id
                rec.create_customer_advance_payment(payment_id, payment_id.amount)

    @api.depends('downpayment_ids', 'downpayment_ids.amount_residual')
    def _get_remaining_downpayment(self):
        for rec in self:
            rec.remaining_downpayment = sum(rec.downpayment_ids.mapped('amount_residual'))

    def create_customer_advance_payment(self, payment_id, amount):
        aml_obj = self.env['account.move.line']
        manual_method_id = self.env.ref('account.account_payment_method_manual_in').id
        for rec in self:
            payment_type = 'inbound'
            partner_type = 'customer'

            if rec.type == 'in_invoice':
                payment_type = 'outbound'
                partner_type = 'supplier'

            advance_payment_id = rec.env['account.payment'].create({
                'dp_id': rec.id,
                'payment_type': payment_type,
                'partner_type': partner_type,
                'payment_method_type': 'advance',
                'payment_method_id': manual_method_id,
                'payment_reference': rec.name,
                'partner_id': rec.env['res.partner']._find_accounting_partner(rec.partner_id).id,
                'amount': amount,
                'currency_id': payment_id.currency_id.id,
                'payment_date': payment_id.payment_date,
                'journal_id': rec.journal_id.id,
                'invoice_ids': []
            })
            advance_payment_id.post()
            payment_id.generated_payment_id = advance_payment_id
            rec._get_remaining_downpayment()


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    dp_id = fields.Many2one('account.move', "Down Payment Invoice")
    generated_payment_id = fields.Many2one('account.payment', "Generated Down Payment Credits")
    amount_residual = fields.Monetary(
        compute='_amount_residual', string='Residual Amount', store=True, currency_field='currency_id')

    # def post(self):
    #     res = super(AccountPayment, self).post()
    #     for rec in self:
    #         if rec.payment_method_type == 'adjustment':
    #             for payment_inv_line_id in rec.payment_inv_line_ids.filtered_domain([('allocation', '>', 0)]):
    #                 invoice_id = payment_inv_line_id.invoice_id
    #                 if invoice_id.is_customer_advance or invoice_id.is_downpayment:
    #                     invoice_id.create_customer_advance_payment(rec, payment_inv_line_id.allocation)
    #         else:
    #             rec.invoice_ids.filtered(
    #                 lambda i: i.is_customer_advance or i.is_downpayment).create_customer_advance_payment(
    #                 rec, rec.amount)
    #     return res

    @api.depends('move_line_ids',
                 'move_line_ids.amount_residual',
                 'move_line_ids.amount_residual_currency')
    def _amount_residual(self):
        for payment_id in self:
            amount_residual = 0.0
            amount_residual_currency = 0.0
            journal_id = payment_id.journal_id
            pay_acc = journal_id.default_debit_account_id or journal_id.default_credit_account_id
            for aml_id in payment_id.move_line_ids.filtered(
                    lambda x: x.account_id.reconcile and x.account_id != pay_acc):
                amount_residual += aml_id.amount_residual
                amount_residual_currency += aml_id.amount_residual_currency
            if payment_id.payment_type == 'inbound':
                amount_residual *= -1
                amount_residual_currency *= -1
            if payment_id.currency_id != payment_id.company_id.currency_id:
                payment_id.amount_residual = amount_residual_currency
            else:
                payment_id.amount_residual = amount_residual
            payment_id.dp_id._get_remaining_downpayment()


class AccountPaymentCancel(models.TransientModel):
    _inherit = 'account.payment.cancel'

    def cancel_payment(self):
        res = super(AccountPaymentCancel, self).cancel_payment()
        payment_ids = self._context.get('active_ids', False)
        payment_ids = self.env['account.payment'].browse(payment_ids)
        generated_payment_ids = payment_ids.mapped('generated_payment_id')

        # Cancel generated downpayment credits if downpayment invoice is cancelled
        if generated_payment_ids:
            self.env['account.payment.cancel'].create({
                'date': self.date,
                'journal_id': self.journal_id.id,
                'cancel_reason': self.cancel_reason
            }).with_context({'active_ids': generated_payment_ids.ids}).cancel_payment()

        return res