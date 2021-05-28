# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2021 Taliform Inc.
#
# Author: Ana Trajano <ana@taliform.com>
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
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleAgreement(models.Model):
    _name = 'sale.agreement'
    _description = "Sales Agreement"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"

    _STATES = [('draft', 'Draft'),
               ('ongoing', 'Ongoing'),
               ('closed', 'Closed'),
               ('cancel', 'Cancelled')]

    name = fields.Char("Reference", default="New", copy=False, readonly=True,
                       help="System generated sequential identifier to be used as the main reference for the document.")
    partner_id = fields.Many2one('res.partner', 'Customer', required=True, track_visibility='onchange')
    partner_trade_name = fields.Char(related='partner_id.trade_name', store=True)
    sale_location_id = fields.Many2one('sale.location', help="Indicates the customer’s sale location",
                                       track_visibility='onchange')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    line_ids = fields.One2many('sale.agreement.line', 'sales_agreement_id', 'Sale Agreement Lines', copy=True)
    so_ids = fields.One2many('sale.order', 'sales_agreement_id', 'Sale Orders', copy=False,
                             help="Indicates the Sales Orders that were created from the Sale Agreement")
    origin = fields.Char('Source Document', help="Indicates the source document (i.e. Customer PO)",
                         track_visibility='onchange')
    description = fields.Text('Terms and Conditions', track_visibility='onchange',
                              help="Indicates the Sales Agreement Terms and Conditions that will be copied "
                              "over to created Sales Orders")
    trade_name = fields.Char(related='partner_id.trade_name', help="Indicates the Customer’s Trade Name")
    agreement_date = fields.Date('Agreement Date', help="Indicates the date the agreement was made",
                                 track_visibility='onchange')
    state = fields.Selection(_STATES, string='Status', default='draft', copy=False, readonly=True,
                             track_visibility='onchange')
    currency_id = fields.Many2one('res.currency', 'Currency', required=True,
                                  default=lambda self: self.env.company.currency_id.id)
    total_qty = fields.Float('Quantity', compute='_compute_quantities', store=True)
    total_alloc_qty = fields.Float('Allocated', compute='_compute_quantities', store=True)
    total_invoiced_qty = fields.Float('Invoiced', compute='_compute_quantities', store=True)
    total_balance_qty = fields.Float('Balance', compute='_compute_quantities', store=True)
    total_intransit_qty = fields.Float('In-Transit', compute='_compute_quantities', store=True)

    @api.depends('line_ids', 'line_ids.product_qty', 'line_ids.product_alloc_qty',
                  'line_ids.balance_qty', 'line_ids.intransit_qty', 'line_ids.invoiced_qty')
    def _compute_quantities(self):
        for rec in self:
            total_qty = total_alloc_qty = total_invoiced_qty = total_balance_qty = total_intransit_qty = 0

            for line in rec.line_ids:
                total_qty += line.product_qty
                total_alloc_qty += line.product_alloc_qty
                total_balance_qty += line.balance_qty
                total_intransit_qty += line.intransit_qty
                total_invoiced_qty += line.invoiced_qty

            rec.total_qty = total_qty
            rec.total_alloc_qty = total_alloc_qty
            rec.total_balance_qty = total_balance_qty
            rec.total_intransit_qty = total_intransit_qty
            rec.total_invoiced_qty = total_invoiced_qty

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        """
        Check existing ongoing agreement for the specific customer
        """
        if self.partner_id:
            # Check existing agreements with the same customer
            ext_agreement_ids = self.env['sale.agreement'].search([('partner_id', '=', self.partner_id.id),
                                                                   ('state', '=', 'ongoing')])

            if any(ext_agreement_ids):
                title = _("Warning for %s") % self.partner_id.name
                message = _(
                    "There is already an ongoing sales agreement for this customer. We suggest you to complete "
                    "the existing ongoing agreement instead of creating a new one.")
                warning = {
                    'title': title,
                    'message': message
                }
                return {'warning': warning}

    def action_confirm_ongoing(self):
        sequence_obj = self.env['ir.sequence']
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('You cannot confirm the sales agreement without products.'))
            else:
                for line_id in rec.line_ids:
                    if line_id.price_unit <= 0.0:
                        raise UserError(_('You cannot confirm the sales agreement without price.'))
                    if line_id.product_qty <= 0.0:
                        raise UserError(_('You cannot confirm the sales agreement without quantity.'))
                if not rec.agreement_date:
                    rec.agreement_date = fields.Date.today()
                rec.write({
                    'name': sequence_obj.next_by_code('peec.sale.agreement'),
                    'state': 'ongoing'
                })

    def create_quotation(self):
        for rec in self:
            so_vals = {'partner_id': rec.partner_id.id,
                       'sales_agreement_id': rec.id,
                       'sale_type': 'cement',
                       'sale_operation': 'cif'}
            so_id = self.env['sale.order'].create(so_vals)
            so_id.onchange_sales_agreement_id()

            return {
                'name': _("Quotations (Cement)"),
                'view_mode': 'form',
                'view_id': self.env.ref('tf_peec_sales.peec_sales_order_ch_view_form').id,
                'res_model': 'sale.order',
                'type': 'ir.actions.act_window',
                'domain': '[]',
                'res_id': so_id.id,
                'context': {'active_id': so_id.id,
                            'default_sale_type': 'cement',
                            'default_sale_operation': 'cif'
                            }
            }

    def action_close(self):
        for rec in self:
            if any(sale_order.state in ['draft', 'sent'] for sale_order in
                   rec.mapped('so_ids')):
                raise UserError(_('You have to cancel or validate every quotation before closing '
                                  'the sales agreement.'))
            rec.write({'state': 'closed'})

    def action_cancel(self):
        for rec in self:
            # Try to set all associated quotations to cancel state
            rec.so_ids.action_cancel()
            for so_id in rec.so_ids:
                so_id.message_post(body=_('Cancelled by the agreement associated to this quotation.'))
            rec.write({'state': 'cancel'})

    def unlink(self):
        for rec in self:
            if any(agreement_id.state != 'draft' for agreement_id in rec):
                raise UserError(_('You can only delete draft agreements.'))
            # Delete agreement lines
            rec.mapped('line_ids').unlink()
        return super(SaleAgreement, self).unlink()


