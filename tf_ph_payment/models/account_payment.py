# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
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
import json
from itertools import groupby

from lxml import etree

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval
from odoo.addons.base.models.ir_ui_view import transfer_field_to_modifiers, transfer_modifiers_to_node, transfer_node_to_modifiers

MAP_INVOICE_TYPE_PAYMENT_SIGN = {
    'out_invoice': 1,
    'out_receipt': 1,
    'in_refund': -1,
    'in_invoice': -1,
    'in_receipt': -1,
    'out_refund': 1,
}


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    amount_total = fields.Float("Payment Amount", compute="_get_payment_amount")
    check_no = fields.Char('Check No.')
    payment_receipt = fields.Char(string='Payment Receipt', copy=False)
    wht_tax_id = fields.Many2one('account.tax', 'Withholding Tax')
    wht_account_id = fields.Many2one('account.account', 'Withholding Account')
    wht_amount = fields.Monetary('Withholding Amount')
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  default=lambda self: self.env.user.company_id.currency_id)
    payment_type = fields.Selection(related='payment_method_id.payment_type')

    @api.depends('wht_amount', 'invoice_ids')
    def _get_payment_amount(self):
        self.amount_total = sum(self.invoice_ids.mapped('amount_total')) - self.wht_amount

    @api.onchange('wht_tax_id')
    def _onchange_wh_tax_id(self):
        for rec in self:
            wht_tax_id = rec.wht_tax_id
            wht_amount = 0.0
            wht_account_id = False
            if wht_tax_id:
                wht_tax_base_amount = sum(rec.invoice_ids.mapped('amount_untaxed'))
                wht_amount = -wht_tax_id._compute_amount(wht_tax_base_amount, wht_tax_base_amount)
                wht_account_id = wht_tax_id.account_id

            rec.wht_amount = wht_amount
            rec.wht_account_id = wht_account_id

    def create_payments(self):
        '''Create payments according to the invoices.
        Having invoices with different commercial_partner_id or different type
        (Vendor bills with customer invoices) leads to multiple payments.
        In case of all the invoices are related to the same
        commercial_partner_id and have the same type, only one payment will be
        created.

        :return: The ir.actions.act_window to show created payments.
        '''
        Payment = self.env['account.payment']
        payments = Payment.create(self.get_payments_vals())
        payments.with_context(self._context).post()

        action_vals = {
            'name': _('Payments'),
            'domain': [('id', 'in', payments.ids), ('state', '=', 'posted')],
            'res_model': 'account.payment',
            'view_id': False,
            'type': 'ir.actions.act_window',
        }
        if len(payments) == 1:
            action_vals.update({'res_id': payments[0].id, 'view_mode': 'form'})
        else:
            action_vals['view_mode'] = 'tree,form'
        return action_vals


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.depends('wht_tax_id', 'payment_difference_handling', 'payment_type')
    def _hide_wht(self):
        for rec in self:
            rec.hide_withholding = False
            # In case, the user paid the invoice from invoice form/list view
            if rec.payment_difference_handling == 'open':
                rec.hide_withholding = True
            if rec.payment_type == 'transfer':
                rec.hide_withholding = True
            if rec.wht_tax_id:
                rec.hide_withholding = False

    @api.constrains('amount', 'payment_method_type', 'payment_difference_handling', 'payment_difference')
    def _check_constrains(self):
        if self.payment_method_type == 'adjustment':
            total_allocation = sum(self.payment_inv_line_ids.mapped('allocation'))
            for line_id in self.payment_inv_line_ids.filtered(lambda l: l.allocation > 0.0):
                # Full reconcile
                if self.payment_difference and self.payment_difference_handling == 'reconcile':
                    if not line_id.full_reconcile:
                        raise ValidationError(_('Mark the payment allocation lines as Full Reconcile.'))

            # Not fully reconcile
            if self.payment_difference_handling == 'open' and self.payment_difference:
                if self.amount != total_allocation:
                    raise ValidationError(_('The payment difference should be zero. '
                                            'Change the payment handling to Mark invoice as fully paid'))

                elif total_allocation <= 0.0:
                    raise ValidationError(_('The total allocated amount should not be less than or equal to zero.'))

        if self.wht_amount < 0:
            raise ValidationError(_('Withholding amount should not be less than zero.'))

    hide_withholding = fields.Boolean(compute='_hide_wht')
    wht_tax_id = fields.Many2one('account.tax', 'Withholding Tax', copy=False)
    wht_account_id = fields.Many2one('account.account', 'Withholding Account', copy=False)
    wht_amount = fields.Monetary('Withholding Amount', copy=False)
    multiple_wth_tax = fields.Boolean(copy=False)
    payment_inv_line_ids = fields.One2many('account.payment.invoice.line', 'payment_id',
                                           string="Invoice Adjustment Lines", copy=False)
    payment_crdr_inv_line_ids = fields.One2many('account.payment.crdr.invoice.line', 'payment_id',
                                                string="CRDRInvoice Adjustment Lines", copy=False)
    payment_charge_line_ids = fields.One2many('account.payment.charge.line', 'payment_id', string="Charge Lines",
                                              copy=False)
    payment_withholding_ids = fields.One2many('account.payment.withholding.line', 'payment_id',
                                              string="Withholding Lines", copy=False)
    payment_method_type = fields.Selection([
        ('advance', 'Advance Payment'),
        ('adjustment', 'Payment Reconciliation')
    ],
        'Method of Payment', default='advance', copy=True,
        help="Advance Payment: Default functionality.\n"
             "Payment Reconciliation: Make payment allocation amount against each invoice dues.")
    payment_receipt = fields.Char(string='Payment Receipt', copy=False)
    or_no = fields.Char("O.R. Number")
    or_date = fields.Date("O.R. Date")

    @api.model
    def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
        res = super(AccountPayment, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                          submenu=submenu)
        if view_type == 'form':
            try:
                doc = etree.XML(res['fields']['payment_inv_line_ids']['views']['tree']['arch'])
                o2m_fields = res['fields']['payment_inv_line_ids']['views']['tree']['fields']
                doc2 = etree.XML(res['fields']['payment_crdr_inv_line_ids']['views']['tree']['arch'])
                o2m_fields2 = res['fields']['payment_crdr_inv_line_ids']['views']['tree']['fields']

                for field in doc.xpath("//field"):
                    if self._context.get('default_partner_type', False):
                        if self._context['default_partner_type'] == 'supplier' and field.attrib['name'] == 'reference':
                            field.set('string', 'Vendor Ref')
                            setup_modifiers(field, o2m_fields[field.attrib['name']])

                res['fields']['payment_inv_line_ids']['views']['tree']['arch'] = etree.tostring(doc, encoding='unicode')

                for field in doc2.xpath("//field"):
                    if self._context.get('default_partner_type', False):
                        if self._context['default_partner_type'] == 'supplier' and field.attrib['name'] == 'reference':
                            field.set('string', 'Vendor Ref')
                            setup_modifiers(field, o2m_fields2[field.attrib['name']])

                res['fields']['payment_crdr_inv_line_ids']['views']['tree']['arch'] = etree.tostring(doc,
                                                                                                     encoding='unicode')

            except:
                pass
        return res

    @api.onchange('multiple_wth_tax')
    def _onchange_mult_wh_tax(self):
        if self.multiple_wth_tax:
            self.wht_amount = 0.0
            self.wht_tax_id = self.wht_account_id = False

    @api.onchange('wht_amount')
    def _onchange_wht_amount(self):
        for rec in self:
            payment_amount = 0
            if rec.invoice_ids:
                payment_amount = rec._compute_payment_amount(
                    rec.invoice_ids,
                    rec.currency_id,
                    rec.journal_id,
                    rec.payment_date
                )
            else:
                payment_amount = sum(rec.payment_inv_line_ids.mapped('allocation'))

            if rec.wht_amount:
                rec.amount = abs(payment_amount) - rec.wht_amount
            else:
                rec.amount = payment_amount

    @api.onchange('wht_tax_id')
    def _onchange_wh_tax_id(self):
        for rec in self:
            wht_tax_id = rec.wht_tax_id
            wht_amount = 0.0
            wht_account_id = False

            if wht_tax_id:
                if rec.payment_method_type == 'adjustment':
                    invoice_ids = self.env['account.move']
                    for line_id in rec.payment_inv_line_ids.filtered(lambda l: l.allocation > 0.0):
                        invoice_ids += line_id.invoice_id
                    wht_tax_base_amount = sum(invoice_ids.mapped('amount_untaxed'))
                else:
                    wht_tax_base_amount = sum(rec.invoice_ids.mapped('amount_untaxed'))
                wht_amount = - wht_tax_id._compute_amount(wht_tax_base_amount, wht_tax_base_amount)
                wht_account_id = wht_tax_id.account_id

            rec.wht_amount = wht_amount
            rec.wht_account_id = wht_account_id

    @api.model
    def create(self, vals):
        res = super(AccountPayment, self).create(vals)
        if res.payment_method_type == 'adjustment':
            if res.payment_inv_line_ids:
                data = []
                for line in res.payment_inv_line_ids:
                    if line.invoice_id in data:
                        raise UserError(_('There are duplicate invoices selected.'))
                    data.append(line.invoice_id)
                    line.balance_amount = line.invoice_id.amount_residual
            if res.payment_difference_handling == 'open':
                # Reset values
                res.wht_tax_id = res.wht_account_id = False
                res.wh_amount = 0.0
        return res

    def write(self, vals):
        # Add or Replace existing check no in memo when updated
        new_check_no = vals.get('check_no', False)
        if new_check_no:
            memo = self.communication
            old_check_no = self.check_no
            if old_check_no and old_check_no in memo:
                vals['communication'] = memo.replace(old_check_no, new_check_no)
            else:
                vals['communication'] = "%s, %s" % (new_check_no, memo)

        res = super(AccountPayment, self).write(vals)
        for rec in self:
            if rec.payment_method_type == 'adjustment':
                if rec.payment_inv_line_ids:
                    data = []
                    for line in rec.payment_inv_line_ids:
                        if line.invoice_id in data: raise UserError(_('There are duplicate invoices selected.'))
                        data.append(line.invoice_id)
                payment_handling = vals.get('payment_difference_handling', False)
                if payment_handling and payment_handling == 'open':
                    # Reset values
                    rec.wht_tax_id = rec.wht_account_id = False
                    rec.wh_amount = 0.0
        return res

    @api.onchange('payment_type')
    def _onchange_payment_type(self):
        line_vals = []
        res = super(AccountPayment, self)._onchange_payment_type()
        if self.payment_type == 'transfer':
            self.payment_method_type = 'advance'
            self.payment_inv_line_ids = line_vals

        return res

    @api.onchange('partner_id', 'payment_method_type', )
    def _onchange_partner_id(self):
        res = super(AccountPayment, self)._onchange_partner_id()
        AccountInvoice = self.env['account.move']
        self.payment_inv_line_ids = self.payment_crdr_inv_line_ids = inv_type = inv_crdr_type = False
        invoice_lines = []
        invoice_crdr_lines = []

        if self.payment_type == 'inbound':
            inv_type = ['out_invoice', 'out_receipt']
            inv_crdr_type = 'out_refund'
        elif self.payment_type == 'outbound':
            inv_type = ['in_invoice', 'in_receipt']
            inv_crdr_type = 'in_refund'

        invoice_ids = AccountInvoice.search([
            ('partner_id', '=', self.partner_id.id),
            ('state', '=', 'posted'),
            ('type', 'in', inv_type),
            ('invoice_payment_state', '=', 'not_paid')
        ])
        invoice_crdr_ids = AccountInvoice.search([
            ('partner_id', '=', self.partner_id.id),
            ('state', '=', 'posted'),
            ('type', '=', inv_crdr_type),
            ('invoice_payment_state', '=', 'not_paid')
        ])

        if self.payment_method_type == 'adjustment' and self.partner_id:
            if not invoice_ids and not invoice_crdr_ids:
                raise ValidationError(_('There are no open invoices for the selected partner.'))

        # Populate Payment Invoice Lines
        if invoice_ids:
            for inv_id in invoice_ids:
                is_pdc = False
                if inv_id.pdc_line_ids:
                    is_pdc = True
                vals = {
                    'payment_id': self.id,
                    'invoice_id': inv_id.id,
                    'balance_amount': inv_id.amount_residual,
                }
                invoice_lines.append((0, 0, vals))

            self.payment_inv_line_ids = invoice_lines

        # Populate Payment CRDR Invoice Lines
        if invoice_crdr_ids:
            for inv_id in invoice_crdr_ids:
                vals = {
                    'payment_id': self.id,
                    'invoice_id': inv_id.id,
                    'balance_amount': inv_id.amount_residual,
                    'full_reconcile': True,
                    'allocation': inv_id.amount_residual
                }
                invoice_crdr_lines.append((0, 0, vals))

            self.payment_crdr_inv_line_ids = invoice_crdr_lines

        return res

    def _get_shared_move_line_vals(self, debit, credit, amount_currency):
        """ Returns values common to both move lines (except for debit, credit and amount_currency which are reversed)
        """
        if self.payment_difference_handling == 'open' and not self.payment_difference and not self._context.get(
                'credit_aml', False):
            if self.payment_method_type == 'adjustment' \
                    and debit > 0.0 \
                    and not amount_currency \
                    and self.partner_type == 'customer':
                debit = 0.0
                for inv_id in self.payment_inv_line_ids.filtered(lambda l: l.allocation > 0.0):
                    debit += inv_id.allocation

            elif self.payment_method_type == 'adjustment' \
                    and credit > 0.0 \
                    and not amount_currency \
                    and self.partner_type == 'supplier':
                credit = 0.0
                for inv_id in self.payment_inv_line_ids.filtered(lambda l: l.allocation > 0.0):
                    credit += inv_id.allocation

        return {
            'partner_id':
                self.payment_type in ('inbound', 'outbound')
                and self.env['res.partner']._find_accounting_partner(self.partner_id).id
                or False,
            # 'invoice_id': invoice_id and invoice_id.id or False,
            'debit': debit,
            'credit': credit,
            'amount_currency': amount_currency or False,
            'payment_id': self.id,
            'journal_id': self.journal_id.id,
        }

    def _prepare_payment_moves(self):
        move_vals = super(AccountPayment, self)._prepare_payment_moves()

        for payment in self:
            if payment.wht_amount and payment.wht_tax_id:
                company_currency = payment.company_id.currency_id.id
                if move_vals[0]['currency_id'] == company_currency:
                    # Single-currency.
                    balance = -payment.wht_amount
                    currency_id = False
                else:
                    # Multi-currencies.
                    balance = -payment.currency_id._convert(payment.wht_amount, company_currency, payment.company_id,
                                                            payment.payment_date)
                    currency_id = payment.currency_id.id

                # Add withholding amount to receivable line
                for move_line in move_vals[0]['line_ids']:
                    if move_line[2]['credit'] > 0:
                        move_line[2]['credit'] += payment.wht_amount
                    break

                # Add withholding journal item
                move_vals[0]['line_ids'].append((0, 0, {
                    'name': payment.wht_tax_id.description,
                    'amount_currency': balance if currency_id else 0.0,
                    'currency_id': currency_id,
                    'debit': balance < 0.0 and -balance or 0.0,
                    'credit': balance > 0.0 and balance or 0.0,
                    'date_maturity': payment.payment_date,
                    'partner_id': payment.partner_id.commercial_partner_id.id,
                    'account_id': payment.wht_tax_id.account_id.id,
                    'payment_id': payment.id,
                }))

        return move_vals

    def _get_move_vals(self, journal=None):
        """ Return dict to create the payment move
        """
        journal = journal or self.journal_id

        move_vals = {
            'date': self.payment_date,
            'ref': self.communication or '',
            'company_id': self.company_id.id,
            'journal_id': journal.id,
            'line_ids': []
        }

        name = False
        if self.move_name:
            names = self.move_name.split(self._get_move_name_transfer_separator())
            if self.payment_type == 'transfer':
                if journal == self.destination_journal_id and len(names) == 2:
                    name = names[1]
                elif journal == self.destination_journal_id and len(names) != 2:
                    # We are probably transforming a classical payment into a transfer
                    name = False
                else:
                    name = names[0]
            else:
                name = names[0]

        if name:
            move_vals['name'] = name
        return move_vals

    def _get_counterpart_move_line_vals(self, invoice=False):
        if self.payment_type == 'transfer':
            name = self.name
        else:
            name = ''
            if self.partner_type == 'customer':
                if self.payment_type == 'inbound':
                    name += _("Customer Payment")
                elif self.payment_type == 'outbound':
                    name += _("Customer Credit Note")
            elif self.partner_type == 'supplier':
                if self.payment_type == 'inbound':
                    name += _("Vendor Credit Note")
                elif self.payment_type == 'outbound':
                    name += _("Vendor Payment")
            if invoice:
                name += ': '
                for inv in invoice:
                    name += inv.name + ', '
                name = name[:len(name)-2]
        return {
            'name': name,
            'account_id': self.destination_account_id.id,
            'currency_id': self.currency_id != self.company_id.currency_id and self.currency_id.id or False,
        }

    def _get_liquidity_move_line_vals(self, amount):
        name = self.name
        if self.payment_type == 'transfer':
            name = _('Transfer to %s') % self.destination_journal_id.name
        vals = {
            'name': name,
            'account_id': self.payment_type in ('outbound', 'transfer') and self.journal_id.default_debit_account_id.id or self.journal_id.default_credit_account_id.id,
            'journal_id': self.journal_id.id,
            'currency_id': self.currency_id != self.company_id.currency_id and self.currency_id.id or False,
        }

        # If the journal has a currency specified, the journal item need to be expressed in this currency
        if self.journal_id.currency_id and self.currency_id != self.journal_id.currency_id:
            amount = self.currency_id._convert(amount, self.journal_id.currency_id, self.company_id, self.payment_date or fields.Date.today())
            debit, credit, amount_currency, dummy = self.env['account.move.line'].with_context(date=self.payment_date)._compute_amount_fields(amount, self.journal_id.currency_id, self.company_id.currency_id)
            vals.update({
                'amount_currency': amount_currency,
                'currency_id': self.journal_id.currency_id.id,
            })

        return vals

    def _create_payment_entry(self, amount):
        """ Create a journal entry corresponding to a payment, if the payment references invoice(s) they are reconciled.
            Return the journal entry.
        """
        all_move_vals = []

        AccountMoveLine = self.env['account.move.line'].with_context(check_move_validity=False)
        AccountTax = self.env['account.tax']
        with_wht = False
        amount_orig = amount
        # print("amount: ", amount)
        # Register Payment Wizard
        if self._context.get('wht_from_invoice', False) \
                and self._context.get('wht_amount', False) \
                and self._context.get('wht_tax_id', False) \
                and self._context.get('wht_account_id', False):
            # Add withholding amount
            amount = amount - self._context.get('wht_amount')
            with_wht = True

        debit, credit, amount_currency, currency_id = AccountMoveLine.with_context(
            date=self.payment_date)._compute_amount_fields(amount, self.currency_id, self.company_id.currency_id)

        wht_tax_id = False
        invoice_id = False
        memo = False
        counterpart_aml = {}
        line_invoice_ids = self.env['account.move']
        total_inv_amount = 0.0
        debit_chn = debit
        credit_chn = credit

        for rec in self:
            move_vals = rec._get_move_vals()

            # Register Payment Wizard (Assign PDC then Confirmed)
            if rec.wht_tax_id and rec.wht_amount and not rec.payment_inv_line_ids and not with_wht:
                # Add withholding amount
                amount = amount_orig - rec.wht_amount
                debit, credit, amount_currency, currency_id = AccountMoveLine \
                    .with_context(date=rec.payment_date) \
                    ._compute_amount_fields(amount, rec.currency_id, rec.company_id.currency_id)
                with_wht = True

            for line_id in rec.payment_inv_line_ids.filtered(lambda l: l.allocation > 0.0):
                line_invoice_ids += line_id.invoice_id
                total_inv_amount += line_id.allocation

                if rec.check_no:
                    rec.communication = rec.check_no
                if not memo and not rec.communication:
                    rec.communication = line_id.invoice_id.name
                    if line_id.reference:
                        rec.communication = rec.communication + '/' + line_id.reference
                else:
                    if line_id.reference:
                        rec.communication = rec.communication + ', ' + line_id.invoice_id.name + '/' + line_id.reference
                    else:
                        rec.communication = rec.communication + ', ' + line_id.invoice_id.name
                line_id.balance_amount = line_id.invoice_id.amount_residual

            # Credit Notes
            for line_id in rec.payment_crdr_inv_line_ids.filtered(lambda l: l.allocation > 0.0):
                line_invoice_ids += line_id.invoice_id
                total_inv_amount += line_id.allocation

                if rec.check_no:
                    if rec.communication:
                        rec.communication += rec.check_no
                    else:
                        rec.communication = rec.check_no

                if not memo and not rec.communication:
                    rec.communication = line_id.invoice_id.name
                    if line_id.reference:
                        rec.communication = rec.communication + '/' + line_id.reference
                else:
                    if line_id.reference:
                        rec.communication = rec.communication + ', ' + line_id.invoice_id.name + '/' + line_id.reference
                    else:
                        rec.communication = rec.communication + ', ' + line_id.invoice_id.name

                line_id.balance_amount = line_id.invoice_id.amount_residual

            # Write line corresponding to invoice payment
            # PAYMENT ADJUSTMENT
            if rec.payment_method_type == 'adjustment':
                # print("ADJUSTMENT")
                # Full Reconcile
                if rec.payment_difference_handling == 'reconcile' and rec.payment_difference:
                    rec.invoice_ids = line_invoice_ids
                    counterpart_aml_dict = rec._get_shared_move_line_vals(
                        debit,
                        credit,
                        amount_currency
                    )
                    counterpart_aml_dict.update(rec._get_counterpart_move_line_vals(rec.invoice_ids))
                    counterpart_aml_dict.update({'currency_id': currency_id})
                    # print("counterpart_aml_dict A: ", counterpart_aml_dict)
                    move_vals['line_ids'].append((0, 0, counterpart_aml_dict))
                else:
                    # Amount is greater than the total allocated amount (Amount will change to Total Allocation)
                    if rec.payment_difference_handling == 'reconcile' and rec.amount > total_inv_amount:
                        rec.invoice_ids = line_invoice_ids
                        if debit != 0.0:
                            debit_chn = total_inv_amount
                        else:
                            credit_chn = total_inv_amount
                        counterpart_aml_dict = rec._get_shared_move_line_vals(
                            debit_chn,
                            credit_chn,
                            amount_currency
                        )
                        counterpart_aml_dict.update(rec._get_counterpart_move_line_vals(rec.invoice_ids))
                        counterpart_aml_dict.update({'currency_id': currency_id})
                        # print("counterpart_aml_dict B: ", counterpart_aml_dict)
                        move_vals['line_ids'].append((0, 0, counterpart_aml_dict))
                    else:
                        # Payment Invoice Lines
                        debit_adj = credit_adj = 0.0
                        invoice_ids = []
                        for payment_id in rec.payment_inv_line_ids.filtered(lambda l: l.allocation > 0.0):
                            if rec.payment_difference_handling == 'reconcile':
                                if not payment_id.full_reconcile and payment_id.allocation == payment_id.balance_amount:
                                    raise ValidationError(_('Mark the payment allocation lines as Full Reconcile.'))

                            invoice_id = payment_id.invoice_id
                            invoice_ids.append(invoice_id.id)
                            if invoice_id.type in ['out_invoice', 'out_receipt']:
                                credit_adj = payment_id.allocation
                            else:
                                credit_adj = 0.0
                            if invoice_id.type in ['in_invoice', 'in_receipt']:
                                debit_adj = payment_id.allocation
                            else:
                                debit_adj = 0.0

                            counterpart_aml_dict = rec._get_shared_move_line_vals(
                                debit_adj,
                                credit_adj,
                                amount_currency
                            )
                            counterpart_aml_dict.update(rec._get_counterpart_move_line_vals(payment_id.invoice_id))
                            # print("counterpart_aml_dict C: ", counterpart_aml_dict)
                            counterpart_aml_dict.update({'currency_id': currency_id})
                            move_vals['line_ids'].append((0, 0, counterpart_aml_dict))
                            # payment_id.invoice_id.with_context(adjust_payment=True, invoice_id=payment_id.invoice_id.id,
                            #                                    amount=credit_adj)\
                            #     .assign_outstanding_credit(counterpart_aml.id)
                        rec.invoice_ids = invoice_ids
                        # Credit Notes
                        debit_adj = credit_adj = 0.0
                        for payment_id in rec.payment_crdr_inv_line_ids.filtered(lambda l: l.allocation > 0.0):
                            if rec.payment_difference_handling == 'reconcile':
                                if not payment_id.full_reconcile and payment_id.allocation == payment_id.balance_amount:
                                    raise ValidationError(_('Mark the payment allocation lines as Full Reconcile.'))

                            invoice_id = payment_id.invoice_id
                            if invoice_id.type == 'out_refund':
                                debit_adj = payment_id.allocation
                            else:
                                debit_adj = 0.0
                            if invoice_id.type == 'in_refund':
                                credit_adj = payment_id.allocation
                            else:
                                credit_adj = 0.0

                            counterpart_aml_dict = rec.with_context(credit_aml=True)._get_shared_move_line_vals(
                                debit_adj,
                                credit_adj,
                                amount_currency
                            )
                            rec.payment_type = 'outbound'
                            counterpart_aml_dict.update(rec._get_counterpart_move_line_vals(invoice_id))
                            counterpart_aml_dict.update({'currency_id': currency_id})
                            # counterpart_aml = AccountMoveLine.create(counterpart_aml_dict)
                            move_vals['line_ids'].append((0, 0, counterpart_aml_dict))
                            # counterpart_aml.invoice_id.with_context(adjust_payment=True,
                            #                                         invoice_id=counterpart_aml.invoice_id.id,
                            #                                         amount=credit_adj).assign_outstanding_credit(
                            #     counterpart_aml.id)
                            # print("counterpart_aml_dict D: ", counterpart_aml_dict)
            else:
                if self._context.get('invoice_id', False):
                    invoice_id = self._context.get('invoice_id')
                print("ADVANCE PAYMENT")
                amount_total = 0.0

                invoice_names = ''
                invoice_refs = ''
                ctr = 0
                invoice_len = len(rec.invoice_ids)

                if rec.invoice_ids:
                    for invoice in rec.invoice_ids:
                        amount_total += invoice.amount_total
                        ctr += 1
                        if rec.communication:
                            invoice_names += invoice.name
                            if invoice.ref:
                                invoice_refs += invoice.ref
                            if invoice_len > 0 and ctr < invoice_len:
                                invoice_names += ', '
                                if invoice.ref:
                                    invoice_refs += ', '
                else:
                    amount_total = rec.amount + rec.wht_amount

                rec.communication = f'{rec.check_no+", " if rec.check_no else ""}' \
                                    f'{rec.communication}' \
                                    f'{", "+invoice_names if invoice_names else ""}' \
                                    f'{" / "+invoice_refs if invoice_refs else ""}'

                if rec.payment_difference_handling == 'open' and amount_total > rec.amount + rec.wht_amount:
                    amount_total = rec.amount + rec.wht_amount

                if rec.payment_type == 'inbound':
                    counterpart_aml_dict = rec._get_shared_move_line_vals(
                        debit,
                        amount_total,
                        amount_currency
                    )
                else:
                    counterpart_aml_dict = rec._get_shared_move_line_vals(
                        amount_total,
                        credit,
                        amount_currency
                    )

                counterpart_aml_dict.update(rec._get_counterpart_move_line_vals(rec.invoice_ids))
                counterpart_aml_dict.update({'currency_id': currency_id})
                print("counterpart_aml_dict wizard: ", counterpart_aml_dict)
                move_vals['line_ids'].append((0, 0, counterpart_aml_dict))

            # WITHHOLDING ADDITION START
            if rec.payment_method_type == 'adjustment' \
                    and rec.payment_difference_handling == 'reconcile' \
                    or self._context.get('wht_from_invoice', False):
                if rec.payment_type != 'transfer':
                    wht_amount = rec.wht_amount
                    wht_tax_id = rec.wht_tax_id
                    wht_account_id = rec.wht_account_id

                    # Withholding Tax from Register Payment (List View)
                    if self._context.get('wht_from_invoice', False) \
                            and self._context.get('wht_amount', False) \
                            and self._context.get('wht_tax_id', False) \
                            and self._context.get('wht_account_id', False):
                        rec.wht_amount = wht_amount = self._context.get('wht_amount')
                        wht_tax_id = AccountTax.browse(self._context.get('wht_tax_id'))
                        wht_account_id = self.env['account.account'].browse(self._context.get('wht_account_id'))
                        rec.wht_tax_id = self._context.get('wht_tax_id')
                        rec.wht_account_id = self._context.get('wht_account_id')

                    if not rec.multiple_wth_tax:
                        # If from Payment Form (Not from Register Payment Wizard)
                        if not self._context.get('wht_from_invoice', False):
                            if rec.amount <= total_inv_amount:
                                wht_amount = rec.wht_amount
                            else:
                                wht_amount = -rec.wht_amount

                        if wht_tax_id and wht_amount:
                            debit_wht = credit_wht = 0
                            amount_currency_wht, currency_id = AccountMoveLine.with_context(
                                date=rec.payment_date)._compute_amount_fields(wht_amount, rec.currency_id,
                                                                              rec.company_id.currency_id)[2:]
                            debit_wht, credit_wht, amount_currency, currency_id = AccountMoveLine.with_context(
                                date=rec.payment_date)._compute_amount_fields(wht_amount, rec.currency_id,
                                                                              rec.company_id.currency_id)
                            if rec.payment_type == 'inbound':
                                wht_line = rec._get_shared_move_line_vals(
                                    debit_wht,
                                    credit_wht,
                                    amount_currency_wht
                                )
                            elif rec.payment_type == 'outbound':
                                wht_line = rec._get_shared_move_line_vals(
                                    credit_wht,
                                    debit_wht,
                                    amount_currency_wht
                                )

                            wht_line.update({
                                'account_id': wht_account_id.id,
                                'name': wht_tax_id.description,
                                'tax_repartition_line_id': wht_tax_id.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax').id,
                            })
                            print("withholding_line: ", wht_line)
                            move_vals['line_ids'].append((0, 0, wht_line))
                    else:
                        # Multiple Withholding
                        for wth_id in rec.payment_withholding_ids:
                            # If from Payment Form (Not from Register Payment Wizard)
                            if not self._context.get('wht_from_invoice', False):
                                if rec.amount <= total_inv_amount:
                                    wht_amount = wth_id.wht_amount
                                else:
                                    wht_amount = -wth_id.wht_amount
                            wht_tax_id = wth_id.wht_tax_id
                            if wht_tax_id and wht_amount:
                                analytic_account_id = wth_id.wht_analytic_accnt_id \
                                                      and wth_id.wht_analytic_accnt_id.id \
                                                      or False
                                debit_wht = credit_wht = 0
                                amount_currency_wht, currency_id = AccountMoveLine.with_context(
                                    date=rec.payment_date)._compute_amount_fields(wht_amount, rec.currency_id,
                                                                                  rec.company_id.currency_id)[2:]
                                debit_wht, credit_wht, amount_currency, currency_id = AccountMoveLine.with_context(
                                    date=rec.payment_date)._compute_amount_fields(wht_amount, rec.currency_id,
                                                                                  rec.company_id.currency_id)
                                if rec.payment_type == 'inbound':
                                    wht_line = rec._get_shared_move_line_vals(
                                        debit_wht,
                                        credit_wht,
                                        amount_currency_wht
                                    )
                                elif rec.payment_type == 'outbound':
                                    wht_line = rec._get_shared_move_line_vals(
                                        credit_wht,
                                        debit_wht,
                                        amount_currency_wht
                                    )

                                wht_line.update({
                                    'account_id': wth_id.wht_account_id.id,
                                    'name': wht_tax_id.description,
                                    'analytic_account_id': analytic_account_id,
                                    'tax_repartition_line_id': wht_tax_id.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax').id,
                                })
                                print("withholding_line: ", wht_line)
                                move_vals['line_ids'].append((0, 0, wht_line))
                    # WITHHOLDING ADDITION END

                # PAYMENT CHARGES START
                if rec.payment_charge_line_ids:
                    # Payment Difference should be 0
                    if rec.payment_difference != 0.0:
                        raise ValidationError(_('Payment Difference should be equal to zero.'))

                    for charge_id in rec.payment_charge_line_ids:
                        charge_amount = tax_amount = debit_charge = credit_charge = debit_tax = credit_tax = 0
                        charge_amount = charge_id.amount_untaxed
                        tax_id = charge_id.tax_id
                        if rec.payment_type == 'inbound':
                            if rec.amount <= total_inv_amount:
                                charge_amount = charge_id.amount_untaxed
                                tax_amount = charge_id.amount_tax
                            else:
                                charge_amount = -charge_id.amount_untaxed
                                tax_amount = -charge_id.amount_tax
                        else:
                            if rec.amount >= total_inv_amount:
                                charge_amount = charge_id.amount_untaxed
                                tax_amount = charge_id.amount_tax
                            else:
                                charge_amount = -charge_id.amount_untaxed
                                tax_amount = -charge_id.amount_tax

                        amount_currency_charge, currency_id = AccountMoveLine.with_context(
                            date=rec.payment_date)._compute_amount_fields(charge_amount, rec.currency_id,
                                                                          rec.company_id.currency_id)[2:]
                        debit_charge, credit_charge, amount_currency, currency_id = AccountMoveLine.with_context(
                            date=rec.payment_date)._compute_amount_fields(charge_amount, rec.currency_id,
                                                                          rec.company_id.currency_id)

                        # Taxes
                        if tax_id:
                            amount_currency_charge, currency_id = AccountMoveLine.with_context(
                                date=rec.payment_date)._compute_amount_fields(charge_amount, rec.currency_id,
                                                                              rec.company_id.currency_id)[2:]
                            amount_currency_tax, currency_id = AccountMoveLine.with_context(
                                date=rec.payment_date)._compute_amount_fields(tax_amount, rec.currency_id,
                                                                              rec.company_id.currency_id)[2:]
                            debit_tax, credit_tax, amount_currency, currency_id = AccountMoveLine.with_context(
                                date=rec.payment_date)._compute_amount_fields(tax_amount, rec.currency_id,
                                                                              rec.company_id.currency_id)

                        charge_line = rec._get_shared_move_line_vals(
                            debit_charge,
                            credit_charge,
                            amount_currency_charge
                        )

                        # Journal Item for Charges
                        charge_line.update({
                            'account_id': charge_id.account_id.id,
                            'analytic_account_id': charge_id.analytic_accnt_id.id,
                            'name': charge_id.label,
                        })

                        if tax_id:
                            tax_line = rec._get_shared_move_line_vals(
                                debit_tax,
                                credit_tax,
                                amount_currency_tax
                            )

                            charge_line.update({
                                'tax_line_id': tax_id.id,
                                'tax_ids': [(6, 0, [tax_id.id])]
                            })

                            # Journal Item for Taxes
                            tax_line.update({
                                'account_id': tax_id.account_id.id,
                                'name': tax_id.name
                            })
                            move_vals['line_ids'].append((0, 0, tax_line))
                        move_vals['line_ids'].append((0, 0, charge_line))
                    # PAYMENT CHARGES END

            else:
                rec.wh_amount = 0.0
                rec.wh_tax_id = False
                rec.payment_charge_line_ids.unlink()

            # Reconcile with the invoices
            if not rec.payment_method_type == 'adjustment' \
                    and rec.payment_difference_handling == 'reconcile' \
                    and rec.payment_difference:

                writeoff_line = rec._get_shared_move_line_vals(0, 0, 0)
                if rec.payment_type == 'outbound':
                    debit_wo, credit_wo, amount_currency_wo, currency_id = AccountMoveLine.with_context(
                        date=rec.payment_date)._compute_amount_fields(rec.payment_difference, rec.currency_id,
                                                                      rec.company_id.currency_id)
                else:
                    credit_wo, debit_wo, amount_currency_wo, currency_id = AccountMoveLine.with_context(
                        date=rec.payment_date)._compute_amount_fields(rec.payment_difference, rec.currency_id,
                                                                      rec.company_id.currency_id)

                writeoff_line['name'] = rec.writeoff_label
                writeoff_line['account_id'] = rec.writeoff_account_id.id
                writeoff_line['debit'] = debit_wo
                writeoff_line['credit'] = credit_wo
                writeoff_line['amount_currency'] = amount_currency_wo
                writeoff_line['currency_id'] = currency_id
                writeoff_line['move_id'] = rec.invoice_ids.id
                counterpart_aml['amount_currency'] = amount_currency_wo
                move_vals['line_ids'].append((0, 0, writeoff_line))
                print("writeoff_line: ", writeoff_line)

            # Write counterpart lines (Invoice Line)
            if not rec.currency_id.is_zero(rec.amount):
                if not rec.currency_id != rec.company_id.currency_id:
                    amount_currency = 0

                payment_amount = rec.amount
                if rec.payment_type == 'outbound':
                    debit = 0
                    credit = payment_amount
                else:
                    debit = payment_amount
                    credit = 0

                if not rec.payment_crdr_inv_line_ids.filtered(lambda l: l.allocation > 0.0):
                    liquidity_aml_dict = rec._get_shared_move_line_vals(
                        debit,
                        credit,
                        -amount_currency
                    )

                else:
                    # If the payment has credit notes
                    liquidity_aml_dict = rec.with_context(credit_aml=True)._get_shared_move_line_vals(
                        debit,
                        credit,
                        -amount_currency
                    )


                liquidity_aml_dict.update(rec._get_liquidity_move_line_vals(-amount))
                print("payment_line_dict: ", liquidity_aml_dict)
                move_vals['line_ids'].append((0, 0, liquidity_aml_dict))

            all_move_vals.append(move_vals)
            #
            # # reconcile the invoice receivable/payable line(s) with the payment
            # if rec.invoice_ids:
            #     # Add Credit Notes
            #     rec.invoice_ids += rec.payment_crdr_inv_line_ids.mapped('invoice_id')
            #     rec.invoice_ids.register_payment(counterpart_aml)
        print(all_move_vals)
        # raise ValidationError("Bamboo")
        return all_move_vals

    def post(self):
        """ Create the journal items for the payment and update the payment's state to 'posted'.
            A journal entry is created containing an item in the source liquidity account (selected journal's default_debit or default_credit)
            and another in the destination reconcilable account (see _compute_destination_account_id).
            If invoice_ids is not empty, there will be one reconcilable move line per invoice to reconcile with.
            If the payment is a transfer, a second journal entry is created in the destination journal to receive money from the transfer account.
        """
        AccountMove = self.env['account.move'].with_context(default_type='entry')
        for rec in self:
            if rec.state not in ['draft', 'pdc']:
                raise UserError(_("Only a draft payment can be posted."))

            if any(inv.state != 'posted' for inv in rec.invoice_ids):
                raise ValidationError(_("The payment cannot be processed because the invoice is not open!"))

            # keep the name in case of a payment reset to draft
            if not rec.name:
                # Use the right sequence to set the name
                if rec.payment_type == 'transfer':
                    sequence_code = 'account.payment.transfer'
                else:
                    if rec.partner_type == 'customer':
                        if rec.payment_type == 'inbound':
                            sequence_code = 'account.payment.customer.invoice'
                        if rec.payment_type == 'outbound':
                            sequence_code = 'account.payment.customer.refund'
                    if rec.partner_type == 'supplier':
                        if rec.payment_type == 'inbound':
                            sequence_code = 'account.payment.supplier.refund'
                        if rec.payment_type == 'outbound':
                            sequence_code = 'account.payment.supplier.invoice'
                rec.name = self.env['ir.sequence'].next_by_code(sequence_code, sequence_date=rec.payment_date)
                if not rec.name and rec.payment_type != 'transfer':
                    raise UserError(_("You have to define a sequence for %s in your company.") % (sequence_code,))

            # moves = AccountMove.create(rec._prepare_payment_moves())
            amount = rec.amount * (rec.payment_type in ('outbound', 'transfer') and 1 or -1)
            # print("Attempt")
            if rec.payment_type != 'transfer':
                moves = AccountMove.create(rec._create_payment_entry(amount))
            else:
                moves = AccountMove.create(rec._prepare_payment_moves())
            # print("Attempt Success")
            moves.filtered(lambda move: move.journal_id.post_at != 'bank_rec').post()
            # Update the state / move before performing any reconciliation.
            move_name = self._get_move_name_transfer_separator().join(moves.mapped('name'))
            rec.write({'state': 'posted', 'move_name': move_name})
            if rec.payment_type in ('inbound', 'outbound'):
                # ==== 'inbound' / 'outbound' ====
                if rec.invoice_ids:
                    (moves[0] + rec.invoice_ids + rec.payment_crdr_inv_line_ids.filtered(lambda l: l.allocation > 0.0).mapped('invoice_id')).line_ids \
                        .filtered(lambda line: not line.reconciled and line.account_id == rec.destination_account_id) \
                        .reconcile()
            elif rec.payment_type == 'transfer':
                # ==== 'transfer' ====
                (moves + rec.payment_crdr_inv_line_ids.filtered(lambda l: l.allocation > 0.0).mapped('invoice_id')).line_ids \
                    .filtered(lambda line: line.account_id == rec.company_id.transfer_account_id) \
                    .reconcile()

        return True

    def _create_payment_entry_legacy(self, amount):
        """ Create a journal entry corresponding to a payment, if the payment references invoice(s) they are reconciled.
            Return the journal entry.
        """
        AccountMoveLine = self.env['account.move.line'].with_context(check_move_validity=False)
        AccountTax = self.env['account.tax']
        with_wht = False
        amount_orig = amount

        # Register Payment Wizard
        if self._context.get('wht_from_invoice', False) \
                and self._context.get('wht_amount', False) \
                and self._context.get('wht_tax_id', False) \
                and self._context.get('wht_account_id', False):
            # Add withholding amount
            amount = amount - self._context.get('wht_amount')
            with_wht = True

        debit, credit, amount_currency, currency_id = AccountMoveLine.with_context(
            date=self.payment_date)._compute_amount_fields(amount, self.currency_id, self.company_id.currency_id)

        move = self.env['account.move'].create(self._get_move_vals())
        wht_tax_id = False
        invoice_id = False
        memo = False
        counterpart_aml = {}
        line_invoice_ids = self.env['account.move']
        total_inv_amount = 0.0
        debit_chn = debit
        credit_chn = credit

        for rec in self:
            # Register Payment Wizard (Assign PDC then Confirmed)
            if rec.wht_tax_id and rec.wht_amount and not rec.payment_inv_line_ids and not with_wht:
                # Add withholding amount
                amount = amount_orig - rec.wht_amount
                debit, credit, amount_currency, currency_id = AccountMoveLine.with_context(
                    date=self.payment_date)._compute_amount_fields(amount, self.currency_id,
                                                                   self.company_id.currency_id)
                with_wht = True

            for line_id in rec.payment_inv_line_ids.filtered(lambda l: l.allocation > 0.0):
                line_invoice_ids += line_id.invoice_id
                total_inv_amount += line_id.allocation

                if rec.check_no:
                    rec.communication = rec.check_no
                if not memo and not rec.communication:
                    rec.communication = line_id.invoice_id.name
                    if line_id.reference: rec.communication = rec.communication + '/' + line_id.reference
                else:
                    if line_id.reference:
                        rec.communication = rec.communication + ', ' + line_id.invoice_id.name + '/' + line_id.reference
                    else:
                        rec.communication = rec.communication + ', ' + line_id.invoice_id.name
                line_id.balance_amount = line_id.invoice_id.amount_residual

            # Credit Notes
            for line_id in rec.payment_crdr_inv_line_ids.filtered(lambda l: l.allocation > 0.0):
                line_invoice_ids += line_id.invoice_id
                total_inv_amount += line_id.allocation
                if rec.check_no:
                    rec.communication = rec.check_no
                if not memo and not rec.communication:
                    rec.communication = line_id.invoice_id.name
                    if line_id.reference: rec.communication = rec.communication + '/' + line_id.reference
                else:
                    if line_id.reference:
                        rec.communication = rec.communication + ', ' + line_id.invoice_id.name + '/' + line_id.reference
                    else:
                        rec.communication = rec.communication + ', ' + line_id.invoice_id.name
                line_id.balance_amount = line_id.invoice_id.amount_residual

            # Write line corresponding to invoice payment
            # PAYMENT ADJUSTMENT
            if rec.payment_method_type == 'adjustment':
                # Full Reconcile
                if rec.payment_difference_handling == 'reconcile' and rec.payment_difference:
                    rec.invoice_ids = line_invoice_ids
                    counterpart_aml_dict = rec._get_shared_move_line_vals(debit, credit, amount_currency, move.id)
                    counterpart_aml_dict.update(rec._get_counterpart_move_line_vals(rec.invoice_ids))
                    counterpart_aml_dict.update({'currency_id': currency_id})
                    counterpart_aml = AccountMoveLine.create(counterpart_aml_dict)
                else:
                    # Amount is greater than the total allocated amount (Amount will change to Total Allocation)
                    if rec.payment_difference_handling == 'reconcile' and rec.amount > total_inv_amount:
                        rec.invoice_ids = line_invoice_ids
                        if debit != 0.0:
                            debit_chn = total_inv_amount
                        else:
                            credit_chn = total_inv_amount
                        counterpart_aml_dict = rec._get_shared_move_line_vals(debit_chn, credit_chn, amount_currency,
                                                                              move.id)
                        counterpart_aml_dict.update(rec._get_counterpart_move_line_vals(rec.invoice_ids))
                        counterpart_aml_dict.update({'currency_id': currency_id})
                        counterpart_aml = AccountMoveLine.create(counterpart_aml_dict)
                    else:
                        # Payment Invoice Lines
                        debit_adj = credit_adj = 0.0
                        for payment_id in rec.payment_inv_line_ids.filtered(lambda l: l.allocation > 0.0):
                            if rec.payment_difference_handling == 'reconcile':
                                if not payment_id.full_reconcile and payment_id.allocation == payment_id.balance_amount:
                                    raise ValidationError(_('Mark the payment allocation lines as Full Reconcile.'))

                            invoice_id = payment_id.invoice_id

                            if invoice_id.type in ['out_invoice', 'out_receipt']:
                                credit_adj = payment_id.allocation
                            else:
                                credit_adj = 0.0
                            if invoice_id.type in ['in_invoice', 'in_receipt']:
                                debit_adj = payment_id.allocation
                            else:
                                debit_adj = 0.0

                            counterpart_aml_dict = rec._get_shared_move_line_vals(debit_adj, credit_adj,
                                                                                  amount_currency, move.id)
                            counterpart_aml_dict.update(rec._get_counterpart_move_line_vals(payment_id.invoice_id))
                            counterpart_aml_dict.update({'currency_id': currency_id})
                            counterpart_aml = AccountMoveLine.create(counterpart_aml_dict)
                            payment_id.invoice_id.with_context(adjust_payment=True, invoice_id=payment_id.invoice_id.id,
                                                               amount=credit_adj).assign_outstanding_credit(
                                counterpart_aml.id)

                        # Credit Notes
                        debit_adj = credit_adj = 0.0
                        for payment_id in rec.payment_crdr_inv_line_ids.filtered(lambda l: l.allocation > 0.0):
                            if rec.payment_difference_handling == 'reconcile':
                                if not payment_id.full_reconcile and payment_id.allocation == payment_id.balance_amount:
                                    raise ValidationError(_('Mark the payment allocation lines as Full Reconcile.'))

                            invoice_id = payment_id.invoice_id

                            if invoice_id.type == 'out_refund':
                                debit_adj = payment_id.allocation
                            else:
                                debit_adj = 0.0
                            if invoice_id.type == 'in_refund':
                                credit_adj = payment_id.allocation
                            else:
                                credit_adj = 0.0

                            counterpart_aml_dict = rec.with_context(credit_aml=True)._get_shared_move_line_vals(
                                debit_adj, credit_adj, amount_currency, move.id)
                            counterpart_aml_dict.update(rec._get_counterpart_move_line_vals(invoice_id))
                            counterpart_aml_dict.update({'currency_id': currency_id})
                            counterpart_aml = AccountMoveLine.create(counterpart_aml_dict)
                            counterpart_aml.invoice_id.with_context(adjust_payment=True,
                                                                    invoice_id=counterpart_aml.invoice_id.id,
                                                                    amount=credit_adj).assign_outstanding_credit(
                                counterpart_aml.id)
            else:
                if self._context.get('invoice_id', False):
                    invoice_id = self._context.get('invoice_id')

                counterpart_aml_dict = self._get_shared_move_line_vals(debit, credit, amount_currency, move.id)
                counterpart_aml_dict.update(self._get_counterpart_move_line_vals(self.invoice_ids))
                counterpart_aml_dict.update({'currency_id': currency_id})
                counterpart_aml = AccountMoveLine.create(counterpart_aml_dict)

            # WITHHOLDING ADDITION START
            if rec.payment_method_type == 'adjustment' \
                    and rec.payment_difference_handling == 'reconcile' \
                    or self._context.get('wht_from_invoice', False):
                if rec.payment_type not in ['transfer', 'outbound']:
                    wht_amount = self.wht_amount
                    wht_tax_id = self.wht_tax_id
                    wht_account_id = self.wht_account_id

                    # Withholding Tax from Register Payment (List View)
                    if self._context.get('wht_from_invoice', False) \
                            and self._context.get('wht_amount', False) \
                            and self._context.get('wht_tax_id', False) \
                            and self._context.get('wht_account_id', False):
                        rec.wht_amount = wht_amount = self._context.get('wht_amount')
                        wht_tax_id = AccountTax.browse(self._context.get('wht_tax_id'))
                        wht_account_id = self.env['account.account'].browse(self._context.get('wht_account_id'))
                        rec.wht_tax_id = self._context.get('wht_tax_id')
                        rec.wht_account_id = self._context.get('wht_account_id')

                    if not rec.multiple_wth_tax:
                        # If from Payment Form (Not from Register Payment Wizard)
                        if not self._context.get('wht_from_invoice', False):
                            if rec.amount <= total_inv_amount:
                                wht_amount = rec.wht_amount
                            else:
                                wht_amount = -rec.wht_amount

                        if wht_tax_id and wht_amount:
                            debit_wht = credit_wht = 0
                            amount_currency_wht, currency_id = AccountMoveLine.with_context(
                                date=rec.payment_date)._compute_amount_fields(wht_amount, rec.currency_id,
                                                                              rec.company_id.currency_id)[2:]
                            debit_wht, credit_wht, amount_currency, currency_id = AccountMoveLine.with_context(
                                date=rec.payment_date)._compute_amount_fields(wht_amount, rec.currency_id,
                                                                              rec.company_id.currency_id)

                            wht_line = rec._get_shared_move_line_vals(debit_wht, credit_wht, amount_currency_wht,
                                                                      move.id)
                            wht_line.update({'account_id': wht_account_id.id,
                                             'name': wht_tax_id.description,
                                             'tax_line_id': wht_tax_id.id})

                            AccountMoveLine.create(wht_line)
                    else:
                        # Multiple Withholding
                        for wth_id in rec.payment_withholding_ids:
                            # If from Payment Form (Not from Register Payment Wizard)
                            if not self._context.get('wht_from_invoice', False):
                                if rec.amount <= total_inv_amount:
                                    wht_amount = wth_id.wht_amount
                                else:
                                    wht_amount = -wth_id.wht_amount
                            wht_tax_id = wth_id.wht_tax_id
                            if wht_tax_id and wht_amount:
                                analytic_account_id = wth_id.wht_analytic_accnt_id \
                                                      and wth_id.wht_analytic_accnt_id.id \
                                                      or False
                                debit_wht = credit_wht = 0
                                amount_currency_wht, currency_id = AccountMoveLine.with_context(
                                    date=rec.payment_date)._compute_amount_fields(wht_amount, rec.currency_id,
                                                                                  rec.company_id.currency_id)[2:]
                                debit_wht, credit_wht, amount_currency, currency_id = AccountMoveLine.with_context(
                                    date=rec.payment_date)._compute_amount_fields(wht_amount, rec.currency_id,
                                                                                  rec.company_id.currency_id)

                                wht_line = rec._get_shared_move_line_vals(debit_wht, credit_wht, amount_currency_wht,
                                                                          move.id)
                                wht_line.update({'account_id': wth_id.wht_account_id.id,
                                                 'name': wht_tax_id.description,
                                                 'analytic_account_id': analytic_account_id,
                                                 'tax_line_id': wht_tax_id.id})

                                AccountMoveLine.create(wht_line)

                    # WITHHOLDING ADDITION END

                # PAYMENT CHARGES START
                if rec.payment_charge_line_ids:
                    # Payment Difference should be 0
                    if rec.payment_difference != 0.0:
                        raise ValidationError(_('Payment Difference should be equal to zero.'))

                    for charge_id in self.payment_charge_line_ids:
                        charge_amount = tax_amount = debit_charge = credit_charge = debit_tax = credit_tax = 0
                        charge_amount = charge_id.amount_untaxed
                        tax_id = charge_id.tax_id
                        if rec.payment_type == 'inbound':
                            if rec.amount <= total_inv_amount:
                                charge_amount = charge_id.amount_untaxed
                                tax_amount = charge_id.amount_tax
                            else:
                                charge_amount = -charge_id.amount_untaxed
                                tax_amount = -charge_id.amount_tax
                        else:
                            if rec.amount >= total_inv_amount:
                                charge_amount = charge_id.amount_untaxed
                                tax_amount = charge_id.amount_tax
                            else:
                                charge_amount = -charge_id.amount_untaxed
                                tax_amount = -charge_id.amount_tax

                        amount_currency_charge, currency_id = AccountMoveLine.with_context(
                            date=rec.payment_date)._compute_amount_fields(charge_amount, rec.currency_id,
                                                                          rec.company_id.currency_id)[2:]
                        debit_charge, credit_charge, amount_currency, currency_id = AccountMoveLine.with_context(
                            date=rec.payment_date)._compute_amount_fields(charge_amount, rec.currency_id,
                                                                          rec.company_id.currency_id)

                        # Taxes
                        if tax_id:
                            amount_currency_charge, currency_id = AccountMoveLine.with_context(
                                date=rec.payment_date)._compute_amount_fields(charge_amount, rec.currency_id,
                                                                              rec.company_id.currency_id)[2:]
                            amount_currency_tax, currency_id = AccountMoveLine.with_context(
                                date=rec.payment_date)._compute_amount_fields(tax_amount, rec.currency_id,
                                                                              rec.company_id.currency_id)[2:]
                            debit_tax, credit_tax, amount_currency, currency_id = AccountMoveLine.with_context(
                                date=rec.payment_date)._compute_amount_fields(tax_amount, rec.currency_id,
                                                                              rec.company_id.currency_id)

                        charge_line = rec._get_shared_move_line_vals(debit_charge, credit_charge,
                                                                     amount_currency_charge, move.id)

                        # Journal Item for Charges
                        charge_line.update({'account_id': charge_id.account_id.id,
                                            'analytic_account_id': charge_id.analytic_accnt_id.id,
                                            'name': charge_id.label,
                                            })
                        if tax_id:
                            tax_line = rec._get_shared_move_line_vals(debit_tax, credit_tax, amount_currency_tax,
                                                                      move.id)
                            charge_line.update({'tax_line_id': tax_id.id,
                                                'tax_ids': [(6, 0, [tax_id.id])]})
                            # Journal Item for Taxes
                            tax_line.update({'account_id': tax_id.account_id.id,
                                             'name': tax_id.name})
                            AccountMoveLine.create(tax_line)

                        AccountMoveLine.create(charge_line)
                        tax_id = False
                        tax_line = {}
                    # PAYMENT CHARGES END

            else:
                rec.wh_amount = 0.0
                rec.wh_tax_id = False
                rec.payment_charge_line_ids.unlink()

            # Reconcile with the invoices
            if not rec.payment_method_type == 'adjustment' \
                    and rec.payment_difference_handling == 'reconcile' \
                    and rec.payment_difference:
                writeoff_line = rec._get_shared_move_line_vals(0, 0, 0, move.id)
                debit_wo, credit_wo, amount_currency_wo, currency_id = AccountMoveLine.with_context(
                    date=rec.payment_date)._compute_amount_fields(rec.payment_difference, rec.currency_id,
                                                                  rec.company_id.currency_id)
                writeoff_line['name'] = rec.writeoff_label
                writeoff_line['account_id'] = rec.writeoff_account_id.id
                writeoff_line['debit'] = debit_wo
                writeoff_line['credit'] = credit_wo
                writeoff_line['amount_currency'] = amount_currency_wo
                writeoff_line['currency_id'] = currency_id
                writeoff_line = AccountMoveLine.create(writeoff_line)
                if counterpart_aml['debit'] or (writeoff_line['credit'] and not counterpart_aml['credit']):
                    counterpart_aml['debit'] += credit_wo - debit_wo
                if counterpart_aml['credit'] or (writeoff_line['debit'] and not counterpart_aml['debit']):
                    counterpart_aml['credit'] += debit_wo - credit_wo
                counterpart_aml['amount_currency'] -= amount_currency_wo

            # Write counterpart lines (Payment Line)
            if not rec.currency_id.is_zero(rec.amount):
                if not rec.currency_id != rec.company_id.currency_id:
                    amount_currency = 0

                # Register Payment Wizard (Deduct withholding amount)
                if self._context.get('wht_from_invoice', False):
                    # Deduct withholding amount
                    if wht_tax_id and wht_amount:
                        amount = amount + wht_amount
                        if debit:
                            debit = abs(amount)
                        else:
                            credit = abs(amount)

                if not rec.payment_crdr_inv_line_ids:
                    liquidity_aml_dict = rec._get_shared_move_line_vals(credit, debit, -amount_currency, move.id, False)
                else:
                    # If the payment has credit notes
                    liquidity_aml_dict = rec.with_context(credit_aml=True)._get_shared_move_line_vals(credit, debit,
                                                                                                      -amount_currency,
                                                                                                      move.id)
                liquidity_aml_dict.update(rec._get_liquidity_move_line_vals(-amount))
                AccountMoveLine.create(liquidity_aml_dict)

            # validate the payment
            if not rec.journal_id.post_at_bank_rec:
                move.post()

            # reconcile the invoice receivable/payable line(s) with the payment
            if rec.invoice_ids:
                # Add Credit Notes
                rec.invoice_ids += rec.payment_crdr_inv_line_ids.mapped('invoice_id')
                rec.invoice_ids.register_payment(counterpart_aml)
        return move

    def _create_transfer_entry(self, amount):
        """ Create the journal entry corresponding to the 'incoming money' part of an internal transfer,
        return the reconcilable move line

        #FIX: Default bug: _get_shared_move_line_vals() missing 1 required positional argument: 'invoice_id'
        """
        aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)
        debit, credit, amount_currency, dummy = aml_obj.with_context(date=self.payment_date)._compute_amount_fields(
            amount, self.currency_id, self.company_id.currency_id)
        amount_currency = self.destination_journal_id.currency_id and self.currency_id._convert(
            amount,
            self.destination_journal_id.currency_id,
            self.company_id,
            self.payment_date or fields.Date.today()
        ) or 0

        dst_move = self.env['account.move'].create(self._get_move_vals(self.destination_journal_id))

        dst_liquidity_aml_dict = self._get_shared_move_line_vals(debit, credit, amount_currency, dst_move.id)
        dst_liquidity_aml_dict.update({
            'name': _('Transfer from %s') % self.journal_id.name,
            'account_id': self.destination_journal_id.default_credit_account_id.id,
            'currency_id': self.destination_journal_id.currency_id.id,
            'journal_id': self.destination_journal_id.id})
        aml_obj.create(dst_liquidity_aml_dict)

        transfer_debit_aml_dict = self._get_shared_move_line_vals(credit, debit, 0, dst_move.id)
        transfer_debit_aml_dict.update({
            'name': self.name,
            'account_id': self.company_id.transfer_account_id.id,
            'journal_id': self.destination_journal_id.id})
        if self.currency_id != self.company_id.currency_id:
            transfer_debit_aml_dict.update({
                'currency_id': self.currency_id.id,
                'amount_currency': -self.amount,
            })
        transfer_debit_aml = aml_obj.create(transfer_debit_aml_dict)
        if not self.destination_journal_id.post_at_bank_rec:
            dst_move.post()
        return transfer_debit_aml

    def cancel(self):
        res = super(AccountPayment, self).cancel()
        self._onchange_partner_id()
        return res

    # The following functions are from Odoo 12 'account.abstract.payment'
    @api.depends('invoice_ids', 'wht_amount', 'payment_inv_line_ids.allocation', 'payment_crdr_inv_line_ids.allocation',
                 'payment_charge_line_ids.amount', 'payment_withholding_ids.wht_amount', 'amount', 'payment_date',
                 'currency_id')
    def _compute_payment_difference(self):
        for rec in self:
            payment_difference = wht_amount = 0
            if rec.payment_method_type == 'adjustment':
                total_inv_amount = sum(rec.payment_inv_line_ids.mapped('allocation')) + \
                                   sum(rec.payment_crdr_inv_line_ids.mapped('allocation'))
                payment_amount = rec.amount
                payment_difference = total_inv_amount - payment_amount
                # print("payment_difference: ", payment_difference)

                # DEDUCT CHARGES
                if rec.payment_charge_line_ids:
                    deduction_charges = sum(rec.payment_charge_line_ids.mapped('amount'))
                    if rec.payment_type == 'outbound':
                        deduction_charges *= -1

                    if payment_amount <= total_inv_amount:
                        payment_difference -= deduction_charges
                    else:
                        payment_difference += deduction_charges

                # Compute Withholding amount
                if not rec.multiple_wth_tax:
                    wht_amount = rec.wht_amount
                else:
                    wht_amount = sum(rec.payment_withholding_ids.mapped('wht_amount'))
                # print("wht_amount: ", wht_amount)

            else:
                for pay in rec.filtered(lambda p: p.invoice_ids):
                    payment_amount = - pay.amount
                    computed_payment_amount = pay._compute_payment_amount(
                        rec.invoice_ids,
                        rec.currency_id,
                        rec.journal_id,
                        rec.payment_date,
                    )
                    wht_amount = 0
                    if pay.wht_amount:
                        wht_amount = pay.wht_amount
                    # print("computed_payment_amount: ", computed_payment_amount)
                    # print("payment_amount: ", payment_amount)
                    # print("wht_amount: ", wht_amount)
                    payment_difference = abs(computed_payment_amount) - abs(payment_amount)

            payment_difference -= wht_amount
            rec.payment_difference = payment_difference * -1

    def _compute_payment_amount_adjustment(self, invoices=None, payments=None, crdr_payments=None):
        """ Compute the total amount for the payment adjustment.
        :return: The total amount to pay the invoices.
        """
        # Get the payment invoices
        if not invoices:
            invoices = self.invoice_ids

        # Get the payment currency
        currency = self.currency_id or self.journal_id.currency_id or self.journal_id.company_id.currency_id \
                   or invoices and invoices[0].currency_id
        amount_total = 0.0

        for payment_id in payments:
            invoice_id = payment_id.invoice_id
            sign = invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
            amount_total += MAP_INVOICE_TYPE_PAYMENT_SIGN[invoice_id.type] * abs(payment_id.allocation) * sign

            if self.payment_difference_handling == 'reconcile' and not payment_id.allocation:
                amount_total += MAP_INVOICE_TYPE_PAYMENT_SIGN[invoice_id.type] * invoice_id.amount_residual_signed * sign

        # Credit Notes
        for payment_id in crdr_payments:
            invoice_id = payment_id.invoice_id
            sign = invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
            amount_total -= MAP_INVOICE_TYPE_PAYMENT_SIGN[invoice_id.type] * abs(payment_id.allocation)

            if self.payment_difference_handling == 'reconcile' and not payment_id.allocation:
                amount_total -= MAP_INVOICE_TYPE_PAYMENT_SIGN[invoice_id.type] * invoice_id.amount_residual_signed

        # Avoid currency rounding issues by summing the amounts according to the company_currency_id before
        total = 0.0
        groups = groupby(invoices, lambda i: i.currency_id)
        for payment_currency, payment_invoices in groups:
            if payment_currency == currency:
                total += amount_total
            else:
                total += payment_currency._convert(amount_total, currency, self.env.user.company_id,
                                                   self.payment_date or fields.Date.today())
        return total

    def action_register_payment(self):
        res = super(AccountPayment, self).action_register_payment()

        active_ids = self.env.context.get('active_ids')
        if not active_ids:
            return ''

        res['view_id'] = len(active_ids) != 1 \
                         and self.env.ref('account.view_account_payment_form_multi').id \
                         or self.env.ref('tf_ph_payment.view_account_payment_invoice_form_withholding').id

        return res

    # Service VAT Module Fields and Functions

    service_invoice_line_ids = fields.Many2many('account.move.line',
                                                'payment_service_line_rel', 'payment_id', 'line_id',
                                                string="Service Invoice Lines")
    vat_move_ids = fields.One2many('account.move', 'vat_payment_id', "Service Vat Reclass Entries")
    vat_move_count = fields.Integer("Service Vat Reclass Entries", compute='get_vat_move_count', store=True)
    vendor_valid_for_reclass = fields.Boolean()

    def action_vendor_svc_vat(self):
        self.ensure_one()
        return {
            'name': 'Create Service VAT Reclass Entry',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'tf.vendor.service.vat.generate',
            'view_id': self.env.ref('tf_ph_payment.tf_vendor_service_vat_generate_form').id,
            'context': {'default_payment_id': self.id},
            'type': 'ir.actions.act_window',
            'target': 'new'
        }

    def is_vendor_valid_for_reclass(self):
        for rec in self:
            valid_for_reclass = False
            if rec.state not in ['draft', 'pdf'] and rec.payment_type == 'outbound' and not rec.vat_move_ids:
                if rec.payment_method_type == 'adjustment':
                    allocated_inv_ids = rec.payment_inv_line_ids.filtered_domain([('allocation', '>', 0.0)])
                    svc_vat_tax_ids = allocated_inv_ids.mapped('invoice_id').mapped('invoice_line_ids').mapped(
                        'tax_ids').filtered_domain([('is_service', '=', True)])
                    if svc_vat_tax_ids:
                        valid_for_reclass = True
                else:
                    allocated_inv_ids = rec.invoice_ids
                    svc_vat_tax_ids = allocated_inv_ids.mapped('invoice_line_ids').mapped(
                        'tax_ids').filtered_domain([('is_service', '=', True)])
                    if svc_vat_tax_ids:
                        valid_for_reclass = True
            rec.vendor_valid_for_reclass = valid_for_reclass

    @api.depends('vat_move_ids')
    def get_vat_move_count(self):
        for rec in self:
            rec.vat_move_count = len(rec.vat_move_ids)

    def create_reclass_entry(self, invoice_ids, other_amounts):
        move_obj = self.env['account.move']
        move_line_obj = self.env['account.move.line']

        if not invoice_ids:
            invoice_ids = self.invoice_ids

        for invoice_id in invoice_ids.filtered(lambda x: x.payment_move_line_ids & self.mapped('move_line_ids')):
            # Get service taxes from invoice lines
            tax_ids = invoice_id.invoice_line_ids.mapped('tax_ids').filtered(lambda t: t.is_service)

            # Get the invoice's move lines
            move_lines = invoice_id.mapped('line_ids')
            sign = 1 if invoice_id.type in ['in_invoice', 'in_receipt', 'out_refund'] else -1
            invoice_total = invoice_id.amount_total

            if self.wht_tax_id:
                if self.payment_difference_handling == 'reconcile':
                    if len(invoice_id.payment_ids) > 1:
                        payments = sum(invoice_id.payment_ids[-1].mapped('amount'))
                        if payments:
                            payment_amount = invoice_total - payments
                    else:
                        payment_amount = invoice_total
                else:
                    payment_amount = sum(self.mapped('amount')) + sum(self.mapped('wht_amount'))
            else:
                if self.payment_method_type == 'adjustment':
                    if self.payment_inv_line_ids:
                        payment_amount = sum(self.payment_inv_line_ids.mapped('allocation'))
                    if self.payment_crdr_inv_line_ids:
                        payment_amount = -sum(self.payment_crdr_inv_line_ids.mapped('allocation'))
                else:
                    if self.payment_difference_handling:
                        if self.payment_difference_handling == 'reconcile':
                            if len(invoice_id.payment_ids) > 1:
                                payments = sum(invoice_id.payment_ids[-1].mapped('amount'))
                                if payments:
                                    payment_amount = invoice_total - payments
                            else:
                                payment_amount = invoice_total
                        elif sum(self.mapped('amount')) == invoice_total:
                            payment_amount = invoice_total
                        else:
                            payment_amount = sum(self.mapped('amount'))

            for tax_id in tax_ids:
                if tax_id.amount_type == 'percent':
                    for move_line in move_lines.filtered(lambda m: m.name == tax_id.name):
                        move_id = move_line.move_id
                        if self.id not in move_id.vat_payment_ref_ids.ids:
                            debit = credit = 0.0

                            total_line_amount = sum(invoice_id.invoice_line_ids
                                                    .filtered(lambda il: tax_id.id in il.tax_ids.ids)
                                                    .mapped('price_subtotal'))

                            if other_amounts != 0.0:
                                payment_amount += other_amounts * sign

                            if payment_amount > invoice_total:
                                payment_amount /= (payment_amount / invoice_total)

                            payment_ratio = (payment_amount / invoice_total)

                            amount = payment_ratio * tax_id.amount

                            # If Customer Invoice
                            if invoice_id.type in ('out_invoice', 'out_receipt', 'in_refund'):
                                credit = abs(total_line_amount * (amount / 100))
                            # If Customer Refund
                            elif invoice_id.type in ('in_invoice', 'in_receipt', 'out_refund'):
                                debit = abs(total_line_amount * (amount / 100))

                            # Add to Invoice Moves the Payment Reference
                            move_id.write({'vat_payment_ref_ids': [(4, self.ids[0], None)]})

                            # Create Journal Items
                            base_vals = {
                                'journal_id': move_line.journal_id.id,
                                'name': move_line.name,
                                'account_id': tax_id.account_vat_service_id.id,
                                'partner_id': move_line.partner_id.id,
                                'currency_id': move_line.currency_id.id,
                                'amount_currency': move_line.amount_currency,
                                'quantity': move_line.quantity,
                                'move_id': invoice_id.id,
                                'credit': credit,
                                'debit': debit,
                                'analytic_account_id': move_line.analytic_account_id.id or False,
                                'tax_ids': move_line.tax_ids.ids or False,
                            }

                            counterpart_base_vals = base_vals.copy()
                            counterpart_base_vals.update({
                                'credit': debit,
                                'debit': credit,
                                'account_id': move_line.account_id.id
                            })

                            # rce_seq = move_obj.search_count([('vat_invoice_rel_id', '=', invoice_id.id)]) + 1
                            rce_seq = move_obj.search_count([('name', 'ilike', "%s/RCE/" % move_id.name)]) + 1

                            # Create Journal Entry
                            new_move_id = move_obj.create({
                                'name': "%s/RCE/%s/%s" % (move_id.name, tax_id.name, rce_seq),
                                # 'name': move_id.name + "/RCE/" + tax_id.name,
                                'journal_id': move_id.journal_id.id,
                                'narration': move_id.narration,
                                'svc_vat_id': tax_id.id,
                                'date': self.payment_date,
                                'ref': move_id.ref,
                                'vat_invoice_rel_id': invoice_id.id,
                                'vat_payment_ref_ids': [(4, self.ids[0], None)],
                                'vat_payment_id': self.id,
                                'line_ids': [(0, 0, base_vals), (0, 0, counterpart_base_vals)]
                            })

                            new_move_id.line_ids.write({'payment_id': self.id})

                            # Post Re-Classed Journal Entry
                            new_move_id.with_context({'no_create': True}).post()

            # Post Payment Journal Entry
            if invoice_id and invoice_id.state == 'draft':
                invoice_id.with_context({'no_create': True}).post()

        return True

    def get_vat_reconciles(self, move_to_reverse_vat):
        """ Returns the voucher's matching invoice, if applicable. """
        self.ensure_one()
        reconciles = []
        for move in move_to_reverse_vat.line_ids:
            reconcile = move.full_reconcile_id
            if reconcile:
                if reconcile.id not in reconciles:
                    reconciles.append(reconcile.id)
        return reconciles

    # Cancel Payment
    cancel_reason = fields.Text('Reason', copy=False, track_visibility='onchange')


