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
from odoo.exceptions import ValidationError, RedirectWarning, UserError


class PeecPurchaseRequest(models.Model):
    _name = "peec.purchase.request"
    _description = "Purchase Request"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'create_date desc, id desc'

    STATES = [
        ('draft', "Draft"),
        ('confirm', "Confirmed"),
        ('approval', "Approval"),
        ('approve', "Approved"),
        ('in_progress', "In Progress"),
        ('done', "Done"),
        ('cancel', "Cancelled"),
        ('reject', "For Revision"),
    ]

    name = fields.Char("Reference", default="Draft Purchase Request", copy=False, readonly=True,
                       help="System generated sequential identifier to be used as the main reference for the document.")
    line_ids = fields.One2many('peec.purchase.request.line', 'request_id', "Purchase Request Lines",
                               help="Indicates the items requested.", copy=True)
    requester_id = fields.Many2one('res.users', "Requested By", required=True,
                                   default=lambda self: self.env.uid, track_visibility='onchange',
                                   help="Indicates the user who made the Purchase Request.")
    approver_id = fields.Many2one('res.users', "Approved By", readonly=True, copy=False,
                                  help="Indicates the user who approved the Purchase Request.")
    currency_id = fields.Many2one('res.currency', 'Currency', required=True,
                                  default=lambda self: self.env.company.currency_id.id)
    # create_date = fields.Datetime("Date Created", readonly=True, default=fields.Datetime.now, copy=False,
    #                               help="Indicates the date and time the purchase request record was created.")
    approve_date = fields.Datetime("Date Approved", readonly=True, copy=False,
                                   help="Indicates the date and time the purchase request record was approved.")
    remarks = fields.Text("Remarks", help="Indicates any additional remarks the requestor wants to include in the "
                                          "purchase request.")
    product_id = fields.Many2one('product.product', related='line_ids.product_id', string='Product', readonly=False)
    is_confirmed = fields.Boolean("Confirmed", copy=False)
    reject_reason = fields.Char("Reject Reason", copy=False, track_visibility='onchange')
    state = fields.Selection(STATES, default='draft', copy=False, track_visibility='onchange',
                             help="Indicates the current status of the purchase request.")
    all_poed = fields.Boolean("All Ordered", default=False)
    po_nbr = fields.Integer(compute="_compute_po_nbr", string='Purchase Orders')
    cs_nbr = fields.Integer(compute="_compute_cs_nbr", string='Canvass Sheets')
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse')

    @api.depends('line_ids', 'line_ids.po_id')
    def _compute_po_nbr(self):
        for rec in self:
            po_from_pr = rec.line_ids.mapped('po_id')
            po_from_cs = rec.line_ids.mapped('cs_line_id').mapped('po_line_ids').mapped('order_id')
            rec.po_nbr = len(po_from_pr | po_from_cs)

    @api.depends('line_ids', 'line_ids.cs_id')
    def _compute_cs_nbr(self):
        for rec in self:
            rec.cs_nbr = len(set(rec.line_ids.mapped('cs_id')))

    def action_view_pos(self):
        po_from_pr = self.line_ids.mapped('po_id')
        po_from_cs = self.line_ids.mapped('cs_line_id').mapped('po_line_ids').mapped('order_id')
        po_ids = po_from_pr | po_from_cs

        return {
            'name': 'Related Purchase Orders',
            'view_mode': 'tree,form',
            'res_model': 'purchase.order',
            'domain': [('id', 'in', po_ids.ids)],
            'views': [(self.env.ref('tf_peec_purchase.peec_purchase_order_view_tree_readonly').id, 'tree'),
                      (False, 'form')],
            'type': 'ir.actions.act_window',
            'target': 'current'
        }

    def action_view_cs(self):
        return {
            'name': 'Related Canvass Sheets',
            'view_mode': 'tree,form',
            'res_model': 'peec.canvass.sheet',
            'domain': [('id', 'in', self.line_ids.mapped('cs_id').ids)],
            'views': [(self.env.ref('tf_peec_purchase.peec_canvass_sheet_view_tree_readonly').id, 'tree'),
                      (False, 'form')],
            'type': 'ir.actions.act_window',
            'target': 'current'
        }

    def unlink(self):
        if self.filtered(lambda x: x.is_confirmed):
            raise UserError('You may not delete a confirmed purchase request.')
        return super(PeecPurchaseRequest, self).unlink()

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancel'})
        self.mapped('line_ids').action_cancel()

    def action_confirm(self):
        sequence_obj = self.env['ir.sequence']
        for rec in self:
            if not rec.is_confirmed:
                rec.write({
                    'name': sequence_obj.sudo().next_by_code('peec.purchase.request'),
                    'is_confirmed': True,
                    'state': 'confirm'
                })
            else:
                rec.state = 'confirm'

    def action_for_approval(self):
        self.write({
            'state': 'approval'
        })

    def action_approve(self):
        self.write({
            'approver_id': self.env.uid,
            'approve_date': fields.Datetime.now(),
            'state': 'approve'
        })
        self.mapped('line_ids').action_approve()

    def action_reject_wizard(self):
        self.ensure_one()
        return {
            'name': 'Reject Purchase Request',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'peec.purchase.request.reject',
            'view_id': self.env.ref('tf_peec_purchase.peec_purchase_request_reject_form_view').id,
            'context': {'default_request_id': self.id},
            'type': 'ir.actions.act_window',
            'target': 'new'
        }

    def action_reject(self, reject_reason):
        self.write({
            'state': 'reject',
            'reject_reason': reject_reason
        })

    def action_force_done(self):
        self.write({'state': 'done'})
        self.mapped('line_ids').action_done()

    def action_done(self):
        self.write({'state': 'done'})

    def action_in_progress(self):
        self.write({'state': 'in_progress'})
        self.line_ids.action_waiting()

    def action_create_purchase_order(self):
        self.ensure_one()
        return {
            'name': 'Create Purchase Order',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'peec.purchase.request.po.create',
            'view_id': self.env.ref('tf_peec_purchase.peec_purchase_request_po_single_create_form_view').id,
            'context': {
                'default_line_ids': self.line_ids.ids,
                'default_warehouse_id': self.warehouse_id.id if self.warehouse_id else False
            },
            'type': 'ir.actions.act_window',
            'target': 'new'
        }

    def action_create_canvass_sheet(self):
        self.ensure_one()
        vendor_ids = self.line_ids.mapped('vendor_id')
        return {
            'name': 'Create Canvass Sheet',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'peec.canvass.sheet.create.wizard',
            'view_id': self.env.ref('tf_peec_purchase.peec_canvass_sheet_create_wizard_form_view').id,
            'context': {'default_line_ids': self.line_ids.ids, 'default_vendor_ids': vendor_ids.ids},
            'type': 'ir.actions.act_window',
            'target': 'new'
        }

