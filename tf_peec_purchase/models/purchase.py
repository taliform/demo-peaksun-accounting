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
from odoo.tools.misc import formatLang, get_lang
from odoo.exceptions import ValidationError, RedirectWarning

_PURCHASE_TYPES = [
        ('standard', "Standard"),
        ('cement', "Cement"),
        ('tire', "Product Service"),
    ]


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    cement_plant_id = fields.Many2one('res.partner', domain=[('is_cement_plant', '=', True)],
                                      help="Indicates the contact record of the vendor's cement plant.")
    purchase_type = fields.Selection(_PURCHASE_TYPES, "Purchase Type", default='standard',
                                     help="Indicates the type of purchase, which will be used to differentiate which "
                                          "form view to display")
    canvass_id = fields.Many2one('peec.canvass.sheet', 'Canvass Sheet')
    atw_ids = fields.One2many('logistics.atw', 'purchase_id', 'ATWs')
    atw_count = fields.Integer('No. of ATWs', compute='_compute_atw_count')
    cement_product_id = fields.Many2one('product.product', 'Cement Product', compute='_compute_cement_product', store=True)
    balance_qty = fields.Float('Balance', compute='_compute_cement_product', store=True)

    def _compute_atw_count(self):
        """ Count the number of trip logs """
        stat_data = self.env['logistics.atw'].read_group(
            [('purchase_id', 'in', self.ids)], ['purchase_id'], ['purchase_id'])
        mapped_data = dict([(m['purchase_id'][0], m['purchase_id_count']) for m in stat_data])
        for purchase_order in self:
            purchase_order.atw_count = mapped_data.get(purchase_order.id, 0)

    @api.depends('order_line', 'purchase_type')
    def _compute_cement_product(self):
        for rec in self:
            if rec.purchase_type == 'cement':
                for line in rec.order_line:
                    rec.cement_product_id = line.product_id
                    rec.balance_qty = line.balance_qty
            else:
                rec.cement_product_id = False
                rec.balance_qty = 0

    @api.onchange('order_line')
    def onchange_order_line(self):
        for rec in self.filtered(lambda s: s.purchase_type == 'cement'):
            if len(rec.order_line) > 1:
                raise ValidationError("Only one product is allowed for cement purchase orders.")

    @api.onchange('purchase_tax_ids')
    def onchange_purchase_tax_ids(self):
        for rec in self:
            if rec.purchase_tax_ids:
                for line in rec.order_line:
                    line.taxes_id = [(6, 0, rec.purchase_tax_ids.ids)]
            else:
                for line in rec.order_line:
                    line.taxes_id = [(5, 0, 0)]

    # Return request lines to waiting if PO is cancelled
    def button_cancel(self):
        res = super(PurchaseOrder, self).button_cancel()
        for rec in self:
            # Cancel Purchase Request Lines
            rec.order_line.mapped('request_line_ids').action_cancel()
            # Cancel Canvass Sheet if all its related purchase order lines have been cancelled
            canvass_ids = rec.order_line.mapped('cs_line_id').mapped('canvass_id')
            for canvass_id in canvass_ids:
                if not canvass_id.line_ids.mapped('po_line_ids').mapped('order_id').filtered(lambda o:
                                                                                             o.state != 'cancel'):
                    # This unlinks the canvass sheet to its related purchase request line and return it to waiting state
                    canvass_id.action_cancel()

        return res

    # Set request lines to for shipping state on PO confirmation
    def button_confirm(self):
        for rec in self:
            rec.order_line.mapped('request_line_ids').for_shipping()
            rec.order_line.cs_line_id.request_line_ids.for_shipping()
        return super(PurchaseOrder, self).button_confirm()

    def action_view_atws(self):
        action = self.env.ref('tf_peec_logistics.action_logistics_atw').read()[0]
        action['domain'] = [('purchase_id', 'in', self.ids)]
        return action


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    cs_line_id = fields.Many2one('peec.canvass.sheet.line', "Source Canvass Sheet")
    request_line_ids = fields.One2many('peec.purchase.request.line', 'po_line_id', "Source Purchase Request Lines")
    serial_id = fields.Many2one('stock.production.lot', "Tire Serial", help="Indicates the serial number of a product "
                                                                            "which received the service.")
    deferred_expense = fields.Boolean("Deferred Expense", help="Indicates whether the expense brought by the purchase "
                                                               "order line (for tire services) needs to be deferred "
                                                               "because tire is not mounted to any vehicle")
    balance_qty = fields.Float('Balance', compute="_compute_balance_qty", store=True)
    cement_plant_id = fields.Many2one(related='order_id.cement_plant_id', store=True)

    @api.depends('product_qty', 'qty_received')
    def _compute_balance_qty(self):
        for rec in self:
            rec.balance_qty = rec.product_qty - rec.qty_received

    # Return purchase request line to waiting if referenced order line is deleted.
    def unlink(self):
        for rec in self.filtered(lambda r: r.request_line_ids):
            rec.request_line_ids.action_waiting()

        return super(PurchaseOrderLine, self).unlink()