class AccountPaymentInvoiceLine(models.Model):
    _name = 'account.payment.invoice.line'
    _description = 'Payment Invoice Line'


    def _get_invoice_ids(self):
        if self._context.get('partner_id', False) and self._context.get('payment_type', False):
            AccountInvoice = self.env['account.move']
            partner_id = self._context['partner_id']
            payment_type = self._context['payment_type']
            inv_type = []

            if payment_type == 'inbound':
                inv_type = ['out_invoice', 'out_receipt']
            elif payment_type == 'outbound':
                inv_type = ['in_invoice', 'in_receipt']

            invoice_ids = AccountInvoice.search([
                ('partner_id', '=', partner_id),
                ('state', '=', 'posted'),
                ('type', 'in', inv_type),
                ('invoice_payment_state', '=', 'not_paid')
            ])

            if invoice_ids:
                return [(6, 0, invoice_ids.ids)]

    def _get_ref(self):
        for rec in self:
            rec.reference = False
            inv_id = rec.invoice_id
            if rec.payment_id.partner_type == 'customer':
                rec.reference = inv_id.invoice_payment_ref
            elif rec.payment_id.partner_type == 'supplier':
                rec.reference = inv_id.invoice_payment_ref

    @api.depends('invoice_id')
    def _compute_account_id(self):
        """ Get the account_id since it was removed in Odoo 13.
        """
        for record in self:
            if record.invoice_id:
                invoice = record.invoice_id

                if invoice.partner_id:
                    if invoice.is_sale_document(include_receipts=True):
                        account = invoice.partner_id.commercial_partner_id.property_account_receivable_id
                    elif invoice.is_purchase_document(include_receipts=True):
                        account = invoice.partner_id.commercial_partner_id.property_account_payable_id
                    else:
                        account = None
                else:
                    if invoice.is_sale_document(include_receipts=True):
                        account = self.journal_id.default_credit_account_id
                    elif invoice.is_purchase_document(include_receipts=True):
                        account = self.journal_id.default_debit_account_id
                    else:
                        account = None

                record.account_id = account
            else:
                record.account_id = None

    payment_id = fields.Many2one('account.payment', string='Payment Reference', ondelete='cascade')
    invoice_id = fields.Many2one('account.move', string='Invoice Reference')
    account_id = fields.Many2one('account.account', string='Account', compute="_compute_account_id", store=True)
    invoice_ids_ref = fields.Many2many('account.move', default=_get_invoice_ids)
    invoice_date = fields.Date(related='invoice_id.invoice_date')
    due_date = fields.Date(related='invoice_id.invoice_date_due')
    original_amount = fields.Monetary(related='invoice_id.amount_total', string='Original Amount')
    balance_amount = fields.Monetary('Balance Amount', digits=(16, 2))
    full_reconcile = fields.Boolean('Full Reconcile')
    allocation = fields.Monetary('Allocation', digits=(16, 2))
    reference = fields.Char('Payment Ref', compute='_get_ref')
    currency_id = fields.Many2one('res.currency', related='invoice_id.currency_id', string='Currency')
    company_id = fields.Many2one('res.company', related='payment_id.company_id', string='Company')

    @api.onchange('invoice_id')
    def _onchange_invoice(self):
        if self.invoice_id:
            self.balance_amount = self.invoice_id.amount_residual

    @api.onchange('allocation')
    def _onchange_allocation(self):
        if self.invoice_id:
            if round(self.allocation, 2) > round(self.balance_amount, 2):
                raise ValidationError(_('Allocation Amount cannot exceed the Balance Amount!'))

            elif self.allocation < 0:
                raise ValidationError(_('Allocation Amount should not be less than or equal to zero!'))

    @api.onchange('full_reconcile')
    def check_full_reconcilation(self):
        if self.full_reconcile:
            self.allocation = round(self.balance_amount, 2)
        else:
            self.allocation = 0.00


