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
from lxml import etree

from odoo import api, fields, models, _
from odoo.addons.base.models.ir_ui_view import transfer_field_to_modifiers, transfer_modifiers_to_node, \
    transfer_node_to_modifiers
from odoo.exceptions import ValidationError, UserError

_NUMBERS = ['one', 'two', 'three', 'four', 'five']


class PeecCanvassSheet(models.Model):
    _name = "peec.canvass.sheet"
    _description = "Canvass Sheet"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'create_date desc, id desc'

    STATES = [
        ('draft', "Draft"),
        ('confirm', "Confirmed"),
        ('rfq', "Waiting Bid"),
        ('bid', "Bid Received"),
        ('approval', "Approval"),
        ('done', "Done"),
        ('cancel', "Cancelled"),
        ('reject', "For Revision"),
    ]

    name = fields.Char("Reference", default="Draft Canvass Sheet", copy=False, readonly=True,
                       help="System generated sequential identifier to be used as the main reference for the document.")
    responsible_id = fields.Many2one('res.users', "Responsible", required=True,
                                     default=lambda self: self.env.uid, track_visibility='onchange',
                                     help="Indicates the user responsible for the canvass sheet.")
    approver_id = fields.Many2one('res.users', "Approved By", readonly=True, copy=False,
                                  help="Indicates the user who approved the Canvass Sheet.")
    currency_id = fields.Many2one('res.currency', 'Currency', required=True,
                                  default=lambda self: self.env.company.currency_id.id)
    product_id = fields.Many2one('product.product', related='line_ids.product_id', string='Product', readonly=False)
    vendor_id = fields.Many2one('res.partner', related='vendor_ids.vendor_id', string='Vendor', readonly=False)
    vendor_domain_ids = fields.Many2many('res.partner', string="Vendor Domain", compute="_compute_vendor_domain",
                                         store=True)
    line_ids = fields.One2many('peec.canvass.sheet.line', 'canvass_id', "Canvass Sheet Lines",
                               help="Lists the items to be canvassed. These items were consolidated from multiple "
                                    "Purchase Request / Purchase Order records, or added manually.", copy=True)
    vendor_ids = fields.One2many('peec.canvass.sheet.vendor', 'canvass_id', "Canvass Sheet Vendors", copy=True,
                                 help="Indicates up to five (5) suppliers to whom a Request for Quotation (RFQ) "
                                      "will be submitted.")
    # create_date = fields.Datetime("Date Created", readonly=True, default=fields.Datetime.now, copy=False,
    #                               help="Indicates the date and time the canvass sheet record was created.")
    approve_date = fields.Datetime("Date Approved", readonly=True, copy=False,
                                   help="Indicates the date and time the canvass sheet record was approved.")
    remarks = fields.Text("Remarks", help="Provides notes for additional information on Canvass Sheet")
    reject_reason = fields.Char("Reject Reason", copy=False, track_visibility='onchange')
    rfq_sent = fields.Boolean("RFQ Sent", copy=False)
    purchase_ids = fields.One2many('purchase.order', 'canvass_id', 'Purchase Orders')
    origin = fields.Char("Source Document",
                         help="Indicates the source document/s of the Canvass Sheet record. It is populated by the "
                              "system upon creation of Canvass Sheet document from Purchase Request / "
                              "Purchase Order records.")
    state = fields.Selection(STATES, default='draft', copy=False, track_visibility='onchange',
                             help="Indicates the current status of the Canvass Sheet.")
    all_poed = fields.Boolean("All Ordered", default=False)
    po_nbr = fields.Integer(compute="_compute_po_nbr", string='Purchase Orders')

    @api.depends('vendor_ids', 'vendor_ids.vendor_id')
    def _compute_vendor_domain(self):
        for rec in self:
            rec.vendor_domain_ids = rec.vendor_ids.mapped('vendor_id')

    @api.constrains('vendor_ids')
    def limit_vendors(self):
        for rec in self:
            if len(rec.vendor_ids) > 5:
                raise ValidationError("You may only add up to 5 vendors.")

    def _compute_po_nbr(self):
        for rec in self:
            rec.po_nbr = len(rec.line_ids.mapped('po_line_ids').mapped('order_id'))

    def unlink(self):
        if self.filtered(lambda x: x.rfq_sent):
            raise UserError('You may not delete a canvass sheet that has been requested for quotation.')

        # Return Purchase Request Lines to waiting state
        self.mapped('line_ids').mapped('request_line_ids').action_waiting()

        return super(PeecCanvassSheet, self).unlink()

    def action_confirm(self):
        sequence_obj = self.env['ir.sequence']
        for rec in self:
            rec.write({
                'name': sequence_obj.sudo().next_by_code('peec.canvass.sheet'),
                'state': 'confirm'
            })

    def action_rfq(self):
        if self.filtered(lambda x: not x.vendor_ids):
            raise UserError("No vendors have been selected for quotation.")

        PurchaseOrder = self.env['purchase.order']
        for rec in self:
            # Build RFQ Lines
            rfq_lines = []
            for line in rec.line_ids:
                rfq_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'product_qty': line.product_qty,
                    'product_uom': line.uom_id.id,
                    'price_unit': 0,
                    'cs_line_id': line.id,
                    'date_planned': fields.Date.context_today(self)
                }))
            for vendor in rec.vendor_ids:
                if not vendor.deliver_to_id:
                    raise ValidationError(_('Vendor: %s requires a value for Deliver To.') % (vendor.vendor_id.display_name,))
                PurchaseOrder.create({
                    'canvass_id': rec.id,
                    'partner_id': vendor.vendor_id.id,
                    'picking_type_id': vendor.deliver_to_id.id,
                    'payment_term_id': vendor.payment_term_id.id,
                    'order_line': rfq_lines,
                    'origin': rec.name,
                })

        self.write({
            'state': 'rfq',
            'rfq_sent': True
        })

    def retrieve_rfq_values(self):
        for rec in self:
            i = 0
            for vendor in rec.vendor_ids:
                index = _NUMBERS[i]
                i += 1
                rfq = rec.purchase_ids.filtered(lambda p: p.partner_id.id == vendor.vendor_id.id)
                for line in rec.line_ids:
                    # Get CS Line in PO
                    rfq_line = rfq.order_line.filtered(lambda r: r.cs_line_id == line)
                    write_vals = {
                        'vendor_price_%s' % (index,): rfq_line.price_unit,
                        'vendor_qty_%s' % (index,): rfq_line.product_qty,
                        'tax_%s_ids' % (index,): rfq_line.taxes_id.ids,
                        'schedule_date_%s' % (index,): rfq_line.date_planned
                    }
                    line.write(write_vals)

    def action_bid(self):
        # Map RFQ Bids to CS
        for rec in self:
            if rec.state != 'rfq':
                raise ValidationError(_('The canvass sheet state already changed prior to your action. '
                                        'Please refresh record.'))
            rec.retrieve_rfq_values()
        self.write({'state': 'bid'})

    def action_approval(self):
        self.write({'state': 'approval'})

    def action_cancel(self):
        self.write({'state': 'cancel'})
        # Return Purchase Request to Waiting and remove reference to canvass sheet
        for rec in self:
            rec.line_ids.mapped('request_line_ids').write({
                'cs_id': False,
                'cs_line_id': False,
                'state': 'waiting'
            })

            # Cancel RFQs and/or POs
            for rfq in rec.purchase_ids:
                if rfq.state in ['draft', 'sent', 'to_approve']:
                    rfq.button_cancel()

    def action_reject(self, reject_reason):
        self.write({
            'state': 'reject',
            'reject_reason': reject_reason
        })

    def action_approve(self):
        self.ensure_one()

        pos = self.finalize_po()
        self.write({'state': 'done'})

        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Orders',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {},
            'domain': [('id', 'in', pos.ids)],
        }

    def finalize_po(self):
        final_pos = self.env['purchase.order']
        for rec in self:
            if rec.state != 'approval':
                raise ValidationError(_('The canvass sheet state already changed prior to your action. '
                                        'Please refresh record.'))
            i = 0

            for vendor in rec.vendor_ids:
                index = _NUMBERS[i]
                i += 1
                awarded_qty = 0
                rfq = rec.purchase_ids.filtered(lambda p: p.partner_id.id == vendor.vendor_id.id)
                for line in rec.line_ids:
                    # Get CS Line in PO
                    rfq_line = rfq.order_line.filtered(lambda r: r.cs_line_id == line)
                    awarded_qty += getattr(line, 'awarded_qty_%s' % (index,), 0)
                    write_vals = {
                        'product_qty': getattr(line, 'awarded_qty_%s' % (index,), 0),
                    }
                    rfq_line.write(write_vals)

                if awarded_qty == 0:
                    # None was awarded to this vendor, so cancel this PO
                    rfq.button_cancel()
                else:
                    rfq.button_confirm()
                    final_pos += rfq
        return final_pos

    def generate_po(self):
        self.ensure_one()
        i = 0
        line_ids = self.line_ids
        dt_now = fields.Datetime.now()
        pol_obj = self.env['purchase.order.line']
        po_ids = []

        for vendor_id in self.vendor_ids:
            index = _NUMBERS[i]
            request_line_ids = line_ids.mapped('request_line_ids')
            pr_names = set(request_line_ids.mapped('request_id').mapped('name'))
            # transition purchase request lines to purchase order state
            request_line_ids.action_po()

            if sum(line_ids.mapped("awarded_qty_%s" % index)) > 0:
                # Create PO record
                vals = {
                    'partner_id': vendor_id.id,
                    'date_order': dt_now,
                    'origin': ", ".join(pr_names)
                }
                po_id = self.env['purchase.order'].create(vals).id
                po_ids.append(po_id)

                # Create PO Lines
                for line_id in line_ids:
                    awarded_qty = getattr(line_id, "awarded_qty_%s" % index)
                    if awarded_qty > 0:
                        pol_id = pol_obj.create({
                            'order_id': po_id,
                            'product_id': line_id.product_id.id,
                            'name': line_id.name,
                            'product_qty': getattr(line_id, "awarded_qty_%s" % index),
                            'product_uom': line_id.uom_id.id,
                            'price_unit': getattr(line_id, "vendor_price_%s" % index),
                            'date_planned': getattr(line_id, "schedule_date_%s" % index),
                            'taxes_id': [(6, 0, getattr(line_id, "tax_%s_ids" % index).ids)],
                            'cs_line_id': line_id.id,
                        })

            i += 1
        return po_ids

    def action_reject_wizard(self):
        self.ensure_one()
        return {
            'name': 'Reject Canvass Sheet',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'peec.canvass.sheet.reject',
            'view_id': self.env.ref('tf_peec_purchase.peec_canvass_sheet_reject_form_view').id,
            'context': {'default_canvass_id': self.id},
            'type': 'ir.actions.act_window',
            'target': 'new'
        }

    def action_view_po(self):
        return {
            'name': 'Purchase Orders',
            'view_mode': 'tree,form',
            'res_model': 'purchase.order',
            'domain': [('id', 'in', self.line_ids.mapped('po_line_ids').mapped('order_id').ids)],
            'views': [(self.env.ref('tf_peec_purchase.peec_purchase_order_view_tree_readonly').id, 'tree'),
                      (False, 'form')],
            'type': 'ir.actions.act_window',
            'target': 'current'
        }

    def view_canvass_sheet(self):
        if not self.line_ids:
            raise models.except_orm(('Matrix Error!'), ('No Canvass Sheet Line records to be viewed.'))

        return {
            'name': "%s Matrix" % self.name,
            'view_mode': 'form',
            'view_id': self.env.ref('tf_peec_purchase.peec_canvass_sheet_matrix_view_form').id,
            'res_model': 'peec.canvass.sheet',
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(PeecCanvassSheet, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                            submenu=submenu)
        matrix_view_id = self.env.ref('tf_peec_purchase.peec_canvass_sheet_matrix_view_form').id
        if view_id != matrix_view_id:
            return res

        canvass_id = self.env['peec.canvass.sheet'].browse(self.env.context.get('active_id'))
        doc = etree.XML(res['arch'])
        res['arch'] = etree.tostring(doc)

        o2m_fields = res['fields']['line_ids']['views']['tree']['fields']
        doc = etree.XML(res['fields']['line_ids']['views']['tree']['arch'])

        i = 0
        for vendor_id in canvass_id.vendor_ids:
            index = _NUMBERS[i]
            i += 1
            for field in doc.xpath("//field"):
                if field.attrib['name'] == 'schedule_date_%s' % index:
                    field.set('invisible', '0')
                    field.set('required', '1')
                    field.set('string', vendor_id.vendor_id.display_name + ': Scheduled Date')
                    setup_modifiers(field, o2m_fields[field.attrib['name']])
                elif field.attrib['name'] == 'tax_%s_ids' % index:
                    field.set('invisible', '0')
                    field.set('string', vendor_id.vendor_id.display_name + ': Taxes')
                    setup_modifiers(field, o2m_fields[field.attrib['name']])
                elif field.attrib['name'] == 'vendor_qty_%s' % index:
                    field.set('invisible', '0')
                    field.set('string', vendor_id.vendor_id.display_name + ': Vendor Qty')
                    setup_modifiers(field, o2m_fields[field.attrib['name']])
                elif field.attrib['name'] == 'vendor_price_%s' % index:
                    field.set('invisible', '0')
                    field.set('required', '1')
                    field.set('string', vendor_id.vendor_id.display_name + ': Vendor Price')
                    setup_modifiers(field, o2m_fields[field.attrib['name']])
                elif field.attrib['name'] == 'awarded_qty_%s' % index:
                    field.set('invisible', '0')
                    field.set('required', '1')
                    field.set('string', vendor_id.vendor_id.display_name + ': Awarded Qty')
                    setup_modifiers(field, o2m_fields[field.attrib['name']])
                elif field.attrib['name'] == 'subtotal_%s' % index:
                    field.set('invisible', '0')
                    field.set('required', '1')
                    field.set('string', vendor_id.vendor_id.display_name + ': Subtotal')
                    setup_modifiers(field, o2m_fields[field.attrib['name']])

        # Remove Edit when Canvass Sheet state is 'Approved' onwards.
        if canvass_id.state in ['approval', 'done', 'cancel', 'reject']:
            for tree in doc.xpath("//" + view_type):
                tree.attrib['editable'] = 'false'

        res['fields']['line_ids']['views']['tree']['arch'] = etree.tostring(doc)

        return res


class PeecCanvassSheetVendor(models.Model):
    _name = "peec.canvass.sheet.vendor"
    _description = "Canvass Sheet Vendor"

    canvass_id = fields.Many2one('peec.canvass.sheet', "Canvass Sheet", ondelete='cascade',
                                 help="Indicates the parent canvass sheet record.", required=True)
    vendor_id = fields.Many2one('res.partner', "Vendor", help="Indicates the preferred vendor of the product being "
                                                              "canvassed, if applicable.")
    deliver_to_id = fields.Many2one('stock.picking.type', "Deliver To",
                                    help="Indicates the picking type of the incoming products")
    payment_term_id = fields.Many2one('account.payment.term', "Payment Terms",
                                      help="Indicates the payment term of the purchase order to be created for "
                                           "the vendor")
    remarks = fields.Char("Remarks", help="Indicate any remarks you want to include as part of information on the "
                                          "vendor")


class PeecCanvassSheetLine(models.Model):
    _name = "peec.canvass.sheet.line"
    _description = "Canvass Sheet Lines"

    canvass_id = fields.Many2one('peec.canvass.sheet', "Canvass Sheet", ondelete='cascade',
                                 help="Indicates the parent canvass sheet record.", required=True)
    product_id = fields.Many2one('product.product', "Product", required=True,
                                 help="Indicates the product being canvassed, if product record is already available "
                                      "in the system")
    responsible_id = fields.Many2one(related='canvass_id.responsible_id')
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    uom_id = fields.Many2one('uom.uom', string='UoM', required=True,
                             domain="[('category_id', '=', product_uom_category_id)]")
    currency_id = fields.Many2one(related='canvass_id.currency_id')
    lpv_id = fields.Many2one('res.partner', "LPV", copy=False,
                             help="Indicates the last known purchase vendor of the product")
    name = fields.Char("Description", required=True,
                       help="Indicates the description of the product being canvassed.")
    product_qty = fields.Float(string='Quantity', digits='Product Unit of Measure', required=True,
                               help="Indicates the quantity of the product being canvassed.")
    lpp = fields.Monetary("LPP", help="Indicates the last known purchase price of the product", copy=False)
    lpd = fields.Datetime("LPD", copy=False,
                          help="Indicates the last known purchase date of the product.")
    request_line_ids = fields.One2many('peec.purchase.request.line', 'cs_line_id', "Source Purchase Request Lines")
    vendor_domain_ids = fields.Many2many(string="Vendor Domain", related="canvass_id.vendor_domain_ids")
    po_line_ids = fields.One2many('purchase.order.line', 'cs_line_id', "Purchase Order References")

    # Canvass Sheet Matrix Fields
    schedule_date_one = fields.Date('Schedule Date 1', copy=False)
    schedule_date_two = fields.Date('Schedule Date 2', copy=False)
    schedule_date_three = fields.Date('Schedule Date 3', copy=False)
    schedule_date_four = fields.Date('Schedule Date 4', copy=False)
    schedule_date_five = fields.Date('Schedule Date 5', copy=False)
    tax_one_ids = fields.Many2many('account.tax', 'cs_tax_one_rel', 'tax_id', 'cs_id', string='Taxes',
                                   domain=['|', ('active', '=', False), ('active', '=', True)])
    tax_two_ids = fields.Many2many('account.tax', 'cs_tax_two_rel', 'tax_id', 'cs_id', string='Taxes',
                                   domain=['|', ('active', '=', False), ('active', '=', True)])
    tax_three_ids = fields.Many2many('account.tax', 'cs_tax_three_rel', 'tax_id', 'cs_id', string='Taxes',
                                     domain=['|', ('active', '=', False), ('active', '=', True)])
    tax_four_ids = fields.Many2many('account.tax', 'cs_tax_four_rel', 'tax_id', 'cs_id', string='Taxes',
                                    domain=['|', ('active', '=', False), ('active', '=', True)])
    tax_five_ids = fields.Many2many('account.tax', 'cs_tax_five_rel', 'tax_id', 'cs_id', string='Taxes',
                                    domain=['|', ('active', '=', False), ('active', '=', True)])
    vendor_qty_one = fields.Float('Vendor Qty. 1', copy=False)
    vendor_qty_two = fields.Float('Vendor Qty. 2', copy=False)
    vendor_qty_three = fields.Float('Vendor Qty. 3', copy=False)
    vendor_qty_four = fields.Float('Vendor Qty. 4', copy=False)
    vendor_qty_five = fields.Float('Vendor Qty. 5', copy=False)
    vendor_price_one = fields.Monetary('Vendor Price 1', copy=False)
    vendor_price_two = fields.Monetary('Vendor Price 2', copy=False)
    vendor_price_three = fields.Monetary('Vendor Price 3', copy=False)
    vendor_price_four = fields.Monetary('Vendor Price 4', copy=False)
    vendor_price_five = fields.Monetary('Vendor Price 5', copy=False)
    awarded_qty_one = fields.Float('Quantity 1', copy=False)
    awarded_qty_two = fields.Float('Quantity 2', copy=False)
    awarded_qty_three = fields.Float('Quantity 3', copy=False)
    awarded_qty_four = fields.Float('Quantity 4', copy=False)
    awarded_qty_five = fields.Float('Quantity 5', copy=False)
    subtotal_one = fields.Float('Awarded Subtotal 1', compute='_get_total', store=True)
    subtotal_two = fields.Float('Awarded Subtotal 2', compute='_get_total', store=True)
    subtotal_three = fields.Float('Awarded Subtotal 3', compute='_get_total', store=True)
    subtotal_four = fields.Float('Awarded Subtotal 4', compute='_get_total', store=True)
    subtotal_five = fields.Float('Awarded Subtotal 5', compute='_get_total', store=True)

    @api.depends('vendor_price_one', 'vendor_price_two', 'vendor_price_three', 'vendor_price_four', 'vendor_price_five',
                 'awarded_qty_one', 'awarded_qty_two', 'awarded_qty_three', 'awarded_qty_four', 'awarded_qty_five')
    def _get_total(self):
        for rec in self:
            for i in _NUMBERS:
                setattr(rec, "subtotal_%s" % i,
                        getattr(rec, "vendor_price_%s" % i) * getattr(rec, "awarded_qty_%s" % i))

    @api.depends('unit_price_one', 'qty_one')
    def _get_total_one(self):
        for rec in self:
            rec.total_one = rec.unit_price_one * rec.qty_one
        return True

    @api.depends('unit_price_two', 'qty_two')
    def _get_total_two(self):
        for rec in self:
            rec.total_two = rec.unit_price_two * rec.qty_two
        return True

    @api.depends('unit_price_three', 'qty_three')
    def _get_total_three(self):
        for rec in self:
            rec.total_three = rec.unit_price_three * rec.qty_three
        return True

    @api.depends('unit_price_four', 'qty_four')
    def _get_total_four(self):
        for rec in self:
            rec.total_four = rec.unit_price_four * rec.qty_four
        return True

    @api.depends('unit_price_five', 'qty_five')
    def _get_total_five(self):
        for rec in self:
            rec.total_five = rec.unit_price_five * rec.qty_five
        return True

    def search_recent_po_line(self):
        line_id = self.env['purchase.order.line'].search([
            ('product_id', '=', self.product_id.id),
            ('order_id.state', 'in', ['purchase', 'done'])
        ], order='date_planned desc', limit=1)

        if line_id:
            self.update({
                'lpp': line_id.price_unit,
                'lpd': line_id.date_planned,
                'lpv_id': line_id.order_id.partner_id.id
            })

    @api.onchange('product_id')
    def onchange_product_id(self):
        product_id = self.product_id
        if product_id:
            name = product_id.display_name
            if product_id.description_purchase:
                name += '\n' + product_id.description_purchase

            self.search_recent_po_line()
            self.update({
                'name': name,
                'uom_id': product_id.uom_po_id or product_id.uom_id
            })


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
