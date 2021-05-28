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

import time

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TfPurchaseAdvancePaymentBill(models.TransientModel):
    _name = "tf.purchase.advance.payment.bill"
    _description = "Purchase Advance Payment Bill"

    @api.model
    def _count(self):
        return len(self._context.get('active_ids', []))

    @api.model
    def _default_product_id(self):
        product_id = self.env['ir.config_parameter'].sudo().get_param(
            'tf_peec_supplier_advances.purchase_deposit_product_id')
        return self.env['product.product'].browse(int(product_id)).exists()

    @api.model
    def _default_deposit_account_id(self):
        return self._default_product_id().property_account_expense_id

    @api.model
    def _default_deposit_taxes_id(self):
        return self._default_product_id().supplier_taxes_id

    @api.model
    def _default_has_down_payment(self):
        if self._context.get('active_model') == 'purchase.order' and self._context.get('active_id', False):
            purchase_order = self.env['purchase.order'].browse(self._context.get('active_id'))
            return purchase_order.order_line.filtered(
                lambda purchase_order_line: purchase_order_line.is_downpayment
            )

        return False

    @api.model
    def _default_currency_id(self):
        if self._context.get('active_model') == 'purchase.order' and self._context.get('active_id', False):
            purchase_order = self.env['purchase.order'].browse(self._context.get('active_id'))
            return purchase_order.currency_id

    advance_payment_method = fields.Selection([
        ('delivered', 'Regular bill'),
        ('percentage', 'Down payment (percentage)'),
        ('fixed', 'Down payment (fixed amount)')
        ], string='Create Bill', default='delivered', required=True,
        help="A standard bill is issued with all the order lines ready for billing, \
        according to their control policy (based on ordered or received quantity).")
    deduct_down_payments = fields.Boolean('Deduct down payments', default=True)
    has_down_payments = fields.Boolean('Has down payments', default=_default_has_down_payment, readonly=True)
    product_id = fields.Many2one('product.product', string='Down Payment Product', domain=[('type', '=', 'service')],
        default=_default_product_id)
    count = fields.Integer(default=_count, string='Order Count')
    amount = fields.Float('Down Payment Amount', digits='Account',
                          help="The percentage of amount to be invoiced in advance, taxes excluded.")
    currency_id = fields.Many2one('res.currency', string='Currency', default=_default_currency_id)
    fixed_amount = fields.Monetary('Down Payment Amount(Fixed)',
                                   help="The fixed amount to be invoiced in advance, taxes excluded.")
    deposit_account_id = fields.Many2one(
        "account.account", string="Expense Account", domain=[('deprecated', '=', False)],
        help="Account used for deposits", default=_default_deposit_account_id)
    deposit_taxes_id = fields.Many2many("account.tax", string="Vendor Taxes", help="Taxes used for deposits",
                                        default=_default_deposit_taxes_id)

    @api.onchange('advance_payment_method')
    def onchange_advance_payment_method(self):
        if self.advance_payment_method == 'percentage':
            amount = self.default_get(['amount']).get('amount')
            return {'value': {'amount': amount}}
        return {}

    def _prepare_bill_values(self, order, name, amount, po_line):
        bill_vals = {
            # 'ref': order.name,
            'type': 'in_invoice',
            'invoice_origin': order.name,
            'invoice_user_id': order.user_id.id,
            'narration': order.notes,
            'partner_id': order.partner_id.id,
            'fiscal_position_id': order.fiscal_position_id.id or order.partner_id.property_account_position_id.id,
            'currency_id': order.currency_id.id,
            'invoice_payment_ref': order.partner_ref,
            'invoice_payment_term_id': order.payment_term_id.id,
            'invoice_partner_bank_id': order.partner_id.bank_ids[:1].id,
            'invoice_line_ids': [(0, 0, {
                'name': name,
                'price_unit': amount,
                'quantity': 1.0,
                'product_id': self.product_id.id,
                'product_uom_id': po_line.product_uom.id,
                'tax_ids': [(6, 0, po_line.taxes_id.ids)],
                'purchase_line_id': po_line.id,
                'analytic_tag_ids': [(6, 0, po_line.analytic_tag_ids.ids)],
                'analytic_account_id': po_line.account_analytic_id.id or False,
            })],
        }

        return bill_vals

    def _get_advance_details(self, order):
        context = {'lang': order.partner_id.lang}
        if self.advance_payment_method == 'percentage':
            amount = order.amount_untaxed * self.amount / 100
            name = _("Down payment of %s%%") % (self.amount)
        else:
            amount = self.fixed_amount
            name = _('Down Payment')
        del context

        return amount, name

    def _create_bill(self, order, so_line, amount):
        if (self.advance_payment_method == 'percentage' and self.amount <= 0.00) or (
                self.advance_payment_method == 'fixed' and self.fixed_amount <= 0.00):
            raise UserError(_('The value of the down payment amount must be positive.'))

        amount, name = self._get_advance_details(order)

        bill_vals = self._prepare_bill_values(order, name, amount, so_line)

        if order.fiscal_position_id:
            bill_vals['fiscal_position_id'] = order.fiscal_position_id.id
        print("A")
        bill = self.env['account.move'].sudo().create(bill_vals).with_user(self.env.uid)
        print("B")
        bill.message_post_with_view('mail.message_origin_link',
                    values={'self': bill, 'origin': order},
                    subtype_id=self.env.ref('mail.mt_note').id)
        # raise ValueError("Bamboo Bamboo Bamboo")
        return bill

    def _prepare_po_line(self, order, analytic_tag_ids, tax_ids, amount):
        context = {'lang': order.partner_id.lang}
        so_values = {
            'name': _('Down Payment: %s') % (time.strftime('%m %Y'),),
            'price_unit': amount,
            'product_qty': 0.0,
            'order_id': order.id,
            'product_uom': self.product_id.uom_id.id,
            'product_id': self.product_id.id,
            'analytic_tag_ids': analytic_tag_ids,
            'taxes_id': [(6, 0, tax_ids)],
            'is_downpayment': True,
            'date_planned': fields.Date.context_today(self)
            # 'display_type': 'line_section',
        }
        del context
        return so_values

    def create_bills(self):
        purchase_orders = self.env['purchase.order'].browse(self._context.get('active_ids', []))

        if self.advance_payment_method == 'delivered':
            purchase_orders._create_bills(final=self.deduct_down_payments)
        else:
            # Create deposit product if necessary
            if not self.product_id:
                vals = self._prepare_deposit_product()
                self.product_id = self.env['product.product'].create(vals)
                self.env['ir.config_parameter'].sudo().set_param(
                    'tf_peec_supplier_advances.default_deposit_product_id', self.product_id.id)

            purchase_line_obj = self.env['purchase.order.line']
            for order in purchase_orders:
                amount, name = self._get_advance_details(order)

                if self.product_id.purchase_method != 'purchase':
                    raise UserError(_('The product used to bill a down payment should have an control policy set to '
                                      '"Ordered quantities". Please update your deposit product to be able to create a '
                                      'deposit bill.'))
                if self.product_id.type != 'service':
                    raise UserError(_("The product used to bill a down payment should be of type 'Service'. "
                                      "Please use another product or update this product."))
                taxes = self.product_id.supplier_taxes_id.filtered(
                    lambda r: not order.company_id or r.company_id == order.company_id)
                if order.fiscal_position_id and taxes:
                    tax_ids = order.fiscal_position_id.map_tax(taxes, self.product_id, order.partner_id).ids
                else:
                    tax_ids = taxes.ids
                analytic_tag_ids = []
                for line in order.order_line:
                    analytic_tag_ids = [(4, analytic_tag.id, None) for analytic_tag in line.analytic_tag_ids]

                po_line_values = self._prepare_po_line(order, analytic_tag_ids, tax_ids, amount)
                po_line = purchase_line_obj.create(po_line_values)
                self._create_bill(order, po_line, amount)
        if self._context.get('open_bills', False):
            return purchase_orders.action_view_invoice()
        return {'type': 'ir.actions.act_window_close'}

    def _prepare_deposit_product(self):
        return {
            'name': 'Down payment',
            'type': 'service',
            'purchase_method': 'purchase',
            'property_account_expense_id': self.deposit_account_id.id,
            'taxes_id': [(6, 0, self.deposit_taxes_id.ids)],
            'company_id': False,
        }