#     <act_window name="Create Canvass Sheet"
#             res_model="peec.canvass.sheet.create.wizard" binding_model="peec.purchase.request.line"
#             view_mode="form" binding_views="list"
#             view_id="peec_canvass_sheet_create_wizard_form_view" target="new"
#             id="peec_canvass_sheet_create_wizard_action"
#             context = "{'default_line_ids': active_ids}"
#         />


class PeecPurchaseRequestLine(models.Model):
    _name = "peec.purchase.request.line"
    _description = "Purchase Request Lines"

    _STATES = [
        ('unapproved', "Unapproved"),
        ('approve', "Approved"),
        ('waiting', "Waiting"),
        ('canvass', "Canvass Sheet"),
        ('po', "Purchase Order"),
        ('shipping', "For Shipping"),
        ('partial', "Partially Delivered"),
        ('delivered', "Delivered"),
        ('done', "Marked Done"),
        ('cancel', "Cancelled"),
    ]

    request_id = fields.Many2one('peec.purchase.request', "Purchase Request", ondelete='cascade',
                                 help="Indicates the parent purchase request record.", required=True, )
    currency_id = fields.Many2one(related='request_id.currency_id')
    product_id = fields.Many2one('product.product', "Product", required=True,
                                 help="Indicates the product requested, if product record is already available in "
                                      "the system")
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    requester_id = fields.Many2one(related='request_id.requester_id')
    vendor_id = fields.Many2one('res.partner', "Preferred Vendor", help="Indicates the preferred vendor of the product"
                                                                        " being requested, if applicable.")
    uom_id = fields.Many2one('uom.uom', string='UoM', required=True,
                             domain="[('category_id', '=', product_uom_category_id)]")
    name = fields.Char("Description", required=True,
                       help="Indicates the description of the product being requested")
    product_qty = fields.Float(string='Quantity', digits='Product Unit of Measure', required=True,
                               help="Indicates the quantity of the product requested")
    unit_cost = fields.Monetary("Unit Cost", required=True,
                                help="Indicates the known or predicted cost of the product requested")
    state = fields.Selection(_STATES, "State", default='unapproved', copy=False, readonly=True,
                             help="Indicates the current state of the purchase request line.")
    pr_create_date = fields.Datetime(related='request_id.create_date')
    po_id = fields.Many2one('purchase.order', "Purchase Order Reference", copy=False)
    po_line_id = fields.Many2one('purchase.order.line', "Purchase Order Line Reference", copy=False)
    cs_id = fields.Many2one('peec.canvass.sheet', "Canvass Sheet Reference")
    cs_line_id = fields.Many2one('peec.canvass.sheet.line', "Canvass Sheet Line Reference")

    def action_canvass(self):
        self.write({'state': 'canvass'})

    def action_approve(self):
        self.write({'state': 'approve'})

    def for_shipping(self):
        self.write({'state': 'shipping'})

    def action_po(self):
        self.write({'state': 'po'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_delivered(self):
        self.write({'state': 'delivered'})
        self.check_complete()

    def action_partial(self):
        self.write({'state': 'partial'})

    def action_done(self):
        self.write({'state': 'done'})
        self.check_complete()

    def action_waiting(self):
        self.mapped('request_id').write({'all_poed': False})
        self.write({
            'po_id': False,
            'po_line_id': False,
            'state': 'waiting'
        })

    def check_complete(self):
        for rec in self:
            request_id = rec.request_id
            complete = True
            if not request_id.line_ids.filtered(lambda l: l.state not in ['done', 'cancel', 'delivered']):
                request_id.action_done()

    @api.onchange('product_id')
    def onchange_product_id(self):
        product_id = self.product_id
        if product_id:
            name = product_id.display_name
            if product_id.description_purchase:
                name += '\n' + product_id.description_purchase
            self.update({
                'name': name,
                'uom_id': product_id.uom_po_id or product_id.uom_id
            })

    def action_create_canvass_sheet(self):
        self.ensure_one()
        active_ids = self._context('active_ids')
        print(active_ids)
        print(self._context())
        vendor_ids = self.line_ids.mapped('vendor_id')
        return {
            'name': 'Create Canvass Sheet',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'peec.canvass.sheet.create.wizard',
            'view_id': self.env.ref('tf_peec_purchase.peec_canvass_sheet_create_wizard_form_view').id,
            'context': {'default_line_ids': self.line_ids.ids, 'default_vendor_ids': vendor_ids.ids},
            'type': 'ir.actions.act_window',
            'target': 'new'
        }