class PurchaseAgreement(models.Model):
    _inherit = 'purchase.requisition'

    desc = fields.Char('Description')
    description = fields.Char('Terms and Conditions')
    balance_qty = fields.Float('Balance', compute='_compute_balance', store=True)
    purchase_type = fields.Selection(_PURCHASE_TYPES, "Purchase Type", default='standard',
                                     help="Indicates the type of purchase, which will be used to differentiate which "
                                          "form view to display")
    cement_count = fields.Integer(compute='_compute_orders_number', string='No. of Cement Orders')
    tire_count = fields.Integer(compute='_compute_orders_number', string='No. of Product Service Orders')

    @api.depends('line_ids', 'line_ids.balance_qty')
    def _compute_balance(self):
        for rec in self:
            rec.balance_qty = sum(rec.line_ids.mapped('balance_qty'))

    @api.depends('purchase_ids')
    def _compute_orders_number(self):
        for requisition in self:
            requisition.order_count = len(requisition.purchase_ids.filtered(lambda p: p.purchase_type == 'standard'))
            requisition.cement_count = len(requisition.purchase_ids.filtered(lambda p: p.purchase_type == 'cement'))
            requisition.tire_count = len(requisition.purchase_ids.filtered(lambda p: p.purchase_type == 'tire'))

    def name_get(self):
        result = []
        for pa in self:
            if pa.desc:
                name = "%s (%s)" % (
                    pa.name,
                    pa.desc
                )
            else:
                name = pa.name
            result.append((pa.id, name))
        return result

    def action_new_quotation(self):
        self.ensure_one()

        if self.purchase_type == 'standard':
            tree_view = self.env.ref('purchase.purchase_order_tree')
            form_view = self.env.ref('purchase.purchase_order_form')
            name = 'Request for Quotations'
        elif self.purchase_type == 'cement':
            tree_view = self.env.ref('tf_peec_purchase.peec_purchase_order_cement_tree')
            form_view = self.env.ref('tf_peec_purchase.peec_purchase_order_cement_form')
            name = 'Request for Quotations (Cement)'
        else:
            tree_view = self.env.ref('purchase.purchase_order_tree')
            form_view = self.env.ref('tf_peec_purchase.peec_purchase_order_tire_form')
            name = 'Request for Quotations (Product Services)'

        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'purchase.order',
            'views': [(form_view.id, 'form'), (tree_view.id, 'tree')],
            'view_mode': 'form,tree',
            'target': 'current',
            'context': {
                'default_requisition_id': self.id,
                'default_user_id': False,
                'default_purchase_type': self.purchase_type
            }
        }

    def action_view_orders(self):
        self.ensure_one()

        if self.purchase_type == 'standard':
            tree_view = self.env.ref('purchase.purchase_order_tree')
            form_view = self.env.ref('purchase.purchase_order_form')
            name = 'Request for Quotations'
        elif self.purchase_type == 'cement':
            tree_view = self.env.ref('tf_peec_purchase.peec_purchase_order_cement_tree')
            form_view = self.env.ref('tf_peec_purchase.peec_purchase_order_cement_form')
            name = 'Request for Quotations (Cement)'
        else:
            tree_view = self.env.ref('purchase.purchase_order_tree')
            form_view = self.env.ref('tf_peec_purchase.peec_purchase_order_tire_form')
            name = 'Request for Quotations (Product Services)'

        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'purchase.order',
            'domain': [('requisition_id', '=', self.id), ('purchase_type', '=', self.purchase_type)],
            'views': [(tree_view.id, 'tree'), (form_view.id, 'form')],
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {
                'default_purchase_type': self.purchase_type,
                'default_partner_id': self.vendor_id.id,
            }
        }


class PurchaseAgreementLine(models.Model):
    _inherit = 'purchase.requisition.line'

    balance_qty = fields.Float('Balance', compute='_compute_balance', store=True)

    @api.depends('product_qty', 'qty_ordered')
    def _compute_balance(self):
        for rec in self:
            rec.balance_qty = rec.product_qty - rec.qty_ordered