class AccountPaymentCreditDebitInvoiceLine(models.Model):
    _name = 'account.payment.crdr.invoice.line'
    _description = 'Payment CRDR Invoice Line'

    def _get_invoice_ids(self):
        if self._context.get('partner_id', False) and self._context.get('payment_type', False):
            AccountInvoice = self.env['account.move']
            partner_id = self._context['partner_id']
            payment_type = self._context['payment_type']
            if payment_type == 'inbound':
                inv_type = 'out_refund'
            elif payment_type == 'outbound':
                inv_type = 'in_refund'
            invoice_ids = AccountInvoice.search([
                ('partner_id', '=', partner_id),
                ('state', '=', 'posted'),
                ('type', '=', inv_type),
                ('invoice_payment_state', '=', 'not_paid')
            ])
            if invoice_ids:
                return [(6, 0, invoice_ids.ids)]

    def _get_ref(self):
        for rec in self:
            rec.reference = False
            inv_id = rec.invoice_id
            if rec.payment_id.partner_type == 'customer':
                rec.reference = inv_id.invoice_payment_ref
            elif rec.payment_id.partner_type == 'supplier':
                rec.reference = inv_id.invoice_payment_ref

    @api.depends('invoice_id')
    def _compute_account_id(self):
        """ Get the account_id since it was removed in Odoo 13.
        """
        for record in self:
            if record.invoice_id:
                invoice = record.invoice_id

                if invoice.partner_id:
                    if invoice.is_sale_document(include_receipts=True):
                        account = invoice.partner_id.commercial_partner_id.property_account_receivable_id
                    elif invoice.is_purchase_document(include_receipts=True):
                        account = invoice.partner_id.commercial_partner_id.property_account_payable_id
                    else:
                        account = None
                else:
                    if invoice.is_sale_document(include_receipts=True):
                        account = self.journal_id.default_credit_account_id
                    elif invoice.is_purchase_document(include_receipts=True):
                        account = self.journal_id.default_debit_account_id
                    else:
                        account = None

                record.account_id = account
            else:
                record.account_id = None

    payment_id = fields.Many2one('account.payment', string='Payment Reference', ondelete='cascade')
    invoice_id = fields.Many2one('account.move', string='Invoice Reference')
    account_id = fields.Many2one('account.account', string='Account', compute="_compute_account_id", store=True)
    invoice_ids_ref = fields.Many2many('account.move', default=_get_invoice_ids)
    invoice_date = fields.Date(related='invoice_id.invoice_date')
    due_date = fields.Date(related='invoice_id.invoice_date_due')
    original_amount = fields.Monetary(related='invoice_id.amount_total', string='Original Amount')
    balance_amount = fields.Monetary('Balance Amount')
    full_reconcile = fields.Boolean('Full Reconcile', default=True)
    allocation = fields.Monetary('Allocation')
    reference = fields.Char('Payment Ref', compute='_get_ref')
    currency_id = fields.Many2one('res.currency', related='invoice_id.currency_id', string='Currency')
    company_id = fields.Many2one('res.company', related='payment_id.company_id', string='Company')

    @api.onchange('invoice_id')
    def _onchange_invoice(self):
        if self.invoice_id:
            self.balance_amount = self.invoice_id.amount_residual

    @api.onchange('allocation')
    def _onchange_allocation(self):
        if self.invoice_id:
            if self.allocation > self.balance_amount:
                raise ValidationError(_('Allocation Amount cannot exceed the Balance Amount!'))

            elif self.allocation < 0:
                raise ValidationError(_('Allocation Amount should not be less than or equal to zero!'))

    @api.onchange('full_reconcile')
    def check_full_reconcilation(self):
        if self.full_reconcile:
            self.allocation = self.balance_amount
        else:
            self.allocation = 0.00


