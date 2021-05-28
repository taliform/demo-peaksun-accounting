# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Martin Perez <martin@taliform.com>
# V13 Porting: Martin Perez <martin@taliform.com>
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


class PoMerge(models.TransientModel):
    _name = 'peec.purchase.order.merge'
    _description = 'Purchase Order Merge'

    def _get_default_pos(self):
        if self.env.context.get('retrieve_all', False):
            return self.env['purchase.order'].search([
                    ('purchase_type', '=', 'cement'),
                    ('state', '=', 'purchase')
                ]).ids

    res_ids = fields.Many2many('purchase.order', 'purchase_order_res_ids_rel', string="Purchase Orders",
                               default=_get_default_pos)
    po_ids = fields.Many2many('purchase.order', 'purchase_order_po_ids_rel', string="Purchase Orders (Cement)",
                              domain="[('purchase_type', '=', 'cement')]")
    partner_id = fields.Many2one('res.partner', "Partner", domain="[('supplier_rank','>', 0)]",
                                 help="Indicates the Partner to filter out from all selected Purchase Orders")
    product_id = fields.Many2one('product.product', "New Product",
                                 help="Indicates the product to use for the new Purchase Order")
    truck_load = fields.Float("Truck Load", default=1000,
                              help="Indicates the value of 1 truck load, which will be used as basis for filtering "
                                   "purchase orders that can be merged")
    new_unit_price = fields.Monetary("New Unit Price")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.ref('base.PHP').id)

    # This functions filters any PO that is not type cement and not in purchase status as we cannot selectively choose
    # which list view 'merge purchase orders' action will show. res_ids will contain every selected POs while po_ids
    # will contain the filtered ones
    @api.onchange('res_ids')
    def onchange_res_ids(self):
        if self.res_ids:
            self.po_ids = self.res_ids.\
                filtered(lambda po_id: po_id.purchase_type == 'cement' and po_id.state == 'purchase')

    def action_merge(self):
        # Validations
        if self.new_unit_price < 1:
            raise ValidationError("New unit price may not be less than 1.")
        if len(self.po_ids) < 2:
            raise ValidationError("Merging needs more than one purchase orders to proceed.")

        # Initialize
        po_obj = self.env['purchase.order']
        valid_po_ids = po_obj
        truck_load = self.truck_load
        partner_id = self.partner_id
        po_ids = self.po_ids

        price_unit = self.new_unit_price
        company_id = self.env.user.company_id
        dt_now = fields.Datetime.now()
        php_id = self.env.ref('base.PHP')

        # Filter by partner
        if partner_id:
            po_ids = po_ids.filtered(lambda p: p.partner_id == partner_id)

        # Filter by truck load
        for po_id in po_ids:
            if len(po_id.order_line) == 1:
                order_line = po_id.order_line[0]
                qty_received_manual = order_line.qty_received_manual
                qty_received = order_line.qty_received
                product_qty = order_line.product_qty
                if product_qty - qty_received_manual + qty_received < truck_load:
                    valid_po_ids = valid_po_ids | po_id

        # Create merged POs per Vendor
        vendor_ids = po_ids.mapped('partner_id')
        new_po_ids = []
        for vendor_id in vendor_ids:
            vendor_po_ids = valid_po_ids.filtered(lambda v: v.partner_id.id == vendor_id.id)

            if vendor_po_ids:
                product_id = self.product_id
                prod_name = product_id.display_name
                if product_id.description_purchase:
                    prod_name += '\n' + product_id.description_purchase

                # Get PHP Amount
                php_amount = 0
                for vendor_po_id in vendor_po_ids:
                    amount_untaxed = vendor_po_id.amount_untaxed
                    po_currency = vendor_po_id.currency_id
                    if po_currency == php_id:
                        php_amount += amount_untaxed
                    else:
                        php_amount += po_currency._convert(amount_untaxed, php_id, company_id,
                                                           vendor_po_id.date_order, round=True)

                new_po_id = po_obj.create({
                    'partner_id': vendor_id.id,
                    'date_approve': dt_now,
                    'company_id': company_id.id,
                    'purchase_type': 'cement',
                    'currency_id': php_id.id,
                    'order_line': [(0, 0, {
                        'product_id': product_id.id,
                        'name': prod_name,
                        'price_unit': price_unit,
                        'product_qty': php_amount / price_unit,
                        'product_uom': product_id.uom_po_id.id or product_id.uom_id.id,
                        'currency_id': php_id.id,
                        'state': 'draft',
                        'date_planned': dt_now,
                        'taxes_id': product_id.supplier_taxes_id.ids
                    })]
                })

                new_po_ids.append(new_po_id.id)

        # Transition merged Pos to done
        valid_po_ids.button_done()

        # View newly created purchase order
        tree_view = self.env.ref('purchase.purchase_order_tree')
        form_view = self.env.ref('tf_peec_purchase.peec_purchase_order_cement_form')
        return {
            'name': 'Merged Purchase Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'views': [(tree_view.id, 'tree'), (form_view.id, 'form')],
            'target': 'current',
            'domain': [('id', 'in', new_po_ids)],
        }
