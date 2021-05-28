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
from odoo import api, fields, models, exceptions, _
from odoo.exceptions import ValidationError, UserError


class SalesOrder(models.Model):
    _inherit = 'sale.order'

    _SALE_TYPE = [('standard', 'Standard'),
                  ('cement', 'Cement'),
                  ('hauling', 'Hauling')]

    _OPERATIONS = [('cif', 'CIF'),
                   ('fob', 'FOB'),
                   ('dropship', 'Drop Ship')]

    _HAULING_TYPE = [('time', 'Time Chartered'),
                     ('voyage', 'Voyage Chartered')]

    def _check_delivery_order(self):
        """
        :return: True if all order line quantities are for delivery (logistics)
        :return: False if all order line quantities are not yet for delivery (logistics)
        """
        for rec in self:
            if rec.sale_type in ('cement', 'hauling'):
                rec.for_do_logistics = False
                if rec.order_line:
                    total_balance = sum(rec.order_line.mapped('balance'))
                    if total_balance > 0.0:
                        rec.for_do_logistics = True

    def _get_do_ids(self):
        """
        Get the Delivery Orders (Logistics) related to the  sales order.
        """
        for rec in self:
            rec.delivery_order_ids = False
            rec.delivery_order_count = 0.0
            if rec.sale_type in ('cement', 'hauling'):
                rec.delivery_order_ids = False
                rec.delivery_order_count = 0.0
                if rec.order_line:
                    for line_id in rec.order_line:
                        for do_id in line_id.delivery_order_ids:
                            rec.delivery_order_ids += do_id

                    if rec.delivery_order_ids:
                        rec.delivery_order_count = len(rec.delivery_order_ids)

    @api.depends('offhire_ids')
    def _get_offhire_ids(self):
        for rec in self:
            rec.offhire_count = 0.0
            if rec.sale_type in ('cement', 'hauling') and rec.offhire_ids:
                rec.offhire_count = len(rec.offhire_ids)

    def _get_delivery_units(self):
        """
        Get the Delivery Units (Logistics) related to the related to the  sales order.
        """
        for rec in self:
            rec.no_reserved_units = 0.0
            rec.reserved_unit_ids = False
            if rec.sale_type in ('cement', 'hauling'):
                if rec.delivery_order_ids:
                    for do_id in rec.delivery_order_ids:
                        unit_ids = self.env['logistics.delivery.unit'].search([('delivery_order_id', '=', do_id.id)])
                        if unit_ids:
                            rec.reserved_unit_ids = unit_ids.ids
                    rec.no_reserved_units = len(rec.reserved_unit_ids)

    @api.depends('state', 'date_order')
    def _get_order_date(self):
        for rec in self:
            rec.do_so_order_date = fields.Date.today()
            if rec.date_order:
                rec.do_so_order_date = rec.date_order.date()

    sales_agreement_id = fields.Many2one('sale.agreement', 'Sales Agreement', track_visibility='onchange', copy=False,
                                         help="Indicates the Sales Agreement the Sales Order was created from, "
                                         "if applicable")
    rate_table_id = fields.Many2one('sale.rate', 'Rate Table', track_visibility='onchange', copy=False,
                                    help="Indicates the Rate Table used as basis for computations")
    project_id = fields.Many2one('res.partner.project', 'Project', track_visibility='onchange',
                                 help="Indicates the project the Sales Order is allocating to")
    batching_plant_id = fields.Many2one('res.partner', 'Batching Plant', track_visibility='onchange',
                                        domain=[('is_batching_plant', '=', True)],
                                        help="Indicates the customer’s batching plant to deliver to")
    cement_plant_id = fields.Many2one('res.partner', 'Cement Plant', track_visibility='onchange',
                                      domain=[('is_cement_plant', '=', True)],
                                      help="Indicates the cement plant to withdraw cement from")
    sale_type = fields.Selection(_SALE_TYPE, string='Sale Type', default='standard',  track_visibility='onchange',
                                 help="Indicates the type of sales order, which will be used to differentiate which "
                                 "form view to display")
    sale_operation = fields.Selection(_OPERATIONS, string='Operations', default='cif', track_visibility='onchange',
                                      help="Indicates the operation of Sales")
    hauling_type = fields.Selection(_HAULING_TYPE, string='Hauling Type', default='time', track_visibility='onchange',
                                    help="Indicates the hauling type")
    state = fields.Selection(selection_add=[('closed', 'Closed')])
    trade_name = fields.Char(related='partner_id.trade_name', store=True, help="Indicates the Customer’s Trade Name")
    batching_plant_city = fields.Char(related='batching_plant_id.city', store=True, help="Indicates the batching "
                                                                                         "plant’s city")
    batching_plant_state = fields.Many2one(related='batching_plant_id.state_id', store=True, help="Indicates the "
                                           "batching plant’s state")
    no_reserved_units = fields.Integer(compute='_get_delivery_units', string='No. of Reserved Units',
                                       track_visibility='onchange', copy=False,
                                       help="Indicates the number of trucks reserved by the customer")
    reserved_unit_ids = fields.Many2many('logistics.delivery.unit', compute='_get_delivery_units',
                                         string='Reserved Units', copy=False,
                                         help="Indicates the designated delivery units" )
    mnt_privilege = fields.Float('Maintenance Privilege', track_visibility='onchange', copy=False,
                                 help="Indicates the number of hours to use as maintenance privilege, "
                                      "which will be consumed when offhire records are recognized in the Sales Order")
    for_do_logistics = fields.Boolean(compute='_check_delivery_order', string='For Delivery Order (Logistics)',
                                      copy=False, help="Indicates if the Sales Orders is still for "
                                                       "delivery (logistics')")
    delivery_order_ids = fields.Many2many('logistics.delivery.order', compute='_get_do_ids', string='Delivery Orders',
                                          copy=False, help="Applicable for Voyage Chartered. Indicates the "
                                                           "corresponding Delivery Order for the Sales Order line.")
    delivery_order_count = fields.Integer(compute='_get_do_ids', string='Delivery Orders', copy=False)
    offhire_ids = fields.One2many('sale.offhire', 'so_id', 'Sale Offhire', copy=False)
    so_line_offhire_ids = fields.Many2many('sale.offhire', string='Added to Sale Order Line Offhire', copy=False)
    offhire_count = fields.Integer(compute='_get_offhire_ids', string='Offhire', copy=False)
    do_merge = fields.Boolean('Merged DO', copy=False, help="Merged Delivery Order from other Sales Orders")
    do_so_order_date = fields.Date(compute='_get_order_date', string='DO SO Order Date', store=True)
    delivery_order_ids = fields.One2many('logistics.delivery.order', 'sale_id', 'Delivery Orders')
    delivery_order_count = fields.Integer('No. of Delivery Orders', compute='_compute_delivery_order_count')
    atw_ids = fields.One2many('logistics.atw', 'sale_id', 'ATWs')
    atw_count = fields.Integer('No. of ATWs', compute='_compute_atw_count')
    amount_balance = fields.Float('Balance', compute='_compute_balance', store=True)
    amount_qty = fields.Float('Order Quantity', compute='_compute_balance', store=True)
    amount_invoiced = fields.Float('Invoiced', compute='_compute_balance', store=True)
    amount_intransit = fields.Float('In Transit', compute='_compute_balance', store=True)

    @api.depends('order_line.balance', 'order_line.qty_invoiced', 'order_line.in_transit', 'order_line.product_uom_qty')
    def _compute_balance(self):
        for rec in self:
            rec.amount_qty = sum(rec.order_line.mapped('product_uom_qty'))
            rec.amount_invoiced = sum(rec.order_line.mapped('qty_invoiced'))
            rec.amount_intransit = sum(rec.order_line.mapped('in_transit'))
            rec.amount_balance = sum(rec.order_line.mapped('balance'))

    def _compute_delivery_order_count(self):
        """ Count the number of delivery orders """
        stat_data = self.env['logistics.delivery.order'].read_group(
            [('sale_id', 'in', self.ids)], ['sale_id'], ['sale_id'])
        mapped_data = dict([(m['sale_id'][0], m['sale_id_count']) for m in stat_data])
        for sale_order in self:
            sale_order.delivery_order_count = mapped_data.get(sale_order.id, 0)

    def _compute_atw_count(self):
        """ Count the number of atws """
        stat_data = self.env['logistics.atw'].read_group(
            [('sale_id', 'in', self.ids)], ['sale_id'], ['sale_id'])
        mapped_data = dict([(m['sale_id'][0], m['sale_id_count']) for m in stat_data])
        for sale_order in self:
            sale_order.atw_count = mapped_data.get(sale_order.id, 0)

    @api.model
    def create(self, vals):
        res = super(SalesOrder, self).create(vals)
        if res.sales_agreement_id:
            res.message_post_with_view('mail.message_origin_link', values={'self': res,
                                                                           'origin': res.sales_agreement_id},
                                       subtype_id=self.env['ir.model.data'].xmlid_to_res_id('mail.mt_note'))
        # Get the Rate Table in the order line
        if res.order_line and res.sale_type in ('cement', 'hauling'):
            res.rate_table_id = res.order_line[0].rate_table_id
        return res

    def write(self, vals):
        res = super(SalesOrder, self).write(vals)
        if vals.get('sales_agreement_id', False):
            self.message_post_with_view('mail.message_origin_link', values={'self': self,
                                                                            'origin': self.sales_agreement_id,
                                                                            'edit': True},
                                        subtype_id=self.env['ir.model.data'].xmlid_to_res_id('mail.mt_note'))

        # Get the Rate Table in the order line
        try:
            if vals.get('order_line', False):
                if self.order_line and self.sale_type in ('cement', 'hauling'):
                    self.rate_table_id = self.order_line[0].rate_table_id
        except: pass
        return res

    def action_confirm(self):
        """
        Blocks confirmation if Credit Status does not allow
        """
        res = super(SalesOrder, self).action_confirm()
        for rec in self:
            if rec.partner_id.sale_warn == 'block' and 'overdue' in rec.partner_id.sale_warn_msg:
                message = rec.partner_id.sale_warn_msg
                raise UserError(_(message))
        return res

    @api.onchange('project_id')
    def onchange_project_id(self):
        if not self.project_id:
            return
        if self.project_id and self.project_id.batching_plant_ids:
            self.batching_plant_id = self.project_id.batching_plant_ids[0].id

    @api.onchange('sales_agreement_id')
    def onchange_sales_agreement_id(self):
        if not self.sales_agreement_id:
            return

        agreement_id = self.sales_agreement_id
        project_id = batching_plant_id = origin = False
        if self.partner_id:
            partner = self.partner_id
        else:
            partner = agreement_id.partner_id

        FiscalPosition = self.env['account.fiscal.position']
        fpos = FiscalPosition.with_context(force_company=self.company_id.id).get_fiscal_position(partner.id)
        fpos = FiscalPosition.browse(fpos)

        if partner.project_ids:
            project_id = partner.project_ids[0].id
            if partner.project_ids[0].batching_plant_ids:
                batching_plant_id = partner.project_ids[0].batching_plant_ids[0].id

        if not self.origin or agreement_id.name not in self.origin.split(', '):
            if self.origin:
                if agreement_id.name:
                    origin = self.origin + ', ' + agreement_id.name
            else:
                origin = agreement_id.name

        addr = partner.address_get(['delivery', 'invoice'])
        partner_user = partner.user_id or partner.commercial_partner_id.user_id

        user_id = partner_user.id
        if not self.env.context.get('not_self_saleperson'):
            user_id = user_id or self.env.uid
        if user_id and self.user_id.id != user_id:
            user_id = user_id

        if not self.env.context.get('not_self_saleperson') or not self.team_id:
            self.team_id = self.env['crm.team'].with_context(default_team_id=self.partner_id.team_id.id)._get_default_team_id(domain=['|', ('company_id', '=', self.company_id.id), ('company_id', '=', False)],
                                                     user_id=user_id)

        self.partner_id = partner.id
        self.fiscal_position_id = fpos.id
        self.company_id = agreement_id.company_id.id
        self.currency_id = agreement_id.currency_id.id
        self.sale_tax_ids = partner.sale_tax_ids.ids or []
        self.pricelist_id = partner.property_product_pricelist and partner.property_product_pricelist.id or False
        self.payment_term_id = partner.property_payment_term_id and partner.property_payment_term_id.id or False
        self.partner_invoice_id = addr['invoice']
        self.partner_shipping_id = addr['delivery']
        self.project_id = project_id
        self.batching_plant_id = batching_plant_id
        self.note = agreement_id.description
        self.date_order = fields.Datetime.now()
        self.origin = origin

        # Create Order Line
        order_lines = []
        for line_id in agreement_id.line_ids:
            product_lang = line_id.product_id.with_context(
                lang=partner.lang,
                partner_id=partner.id
            )
            name = product_lang.display_name
            product_qty = line_id.product_qty
            price_unit = line_id.price_unit

            order_line_values = line_id._prepare_order_line(
                name=name, product_qty=product_qty, price_unit=price_unit, tax_id=False)
            order_lines.append((0, 0, order_line_values))

        self.order_line = order_lines

    def create_so_line_offhire_ids(self, offhire_ids, product_qty, price_unit):
        """
        :param offhire_ids: From Add to Sales Order wizard (Sale Offhire)
        :return: order line for offhire
        """
        if not self.so_line_offhire_ids:
            return

        # Create Order Line
        order_lines = []
        product_id = self.env['product.product'].search([('name', '=', 'Offhire')])
        if product_id:
            name = product_id[0].display_name + ' / ' + str(fields.Date.today())
            product_qty = product_qty
            price_unit = price_unit

            order_line_values = self.so_line_offhire_ids[0]._prepare_order_line(
                name=name, product_qty=product_qty, price_unit=price_unit, tax_id=False)
            order_lines.append((0, 0, order_line_values))

            if order_lines:
                self.order_line = order_lines

                # Assign SO Line to Offhire record
                for offhire_id in offhire_ids:
                    offhire_id.so_line_id = self.order_line[-1]

        else:
            raise UserError(_('There is no product configured for Offhire.'))

    def update_offhire(self):
        """
        Updates the unrecognized offhire records and add as negative Sales Order line.
        """
        for rec in self:
            so_line_offhire = self.env['sale.line.offhire']
            offhire_ids = self.env['sale.offhire'].search([('so_id', '=', rec.id),
                                                           ('added', '=', False),
                                                           ('waive', '=', False)])
            if not offhire_ids:
                raise UserError(_('There is no offhire record to be added.'))
            else:
                so_line_offhire.with_context(active_ids=offhire_ids.ids).add_to_so_line()

    def action_close(self):
        """
        Check if all order lines are already invoiced and delivered to close the sales order.
        """

        for rec in self:
            not_del_ids = False
            # Check the delivery orders (stock picking)
            if rec.sale_type == 'standard':
                picking_ids = self.env['stock.picking'].search([('sale_id', '=', rec.id)])
                not_del_ids = picking_ids.filtered(lambda l: l.state not in ('done', 'cancel'))
                if not_del_ids:
                    raise UserError(_("There are pending delivery orders (Inventory). Transfer the delivery orders "
                                      "before closing this sales order."))

            elif rec.sale_type in ('cement', 'hauling'):
                if not rec.for_do_logistics and rec.delivery_order_ids:
                    not_del_ids = rec.delivery_order_ids.filtered(lambda l: l.state != 'closed')
                    if not_del_ids:
                        raise UserError(_("There are pending delivery orders (Delivery Orders). Process the "
                                          "delivery orders in Logistics before closing this sales order."))

            # Check invoice status if fully invoiced
            if rec.invoice_status != 'invoiced':
                raise UserError(_("There are pending order lines to be invoiced. Create the invoices before "
                                  "closing this sales order."))
            else:
                rec.state = 'closed'

    def action_view_delivery_orders(self):
        """
        This function returns an action that display existing delivery orders (logistics) based on the sales order ids.
        """
        action = self.env.ref('tf_peec_logistics.action_logistics_delivery_order').read()[0]

        delivery_order_ids = self.mapped('delivery_order_ids')
        if len(delivery_order_ids) >= 1:
            action['domain'] = action['domain'] = [('id', 'in', delivery_order_ids.ids)]
        action['context'] = dict(self._context, default_partner_id=self.partner_id.id)
        return action

    def action_view_offhire(self):
        """
        This function returns an action that display existing offhire records.
        """
        action = self.env.ref('tf_peec_sales.peec_sale_offhire_action_view').read()[0]

        offhire_ids = self.mapped('offhire_ids')
        if len(offhire_ids) >= 1:
            action['domain'] = action['domain'] = [('id', 'in', offhire_ids.ids),
                                                   ('so_id', '=', self.id),
                                                    ('added', '=', False)]
        else:
            action['domain'] = action['domain'] = [('so_id', '=', self.id)]
        action['context'] = dict(self._context, default_so_id=self.id, default_mnt_privilege=self.mnt_privilege)
        return action

    def action_cancel(self):
        res = super(SalesOrder, self).action_cancel()
        for rec in self:
            if rec.state == 'closed':
                raise UserError(_('Unable to cancel sales order %s as some related records '
                                  'have already been done.') % rec.name)

            if rec.sale_type in ('cement', 'hauling'):
                if rec.delivery_order_ids:
                    raise UserError(_('Unable to cancel sales order %s as some related records '
                                      'have already been done.') % rec.name)
        return res

    def action_view_delivery_orders(self):
        action = self.env.ref('tf_peec_logistics.action_logistics_delivery_order').read()[0]
        action['domain'] = [('sale_id', 'in', self.ids)]
        return action

    def action_create_atw(self):
        ATW = self.env['logistics.atw']
        for sale_order in self:
            if sale_order.order_line:
                atw = ATW.create(
                    {
                        'sale_id': sale_order.id,
                        'cement_plant_id': sale_order.cement_plant_id.id,
                        'product_id': sale_order.order_line[0].product_id.id,
                        'quantity': sale_order.order_line[0].product_uom_qty,
                        'uom_id': sale_order.order_line[0].product_uom.id,
                    }
                )

    def action_view_atws(self):
        action = self.env.ref('tf_peec_logistics.action_logistics_atw').read()[0]
        action['domain'] = [('sale_id', 'in', self.ids)]
        return action


class SalesOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('total_distance', 'rate_id')
    def _compute_rate(self):
        """
        Computes the Logistics Rate
        """
        for line_id in self:
            if line_id.order_id.sale_type in ('cement', 'hauling'):
                line_id.cement_price = line_id.product_id.lst_price
                line_id.logistics_rate = 0.0
                line_id.suggested_price = 0.0
                if line_id.order_id.sale_type == 'cement' and line_id.order_id.sale_operation == 'cif':
                    if line_id.rate_table_id and line_id.total_distance and line_id.rate_id:
                        rt_id = line_id.rate_table_id
                        rt_id.km_comp = line_id.total_distance
                        rt_id.rate_id_comp = line_id.rate_id
                        computed_rate = rt_id.compute_rate()

                        if computed_rate:
                            line_id.logistics_rate = computed_rate['based_on_rate']

                        line_id.suggested_price = line_id.cement_price + line_id.logistics_rate
                        line_id.price_unit = line_id.suggested_price
            else:
                line_id.cement_price = line_id.product_id.lst_price
                line_id.logistics_rate = 0.0
                line_id.suggested_price = 0.0

    @api.depends('delivery_order_ids', 'delivery_order_ids.state', 'product_uom_qty',
                 'order_id.picking_ids', 'order_id.picking_ids.state', 'delivery_order_ids.allocation_ids',
                 'delivery_order_ids.allocation_ids.state', 'line_do_alloc_ids', 'line_do_alloc_ids.delivery_order_id')
    def _get_do_details(self):
        """
        Checks the quantity that are Scheduled and In Transit
        """
        for line_id in self:
            line_id.scheduled = line_id.in_transit = line_id.balance = 0.0
            do_ids_scheduled = do_ids_transit = do_ids_closed = 0.0
            order_id = line_id.order_id
            if order_id.sale_type in ('cement', 'hauling'):
                line_id.balance = line_id.product_uom_qty

            if line_id.delivery_order_ids and not line_id.is_offhire and not line_id.is_do_trip_exp:
                do_ids = line_id.delivery_order_ids
                do_alloc_ids = self.env['logistics.delivery.order.allocation'].search([('sale_id', '=', line_id.order_id.id)])
                if do_ids:
                    if order_id.sale_type == 'cement' and order_id.sale_operation == 'cif':
                        for sched_do_id in do_ids.filtered(lambda l: l.state in ('unassigned', 'assigned')):
                            if not sched_do_id.is_multiple_sale:
                                if line_id.product_uom != sched_do_id.uom_id:
                                    converted_load = sched_do_id.uom_id._compute_quantity(sched_do_id.requested_load, line_id.product_uom)
                                    do_ids_scheduled += converted_load
                                else:
                                    do_ids_scheduled += sched_do_id.requested_load
                            else:
                                for alloc_id in do_alloc_ids:
                                    alloc_do_id = alloc_id.delivery_order_id
                                    if alloc_do_id.state in ('unassigned', 'assigned') and alloc_do_id in line_id.delivery_order_ids:
                                        if line_id.product_uom != sched_do_id.uom_id:
                                            converted_load = sched_do_id.uom_id._compute_quantity(sched_do_id.requested_load,
                                                                                 line_id.product_uom)
                                            do_ids_scheduled += converted_load
                                        else:
                                            do_ids_scheduled += alloc_id.requested_load

                        for transit_do_id in do_ids.filtered(lambda l: l.state not in ('unassigned', 'assigned', 'closed')):
                            if not transit_do_id.is_multiple_sale:
                                if line_id.product_uom != transit_do_id.uom_id:
                                    converted_load = transit_do_id.uom_id._compute_quantity(transit_do_id.requested_load, line_id.product_uom)
                                    do_ids_transit += converted_load
                                else:
                                    do_ids_transit += transit_do_id.requested_load
                            else:
                                for alloc_id in do_alloc_ids:
                                    alloc_do_id = alloc_id.delivery_order_id
                                    if alloc_do_id.state not in ('unassigned', 'assigned', 'closed') and alloc_do_id in line_id.delivery_order_ids:
                                        if line_id.product_uom != transit_do_id.uom_id:
                                            converted_load = transit_do_id.uom_id._compute_quantity(
                                                transit_do_id.requested_load, line_id.product_uom)
                                            do_ids_transit += converted_load
                                        else:
                                            do_ids_transit += alloc_id.requested_load

                        line_id.scheduled += do_ids_scheduled
                        line_id.in_transit += do_ids_transit
                        line_id.balance = line_id.product_uom_qty - (line_id.scheduled + line_id.in_transit + line_id.qty_delivered)

                    if order_id.sale_type == 'hauling' and order_id.hauling_type in ('time', 'voyage'):
                        for alloc_do_id in line_id.line_do_alloc_ids:
                            if alloc_do_id.delivery_order_id.state in ('unassigned', 'assigned'):
                                do_ids_scheduled += alloc_do_id.alloc_qty

                        for alloc_do_id in line_id.line_do_alloc_ids:
                            if alloc_do_id.delivery_order_id.state not in ('unassigned', 'assigned', 'closed'):
                                do_ids_transit += alloc_do_id.alloc_qty

                        for alloc_do_id in line_id.line_do_alloc_ids:
                            if alloc_do_id.delivery_order_id.state == 'closed':
                                do_ids_closed += alloc_do_id.alloc_qty

                        line_id.scheduled += do_ids_scheduled
                        line_id.in_transit += do_ids_transit
                        line_id.balance = line_id.product_uom_qty - (line_id.scheduled + line_id.in_transit + do_ids_closed)

    @api.constrains('total_distance')
    def _verify_values(self):
        for rec in self:
            if rec.total_distance and rec.total_distance < 0.0:
                raise ValidationError(_('The indicated total distance is invalid.'))

    delivery_order_id = fields.Many2one('logistics.delivery.order', 'Delivery Order', copy=False,
                                        help="Applicable for Voyage Chartered. Indicates the corresponding "
                                             "Delivery Order for the Sales Order line.")
    delivery_order_ids = fields.Many2many('logistics.delivery.order', string='Delivery Orders', copy=False,
                                          help="Applicable for Voyage Chartered. Indicates the corresponding "
                                               "Delivery Order for the Sales Order line.")
    vendor_dr_no = fields.Char(related='delivery_order_id.vendor_dr_no')
    rate_id = fields.Many2one('sale.rate.rate', 'Rate', help="Indicates the selected Rate (in percentage) where "
                                                             "choices are from the selected Rate Table")
    rate_table_id = fields.Many2one('sale.rate', 'Rate Table', copy=False, help="Indicates the Rate Table used as "
                                                                                "basis for computations")
    travel_route_ids = fields.Many2many('sale.location', copy=False, help="Indicates the assumed travel routes to get "
                                                                          "the value of Total Distance")
    scheduled = fields.Float(compute='_get_do_details', copy=False, store=True,
                             help="Indicates the current quantity of items that have already been scheduled "
                                  "for delivery")
    in_transit = fields.Float(compute='_get_do_details', copy=False, store=True,
                              help="Indicates the current quantity of items that are already in transit")
    balance = fields.Float(compute='_get_do_details', copy=False, store=True,
                           help="Indicates the current quantity of items left after deducting items that have already "
                                "been elivered, scheduled, or are in transit")
    no_bags = fields.Float(related='delivery_order_id.atw_id.bags_qty', string='No. of Bags',
                           help="Applicable for Voyage Chartered. Indicates the number of bags for the Delivery Order.")
    total_distance = fields.Float('Total Distance', copy=False, help="Indicates the Total Distance based on selected "
                                                                     "Travel Routes. Can be manually overwritten.")
    logistics_rate = fields.Monetary('Logistics Rate', compute='_compute_rate', readonly=True, store=True,
                                     help="Computed Logistics Rate based on the selected Rate Table, Rate percentage, "
                                          "and Total Distance.")
    cement_price = fields.Monetary('Cement Price', compute='_compute_rate', readonly=True, store=True, copy=False,
                                   help="The default sales price of the Cement Product")
    suggested_price = fields.Monetary('Suggested Price', compute='_compute_rate', readonly=True, store=True, copy=False,
                                      help="The suggested price of the Sales Order Line, based on Suggested Price "
                                           "= Logistics Rate + Cement Price")
    do_merge_alloc = fields.Float(help="Allocated qty if created from merged delivery order (current)", copy=False)
    is_offhire = fields.Boolean('Offhire', copy=False, help="Indicates if the line is Offhire")
    is_do_trip_exp = fields.Boolean('Trip Expense', copy=False, help="Indicates if the line is created "
                                                                     "from Trip Expense (Logistics)")
    line_do_alloc_ids = fields.One2many('sale.order.line.do.allocation', 'so_line_id', string='Allocated Qty in DO',
                                        copy=False, help="Allocated quantity in the delivery order")
    cement_plant_id = fields.Many2one(related='order_id.cement_plant_id', readonly=False, store=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super(SalesOrderLine, self).create(vals_list)
        for rec in records:
            # Limited to only 1 Sales Order Line
            if rec.order_id and rec.order_id.sale_type == 'cement':
                if len(rec.order_id.order_line) > 1:
                    raise UserError(_('Limited to only one sales order line for Cement sale type.'))

                if rec.price_unit <= 0.0:
                    raise UserError(_('You cannot confirm the sales quotation without price.'))

        return records

    @api.onchange('product_id')
    def product_id_change(self):
        """
        Reset Rate Table
        """
        res = super(SalesOrderLine, self).product_id_change()
        if self.order_id:
            if self.order_id.sale_type in ('cement', 'hauling'):
                self.rate_table_id = False
        return res

    @api.onchange('product_uom_qty')
    def onchange_product_uom_qty(self):
        """
        Reset Rate Table
        """
        if self.order_id:
            if self.order_id.sale_type in ('cement', 'hauling'):
                self.rate_table_id = False

    # Overwrite this function to stop price unit from changing if under SA
    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        sa = self.order_id.sales_agreement_id
        if sa:
            # Get price from the same product item in Sales Agreement
            for line in sa.line_ids:
                if line.product_id == self.product_id:
                    self.write({'price_unit': line.price_unit})
                    break
        else:
            super(SalesOrderLine, self).product_uom_change()

    @api.onchange('rate_table_id', 'product_id', 'travel_route_ids')
    def onchange_rate_table(self):
        """
        Updates the Unit Price based on the selected Rate Table
        """
        if self.rate_table_id:
            order_id = self.order_id
            if order_id.cement_plant_id and order_id.batching_plant_id:
                company_partner_id = self.env.company.partner_id
                cement_plant_id = order_id.cement_plant_id
                batching_plant_id = order_id.batching_plant_id

                if order_id.sale_type == 'hauling':
                    # Check Rate Table Lines that matches the Cement and Batching Plant
                    rt_line_id = self.env['sale.rate.line'].search([('cement_plant_id', '=', cement_plant_id.id),
                                                                    ('batching_plant_id', '=', batching_plant_id.id)])
                    if rt_line_id:
                        # Get the Rate and update the Unit Price and Rate Table
                        self.price_unit = rt_line_id.rate

                elif order_id.sale_type == 'cement' and order_id.sale_operation == 'cif':
                    # Check Sale Location that matches the Cement and Batching Plant for the Distance
                    company_partner_id = self.env.company.partner_id
                    travel_route_ids = self.env['sale.location']
                    # Set Default Travel Routes
                    # Company -> Cement Plant / Cement Plant -> Batching Plant
                    location_one = self.env['sale.location'].search([('origin_id', '=', company_partner_id.id),
                                                                     ('destination_id', '=', cement_plant_id.id)])

                    location_two = self.env['sale.location'].search([('origin_id', '=', cement_plant_id.id),
                                                                     ('destination_id', '=', batching_plant_id.id)])

                    travel_route_ids += location_one
                    travel_route_ids += location_two
                    self.travel_route_ids = travel_route_ids
                    if self.travel_route_ids:
                        self.total_distance = sum(self.travel_route_ids.mapped('distance'))

        else:
            self.travel_route_ids = False

    @api.onchange('cement_plant_id')
    def onchange_cement_plant_id(self):
        for rec in self:
            if rec.cement_plant_id and rec.order_id.sale_type == 'cement':
                return {'domain': {'product_id': [('cement_plant_ids', 'in', [rec.cement_plant_id.id])]}}


class SaleOrderLineDOAllocation(models.Model):
    _name = 'sale.order.line.do.allocation'
    _description = 'Sale Order Line - Delivery Order Allocation'
    _rec_name = 'so_line_id'

    so_line_id = fields.Many2one('sale.order.line', 'Sale Order Line', ondelete='cascade')
    delivery_order_id = fields.Many2one('logistics.delivery.order', 'Delivery Order', ondelete='cascade')
    alloc_qty = fields.Float('Allocated Quantity in DO')