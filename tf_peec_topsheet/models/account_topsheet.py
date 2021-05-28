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
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountTopsheet(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = 'account.topsheet'
    _description = 'Account Topsheet'

    _STATES = [
        ('draft', 'Draft'),
        ('validate', 'Validated')
    ]

    state = fields.Selection(_STATES, default='draft', copy=False)

    name = fields.Char(default="Draft Topsheet")
    for_monitoring = fields.Boolean(string='For Monitoring', default=False)
    customer_id = fields.Many2one('res.partner', string='Customer', required=False)
    sales_order_no = fields.Many2one('sale.order', string='Sales Order No.', index=True)

    customer_po_ref = fields.Char(compute='_get_customer_po_ref', string='P.O Reference', readonly=True)
    invoice_address = fields.Char(related='customer_id.contact_address_complete')

    invoice_ids = fields.One2many('account.move', 'topsheet_id', string='Invoices')
    delivery_ids = fields.One2many('stock.picking', 'id', string='Deliveries')
    topsheet_date = fields.Date('Topsheet Date', default=fields.Date.context_today)

    subject = fields.Char(string='Subject',
                          help='Divided into two parts, the subject header which displays on the print out in bold'
                               ' form and subject details.')
    attention = fields.Char(related='customer_id.display_name', string='Attention')
    thru = fields.Char(related='customer_id.display_name', string='Thru')
    delivery_order_id = fields.Many2one('stock.picking', compute='_get_delivery_order',
                                       string='Delivery Order')
    topsheet_total = fields.Float(compute='_get_topsheet_total', string='Total')

    @api.depends('sales_order_no')
    def _get_customer_po_ref(self):
        PurchaseOrder = self.env['purchase.order']
        for rec in self:
            customer_ref = ''
            if rec.sales_order_no:
                product_id = rec.sales_order_no.order_line[0].product_id.id
                customer_ref = PurchaseOrder.search([('product_id', '=', product_id)]).name
            rec.customer_po_ref = customer_ref

    @api.depends('invoice_ids')
    def _get_topsheet_total(self):
        for rec in self:
            topsheet_total = 0
            if rec.invoice_ids:
                topsheet_total = sum(rec.invoice_ids.mapped('amount_residual'))
            rec.topsheet_total = topsheet_total

    @api.depends('sales_order_no')
    def _get_delivery_order(self):
        StockPicking = self.env['stock.picking']
        for rec in self:
            if rec.sales_order_no:
                order_id = StockPicking.search([('origin', '=', rec.sales_order_no.name)])
                rec.delivery_order_id = order_id
            else:
                rec.delivery_order_id = False

    def action_confirm(self):
        for rec in self:
            if not rec.invoice_ids:
                raise ValidationError('Invoices should not be empty!')
            rec.state = 'validate'