class AccountPaymentChargesLine(models.Model):
    _name = 'account.payment.charge.line'
    _description = 'Payment Charges Line'

    @api.depends('tax_id', 'amount')
    def _compute_amount(self):
        for rec in self:
            invoice_id = rec.payment_id.payment_inv_line_ids[0].invoice_id
            currency = invoice_id and invoice_id.currency_id or None
            writeoff_amt = rec.amount
            quantity = 1
            taxes = False
            if rec.tax_id:
                taxes = rec.tax_id.compute_all(writeoff_amt, currency, quantity, product=False,
                                               partner=rec.payment_id.partner_id)['taxes']
                rec.amount_tax = taxes[0]['amount']
                rec.amount_untaxed = writeoff_amt - rec.amount_tax
            else:
                rec.amount_untaxed = writeoff_amt

    payment_id = fields.Many2one('account.payment', string='Payment Reference', ondelete='cascade')
    recon_model_id = fields.Many2one('account.reconcile.model', string='Reconciliation Model')
    account_id = fields.Many2one('account.account', string='Account')
    analytic_accnt_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    journal_id = fields.Many2one('account.journal', related='payment_id.journal_id', string='Journal')
    currency_id = fields.Many2one('res.currency', related='payment_id.currency_id', string='Currency')
    tax_id = fields.Many2one('account.tax', string='Tax')
    label = fields.Char('Journal Item Label', default='Write-Off')
    amount = fields.Monetary('Write-off Amount')
    amount_untaxed = fields.Monetary('Amount (without Taxes)', compute='_compute_amount', store=True)
    amount_tax = fields.Monetary('Tax Amount', compute='_compute_amount', store=True)
    company_id = fields.Many2one('res.company', related='payment_id.company_id', string='Company')

    @api.onchange('recon_model_id')
    def _onchange_recon_model_id(self):
        if self.recon_model_id:
            self.account_id = self.recon_model_id.account_id
            self.tax_id = self.recon_model_id.tax_ids
            self.label = self.recon_model_id.label or self.recon_model_id.name
            self.amount = self.recon_model_id.amount


