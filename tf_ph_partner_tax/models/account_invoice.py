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
from odoo import models, fields, api
from lxml import etree

from odoo.exceptions import ValidationError

_TRANSACTION_TYPES = [('0', 'Purchase of Capital Goods'),
                      ('1', 'Purchase of Good Other than Capital Goods'),
                      ('2', 'Purchase of Services'),
                      ('3', 'Purchases Not Qualified for Input Tax'),
                      ('4', 'Others')]


class AccountInvoice(models.Model):
    _inherit = 'account.move'

    vatable = fields.Monetary(string='VATable', compute='_compute_taxes', digits='Account')
    exempt = fields.Monetary(string='VAT-Exempt', compute='_compute_taxes', digits='Account')
    zero = fields.Monetary(string='Zero Rated', compute='_compute_taxes', digits='Account')
    sale_tax_ids = fields.Many2many('account.tax', 'tf_ph_sale_invoice_tax', 'sale_tax_ids', 'invoice_id',
                                    string='Sale Tax', domain=[('type_tax_use', 'in', ['sale', 'none'])])
    purchase_tax_ids = fields.Many2many('account.tax', 'tf_ph_purchase_invoice_tax', 'purchase_tax_ids', 'invoice_id',
                                        string='Purchase Tax', domain=[('type_tax_use', 'in', ['purchase', 'none'])])
    base_transaction_type = fields.Selection(_TRANSACTION_TYPES, string='Transaction Type',
                                             related='partner_id.transaction_type', readonly=False,
                                             help="Updating this field also updates the Transaction Type specified in "
                                                  "the Supplier's Sales and Purchases configuration")
    ewt = fields.Monetary(string='EWT', compute='_compute_taxes', digits='Account')
    vat_tax = fields.Monetary(string='VAT', compute='_compute_taxes', digits='Account')
    show_update_transactions = fields.Boolean('Show Update Transactions Button',
                                              compute="_compute_show_update_transactions", store=True)

    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_id(self):
        res = super(AccountInvoice, self)._onchange_partner_id()
        self.sale_tax_ids = self.partner_id.sale_tax_ids.ids or []
        self.purchase_tax_ids = self.partner_id.purchase_tax_ids.ids or []

        return res

    @api.depends('base_transaction_type')
    def _compute_show_update_transactions(self):
        for rec in self:
            if rec.base_transaction_type and any(rec.invoice_line_ids.mapped(lambda l: l.transaction_type != rec.base_transaction_type)):
                rec.show_update_transactions = True
            else:
                rec.show_update_transactions = False

    @api.depends('invoice_line_ids', 'invoice_line_ids.tax_ids', 'line_ids', 'line_ids.tax_line_id')
    def _compute_taxes(self):
        company = self.env.user.company_id

        vat_exempt_tax_ids = company.vat_exempt_tax_ids
        zero_rated_tax_ids = company.zero_rated_tax_ids
        vatable_taxes = company.vat_tax_ids

        for rec in self:
            rec.vatable = sum(
                rec.invoice_line_ids.filtered(lambda r: r.tax_ids & vatable_taxes).mapped('price_subtotal'))
            rec.exempt = sum(
                rec.invoice_line_ids.filtered(lambda r: r.tax_ids & vat_exempt_tax_ids).mapped('price_subtotal'))
            rec.zero = sum(
                rec.invoice_line_ids.filtered(lambda r: r.tax_ids & zero_rated_tax_ids).mapped('price_subtotal'))
            rec.ewt = sum(
                rec.line_ids.filtered(lambda r: r.tax_line_id and r.price_subtotal < 0).mapped('price_subtotal'))
            rec.vat_tax = sum(
                rec.line_ids.filtered(lambda r: r.tax_line_id and r.price_subtotal > 0).mapped('price_subtotal'))

    def button_upd_transaction(self):
        for rec in self:
            rec.invoice_line_ids.write({'transaction_type': rec.base_transaction_type})
            rec.show_update_transactions = False

    def write(self, vals):
        records = vals
        for rec in self:
            for invoice_line in rec.invoice_line_ids:
                if not invoice_line.req_transaction_type and not invoice_line.transaction_type:
                    invoice_line.transaction_type = '0'
        return super(AccountInvoice, self).write(vals)

class AccountInvoiceLine(models.Model):
    _inherit = 'account.move.line'

    transaction_type = fields.Selection(_TRANSACTION_TYPES, string='Transaction Type', default='0')
    invoice_state = fields.Selection(string='Invoice State', related='move_id.state', store=True)
    req_transaction_type = fields.Boolean('Require Transaction Type', compute='get_req_transaction_type', store=True)
    type = fields.Selection(related='move_id.type', store=True)

    @api.depends('tax_ids')
    def get_req_transaction_type(self):
        company = self.env.user.company_id
        vat_tax_ids = company.vat_tax_ids

        req_transaction_type = False

        if vat_tax_ids:
            for rec in self:
                rec.req_transaction_type = False
                if rec.move_id.type in ['in_invoice', 'in_receipt', 'in_refund']:
                    if set(rec.tax_ids.ids).intersection(set(vat_tax_ids.ids)):
                        req_transaction_type = True
                rec.req_transaction_type = req_transaction_type
        else:
            self.req_transaction_type = req_transaction_type

    @api.onchange('product_id')
    def _onchange_product_id(self):
        res = super(AccountInvoiceLine, self)._onchange_product_id()
        account_type = self.move_id.type
        if account_type in ('out_invoice', 'out_receipt', 'out_refund'):
            self.tax_ids = self.move_id.sale_tax_ids.ids
        if account_type in ('in_invoice', 'in_receipt', 'in_refund'):
            self.tax_ids = self.move_id.purchase_tax_ids.ids
            self.transaction_type = self.move_id.base_transaction_type

        return res

    def write_transaction(self):
        return self.write({'transaction_type': self._context.get('transaction_type')})

    def change_transaction_type(self):
        dummy, view_id = self.env['ir.model.data'].get_object_reference('tf_ph_partner_tax',
                                                                        'tf_ph_partner_change_transaction_invoice_view')

        return {
            'name': "Change Transaction Type",
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': view_id,
            'res_model': 'account.move.line',
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {'product_id': self.product_id.id,
                        'transaction_type': self.transaction_type},
        }