class SaleAgreementLine(models.Model):
    _name = 'sale.agreement.line'
    _description = "Sale Agreement Line"
    _rec_name = 'product_id'

    sales_agreement_id = fields.Many2one('sale.agreement', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', domain=[('sale_ok', '=', True)], required=True)
    product_uom_id = fields.Many2one('uom.uom', 'Product Unit of Measure')
    company_id = fields.Many2one('res.company', related='sales_agreement_id.company_id', string='Company', store=True,
                                 readonly=True, default=lambda self: self.env.company)
    product_qty = fields.Float(string='Quantity', digits='Product Unit of Measure',
                               help="Indicates the agreed total order quantity of the customer")
    product_alloc_qty = fields.Float(compute='_compute_alloc_qty', string='Allocated Quantity',
                                     digits='Product Unit of Measure',
                                     help="Indicates the number of products that have already been allocated to "
                                          "projects", store=True)
    balance_qty = fields.Float('Balance', compute='_compute_balance_qty', store=True)
    intransit_qty = fields.Float('In-Transit', compute='_compute_intransit_qty', store=True)
    invoiced_qty = fields.Float('Invoiced', compute='_compute_invoiced_qty', store=True)
    price_unit = fields.Float(string='Unit Price', digits='Product Price')
    rate_computed = fields.Float(help="Indicates the computed rate for the selected product based on the Rate Table "
                                      "computation and Product’s Sales Price (Computed Rate = Product Sales Price + "
                                      "Rate Table Price)")
    state = fields.Selection(related='sales_agreement_id.state', string='Status')

    @api.depends('sales_agreement_id.so_ids.state',
                 'sales_agreement_id.so_ids.amount_qty')
    def _compute_alloc_qty(self):
        for line_id in self:
            total = 0.0
            for so_id in line_id.sales_agreement_id.so_ids.filtered(
                    lambda so: so.state in ['sale', 'done', 'closed']):
                for so_line_id in so_id.order_line.filtered(
                        lambda order_line: order_line.product_id == line_id.product_id):
                    total += so_line_id.product_uom_qty
            line_id.product_alloc_qty = total

    @api.depends('sales_agreement_id.so_ids.state',
                 'sales_agreement_id.so_ids.amount_balance')
    def _compute_balance_qty(self):
        for line_id in self:
            total = 0.0
            for so_id in line_id.sales_agreement_id.so_ids.filtered(
                    lambda so: so.state in ['sale', 'done', 'closed']):
                for so_line_id in so_id.order_line.filtered(
                        lambda order_line: order_line.product_id == line_id.product_id):
                    total += so_line_id.balance
            line_id.balance_qty = total

    @api.depends('sales_agreement_id.so_ids.state',
                 'sales_agreement_id.so_ids.amount_intransit')
    def _compute_intransit_qty(self):
        for line_id in self:
            total = 0.0
            for so_id in line_id.sales_agreement_id.so_ids.filtered(
                    lambda so: so.state in ['sale', 'done', 'closed']):
                for so_line_id in so_id.order_line.filtered(
                        lambda order_line: order_line.product_id == line_id.product_id):
                    total += so_line_id.in_transit
            line_id.intransit_qty = total

    @api.depends('sales_agreement_id.so_ids.state',
                 'sales_agreement_id.so_ids.amount_invoiced',)
    def _compute_invoiced_qty(self):
        for line_id in self:
            total = 0.0
            for so_id in line_id.sales_agreement_id.so_ids.filtered(
                    lambda so: so.state in ['sale', 'done', 'closed']):
                for so_line_id in so_id.order_line.filtered(
                        lambda order_line: order_line.product_id == line_id.product_id):
                    total += so_line_id.qty_invoiced
            line_id.invoiced_qty = total

    @api.model_create_multi
    def create(self, vals_list):
        records = super(SaleAgreementLine, self).create(vals_list)
        for rec in records:
            if rec.price_unit <= 0.0:
                raise UserError(_('You cannot confirm the sales agreement without price.'))

            # Limited to only 1 Sales Agreement Line
            if rec.sales_agreement_id:
                if len(rec.sales_agreement_id.line_ids) > 1:
                    raise UserError(_('Limited to only one product line.'))
        return records

    def write(self, vals):
        res = super(SaleAgreementLine, self).write(vals)
        if vals.get('price_unit', False):
            if vals['price_unit'] <= 0.0:
                raise UserError(_('You cannot confirm the sales agreement without price.'))
        return res

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id
            self.product_qty = 1.0

    def _prepare_order_line(self, name, product_qty=0.0, price_unit=0.0, tax_id=False):
        self.ensure_one()
        return {
            'name': name,
            'product_id': self.product_id.id,
            'product_uom': self.product_id.uom_id.id,
            'product_uom_qty': product_qty,
            'price_unit': price_unit,
            'tax_id': tax_id,
        }