# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Martin Perez <martin@taliform.com>
# V13 Porting: Martin Perez <martin@taliform.com>
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
##############################################################################
from odoo import models, fields, api
from odoo.exceptions import UserError,  ValidationError


class PeecPurchaseRequestReject(models.TransientModel):
    _name = 'peec.purchase.request.reject'
    _description = 'Purchase Request Reject Wizard'

    request_id = fields.Many2one('peec.purchase.request', 'Purchase Request')
    name = fields.Text()

    def action_apply(self):
        self.ensure_one()
        self.request_id.action_reject(self.name)


class PeecPurchaseRequestPoCreateAdd(models.Model):
    _name = 'peec.pr.po.add'
    _description = 'Purchase Request Add to Existing'

    vendor_id = fields.Many2one('res.partner', 'Vendor')
    po_id = fields.Many2one('purchase.order', "Purchase Order")


class PeecPurchaseRequestPoCreate(models.TransientModel):
    _name = 'peec.purchase.request.po.create'
    _description = 'Purchase Request PO Creation Wizard'

    CREATE_OPTIONS = [
        ('new', "Create new purchase order"),
        ('add', "Add request lines to an existing draft RFQ"),
    ]

    line_ids = fields.Many2many('peec.purchase.request.line', string="Request Lines")
    add_po_ids = fields.Many2many('peec.pr.po.add', string="Add to Purchase Orders")
    consolidate_prod = fields.Boolean("Consolidate Products")
    consolidate_desc = fields.Boolean("Consolidate Description")
    create_option = fields.Selection(CREATE_OPTIONS, required=True, default='new')
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse')

    @api.onchange('line_ids', 'line_ids.vendor_id', 'create_option')
    def onchange_add(self):
        if self.create_option == 'new':
            self.add_po_ids = False
        else:
            vendor_ids = self.line_ids.mapped('vendor_id')
            self.add_po_ids = False
            for vendor_id in vendor_ids:
                if vendor_id not in self.add_po_ids.mapped('vendor_id'):
                    self.add_po_ids = [(0, 0, {'vendor_id': vendor_id.id})]

    def action_confirm(self):
        line_ids = self.line_ids
        if line_ids.filtered(lambda l: not l.vendor_id):
            raise UserError("A request line isn't tagged with a vendor.")

        # Remove lines that purchase orders already
        line_ids = line_ids.filtered(lambda l: l.state == 'waiting')

        po_ids = []
        # Filter by Vendor
        vendor_ids = set(line_ids.mapped('vendor_id'))
        for vendor_id in vendor_ids:
            vendor_line_ids = line_ids.filtered(lambda l: l.vendor_id == vendor_id)

            # Create New POs
            if self.create_option == 'new':
                po_ids.append(self.option_create(vendor_id, vendor_line_ids, self.warehouse_id))
            # Add to existing POs
            else:
                add_po_id = self.add_po_ids.filtered(lambda a: a.vendor_id == vendor_id)
                # Add to specified PO
                if add_po_id and add_po_id.po_id:
                    po_ids.append(self.option_add(vendor_line_ids, add_po_id.po_id))
                # If no PO is specified, create new
                else:
                    po_ids.append(self.option_create(vendor_id, vendor_line_ids))

        self.add_po_ids.unlink()

        #Mark Purchase Request if All POed
        pr_ids = line_ids.mapped('request_id')
        for pr_id in set(pr_ids):
            if pr_id.line_ids.filtered(lambda l: not l.po_id):
                pr_id.all_poed = False
            else:
                pr_id.all_poed = True

        # Transition lines to PO
        line_ids.action_po()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Orders',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {},
            'domain': [('id', 'in', po_ids)],
        }

    def option_add(self, vendor_line_ids, po_id):
        po_line_obj = self.env['purchase.order.line']
        pr_names = set(vendor_line_ids.mapped('request_id').mapped('name'))
        if po_id.origin:
            po_id.origin = po_id.origin + ", " + ", ".join(pr_names)

        # Not consolidated
        if not self.consolidate_prod:
            for vendor_line_id in vendor_line_ids:
                po_line_id = po_line_obj.create({
                    'order_id': po_id.id,
                    'product_id': vendor_line_id.product_id.id,
                    'name': vendor_line_id.name,
                    'product_qty': vendor_line_id.product_qty,
                    'product_uom': vendor_line_id.uom_id.id,
                    'price_unit': vendor_line_id.unit_cost,
                    'date_planned': fields.Datetime.now()
                })

                vendor_line_id.write({
                    'po_id': po_id.id,
                    'po_line_id': po_line_id.id
                })
        # Consolidated Products
        else:
            product_ids = set(vendor_line_ids.mapped('product_id'))
            for product_id in product_ids:
                prod_line_ids = vendor_line_ids.filtered(lambda v: v.product_id == product_id)
                name = prod_line_ids[0].name if not self.consolidate_desc \
                    else ", ".join(set(prod_line_ids.mapped('name')))

                # Check if existing purchase order has product in its lines
                existing_line_id = po_id.order_line.filtered(lambda o: o.product_id == product_id)
                if existing_line_id:
                    uom_id = existing_line_id.product_uom
                    # Determine Qty in consideration of UoM
                    qty = 0
                    for prod_line_id in prod_line_ids:
                        if uom_id != prod_line_id.uom_id:
                            qty += prod_line_id.uom_id._compute_quantity(prod_line_id.product_qty, uom_id, True)
                        else:
                            qty += prod_line_id.product_qty
                    # Add new quantity to existing line
                    existing_line_id[0].product_qty += qty
                    # Add existing line reference to po line
                    prod_line_ids.write({
                        'po_id': po_id.id,
                        'po_line_id': existing_line_id[0].id
                    })
                else:
                    uom_id = product_id.uom_po_id or product_id.uom_id
                    # Init Line Vals
                    vals = {
                        'order_id': po_id.id,
                        'product_id': product_id.id,
                        'name': name,
                        'product_uom': uom_id.id,
                        'date_planned': fields.Datetime.now(),
                        'price_unit': max(prod_line_ids.mapped('unit_cost')),
                    }

                    # Determine Qty in consideration of UoM
                    qty = 0
                    for prod_line_id in prod_line_ids:
                        if uom_id != prod_line_id.uom_id:
                            qty += prod_line_id.uom_id._compute_quantity(prod_line_id.product_qty, uom_id, True)
                        else:
                            qty += prod_line_id.product_qty
                    vals['product_qty'] = qty

                    # Create new line and add reference to purchase request
                    po_line_id = po_line_obj.create(vals)
                    prod_line_ids.write({
                        'po_id': po_id.id,
                        'po_line_id': po_line_id.id
                    })

        return po_id.id

    def option_create(self, vendor_id, vendor_line_ids, warehouse_id=None):
        dt_now = fields.Datetime.now()
        pol_obj = self.env['purchase.order.line']
        pr_names = set(vendor_line_ids.mapped('request_id').mapped('name'))

        # Create PO record
        vals = {
            'partner_id': vendor_id.id,
            'date_order': dt_now,
            'origin': ", ".join(pr_names)
        }

        if warehouse_id:
            # Search for Receipt picking type under the warehouse
            picking_type = self.env['stock.picking.type'].search([
                ('warehouse_id', '=', warehouse_id.id),
                ('code', '=', 'incoming')
            ], limit=1)
            if picking_type:
                vals['picking_type_id'] = picking_type.id
        po_id = self.env['purchase.order'].create(vals).id

        # Create PO Lines
        if not self.consolidate_prod:
            for vendor_line_id in vendor_line_ids:
                pol_id = pol_obj.create({
                    'order_id': po_id,
                    'product_id': vendor_line_id.product_id.id,
                    'name': vendor_line_id.name,
                    'product_qty': vendor_line_id.product_qty,
                    'product_uom': vendor_line_id.uom_id.id,
                    'price_unit': vendor_line_id.unit_cost,
                    'date_planned': dt_now,
                })
                vendor_line_id.write({
                    'po_id': po_id,
                    'po_line_id': pol_id.id
                })
        # Consolidated Products
        else:
            product_ids = set(vendor_line_ids.mapped('product_id'))
            for product_id in product_ids:
                prod_line_ids = vendor_line_ids.filtered(lambda v: v.product_id == product_id)
                name = prod_line_ids[0].name if not self.consolidate_desc else \
                    ", ".join(set(prod_line_ids.mapped('name')))
                uom_id = product_id.uom_po_id or product_id.uom_id
                # Init Line Vals
                vals = {
                    'order_id': po_id,
                    'product_id': product_id.id,
                    'name': name,
                    'product_uom': uom_id.id,
                    'date_planned': fields.Datetime.now(),
                    'price_unit': max(prod_line_ids.mapped('unit_cost')),
                }

                # Determine Qty in consideration of UoM
                qty = 0
                for prod_line_id in prod_line_ids:
                    if uom_id != prod_line_id.uom_id:
                        qty += prod_line_id.uom_id._compute_quantity(prod_line_id.product_qty, uom_id, True)
                    else:
                        qty += prod_line_id.product_qty
                vals['product_qty'] = qty

                # Create new line and add reference to purchase request
                po_line_id = pol_obj.create(vals)
                prod_line_ids.write({
                    'po_id': po_id,
                    'po_line_id': po_line_id.id
                })

        return po_id

