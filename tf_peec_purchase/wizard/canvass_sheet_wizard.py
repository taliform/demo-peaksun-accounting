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


class PeecCanvassSheetReject(models.TransientModel):
    _name = 'peec.canvass.sheet.reject'
    _description = 'Canvass Sheet Reject Wizard'

    canvass_id = fields.Many2one('peec.canvass.sheet', 'Canvass Sheet')
    name = fields.Text()

    def action_apply(self):
        self.ensure_one()
        self.canvass_id.action_reject(self.name)


class PeecCanvassSheetCreateWizard(models.TransientModel):
    _name = 'peec.canvass.sheet.create.wizard'
    _description = 'Canvass Sheet Creation Wizard'

    line_ids = fields.Many2many('peec.purchase.request.line', string="Request Lines")
    vendor_ids = fields.Many2many('res.partner', string="Vendors", domain="[('supplier_rank', '>', 0)]", limit=5)
    consolidate_prod = fields.Boolean("Consolidate Products")
    consolidate_desc = fields.Boolean("Consolidate Description")

    def action_confirm(self):
        line_ids = self.line_ids
        cs_line_obj = self.env['peec.canvass.sheet.line']
        vendor_line_obj = self.env['peec.canvass.sheet.vendor']

        # Remove lines that have purchase orders or canvas sheet
        line_ids = line_ids.filtered(lambda l: l.state == 'waiting')
        # Get Purchase Request Names
        pr_names = set(line_ids.mapped('request_id').mapped('name'))

        vendor_vals = []
        # Create Vendor Lines
        for vendor_id in self.vendor_ids:
            deliver_to = self.env['stock.picking.type'].search([
                ('code', '=', 'incoming'), ('company_id', '=', self.env.company.id)
            ], limit=1)
            vendor_vals.append((0, 0, {
                'vendor_id': vendor_id.id,
                'payment_term_id': vendor_id.property_supplier_payment_term_id.id or False,
                'deliver_to_id': deliver_to.id or False,
            }))

        # Create Canvass Sheet
        cs_id = self.env['peec.canvass.sheet'].create({
            'responsible_id': self.env.uid,
            'create_date': fields.Datetime.now(),
            'origin': ", ".join(pr_names),
            'vendor_ids': vendor_vals,
        }).id

        # Create Canvass Sheet Lines
        if not self.consolidate_prod:
            for line_id in line_ids:
                csl_id = cs_line_obj.create({
                    'canvass_id': cs_id,
                    'product_id': line_id.product_id.id,
                    'uom_id': line_id.uom_id.id,
                    'name': line_id.name,
                    'product_qty': line_id.product_qty,
                })
                csl_id.onchange_product_id()
                line_id.write({
                    'cs_id': cs_id,
                    'cs_line_id': csl_id.id
                })
        # Consolidated Products
        else:
            product_ids = set(line_ids.mapped('product_id'))
            for product_id in product_ids:
                prod_line_ids = line_ids.filtered(lambda v: v.product_id == product_id)
                name = prod_line_ids[0].name if not self.consolidate_desc else \
                    ", ".join(set(prod_line_ids.mapped('name')))
                uom_id = product_id.uom_po_id or product_id.uom_id
                # Init Line Vals
                vals = {
                    'canvass_id': cs_id,
                    'product_id': product_id.id,
                    'uom_id': uom_id.id,
                    'name': name,
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
                csl_id = cs_line_obj.create(vals)
                csl_id.onchange_product_id()
                prod_line_ids.write({
                    'cs_id': cs_id,
                    'cs_line_id': csl_id.id
                })

        # Transition Purchase Request Lines to Canvas State
        line_ids.action_canvass()

        # View Created Canvas
        return {
            'type': 'ir.actions.act_window',
            'name': 'Generated Canvass Sheet',
            'res_model': 'peec.canvass.sheet',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {},
            'domain': [('id', '=', cs_id)],
        }