class PaymentWithholdingLine(models.Model):
    _name = 'account.payment.withholding.line'
    _description = 'Payment Withholding Line'

    @api.constrains('wht_amount')
    def check_constrains(self):
        for rec in self:
            if rec.wht_amount < 0:
                raise ValidationError(_('Withholding amount should not be less than zero.'))

    payment_id = fields.Many2one('account.payment', string='Payment Reference', ondelete='cascade')
    wht_tax_id = fields.Many2one('account.tax', 'Tax Code', copy=False)
    wht_account_id = fields.Many2one(string='Account', related='wht_tax_id.account_id', store=True)
    wht_amount = fields.Monetary('Amount', copy=False)
    wht_analytic_accnt_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    currency_id = fields.Many2one('res.currency', related='payment_id.currency_id', string='Currency', store=True)
    company_id = fields.Many2one('res.company', related='payment_id.company_id', string='Company', store=True)

class AccountBatchPayment(models.Model):
    _inherit = 'account.batch.payment'

    check_no = fields.Char('Check No.', track_visibility='onchange')



# Add back missing functions from Odoo 12
def setup_modifiers(node, field=None, context=None, in_tree_view=False):
    """ Processes node attributes and field descriptors to generate
    the ``modifiers`` node attribute and set it on the provided node.
    Alters its first argument in-place.
    :param node: ``field`` node from an OpenERP view
    :type node: lxml.etree._Element
    :param dict field: field descriptor corresponding to the provided node
    :param dict context: execution context used to evaluate node attributes
    :param bool in_tree_view: triggers the ``column_invisible`` code
                              path (separate from ``invisible``): in
                              tree view there are two levels of
                              invisibility, cell content (a column is
                              present but the cell itself is not
                              displayed) with ``invisible`` and column
                              invisibility (the whole column is
                              hidden) with ``column_invisible``.
    :returns: nothing
    """
    modifiers = {}
    if field is not None:
        transfer_field_to_modifiers(field, modifiers)
    transfer_node_to_modifiers(
        node, modifiers, context=context, in_tree_view=in_tree_view)
    transfer_modifiers_to_node(modifiers, node)
