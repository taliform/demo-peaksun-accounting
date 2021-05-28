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
from odoo import fields, models, api, _
from odoo.exceptions import UserError

_SALE_TYPE = [('standard', 'Standard'),
                  ('cement', 'Cement'),
                  ('hauling', 'Hauling')]


class SaleDeliveryOrder(models.TransientModel):
    _name = 'sale.logistics.delivery.order'
    _description = "Sales Delivery Order (Logistics)"

    @api.constrains('no_delivery_order', 'no_delivery_order_qty')
    def _check_values(self):
        for rec in self:
            if rec.no_delivery_order <= 0.0:
                raise UserError(_("The indicated no. of delivery order should be positive."))
            if rec.no_delivery_order_qty <= 0.0:
                raise UserError(_("The indicated quantity per delivery order should be positive."))

    no_delivery_order = fields.Integer('No. of Delivery Orders', default=1)
    no_delivery_order_qty = fields.Float('Quantity per Delivery Order', default="1000")
    # so_id = fields.Many2one('sale.order', help="Indicates the sale order record that will shoulder the "
    #                                            "remaining/excess quantity")
    do_created = fields.Integer("No. of Delivery Orders created")
    uom_id = fields.Many2one('uom.uom', "Cement Unit of Measure", default=lambda s: s.env.company.logistics_cement_bag_uom_id)
    batching_plant_id = fields.Many2one('res.partner', 'Batching Plant',
                                        domain=[('is_batching_plant', '=', True)],
                                        help="Indicates the customer’s batching plant to deliver to")
    cement_plant_id = fields.Many2one('res.partner', 'Cement Plant',
                                      domain=[('is_cement_plant', '=', True)],
                                      help="Indicates the cement plant to withdraw cement from")
    product_id = fields.Many2one('product.product', 'Cement Product')
    sale_type = fields.Selection(_SALE_TYPE, string='Sale Type', default='standard', track_visibility='onchange',
                                 help="Indicates the type of sales order, which will be used to differentiate which "
                                      "form view to display")

    def prepare_delivery_order(self):
        active_ids = self._context.get('active_ids')
        for rec in self:
            sale_order = self.env['sale.order']

            for active_id in active_ids:
                so_id = sale_order.browse(active_id)
                if so_id.sale_type in ('cement', 'hauling'):
                    # Block creation if Credit Status does not allow
                    if so_id.partner_id.sale_warn == 'block' and 'overdue' in so_id.partner_id.sale_warn_msg:
                        message = "%s has existing invoices that are overdue." % so_id.partner_id.name
                        raise UserError(_(message))

                    if so_id.for_do_logistics:
                        # Create Delivery Order
                        # Created from form view
                        total_product_balance = sum(so_id.order_line.filtered(lambda l: not l.is_offhire and
                                                                              not l.is_do_trip_exp).mapped('balance'))
                        # Error message if the balance is less than the requested load qty
                        if total_product_balance < rec.no_delivery_order_qty and so_id.sale_type == 'cement':
                            if self._context.get('from_sale_order_form', False):
                                raise UserError(_('The product quantity balance (%d) is less than the requested quantity '
                                                  'per delivery order. Change the quantity per delivery order to '
                                                  'proceed.')
                                                % total_product_balance)
                            else:
                                raise UserError(_('The product quantity balance (%d) from %s is less than the requested '
                                                  'quantity per delivery order. Change the quantity per delivery order '
                                                  'to proceed.')
                                                % (total_product_balance, so_id.name))

                        else:
                            order_line_ids = so_id.order_line.filtered(lambda l: not l.is_offhire and not l.is_do_trip_exp
                                                                       and l.balance > 0.0)

                            # Items sold must be the same product
                            if all(x.product_id == order_line_ids[0].product_id for x in order_line_ids) and \
                               all(x.product_uom == order_line_ids[0].product_uom for x in order_line_ids):

                                if rec.do_created < rec.no_delivery_order:
                                    rec.create_do_details(so_id)
                            else:
                                if self._context.get('from_sale_order_form', False):
                                    raise UserError(_('Items to deliver should have the same product and unit of '
                                                      'measure.'))
                                else:
                                    raise UserError(_('Items to deliver from %s should have the same product and unit '
                                                      'of measure.') % so_id.name)
                    else:
                        raise UserError(_('%s has an existing delivery order.') % so_id.name)
                else:
                    raise UserError(_('You cannot merge delivery orders with Standard or Hauling sale type.'))

    def create_do_details(self, so_id):
        for rec in self:
            product_id = product_uom = False
            do_ctr = do_to_create = 1
            line_do_allocation = self.env['sale.order.line.do.allocation']
            product_id_temp = so_id.order_line.filtered(lambda l: not l.is_offhire and
                                                        not l.is_do_trip_exp).product_id

            so_line_ids = so_id.order_line.filtered(lambda l: not l.is_offhire and not l.is_do_trip_exp and
                                                    l.balance > 0.0)
            total_product_balance = sum(so_line_ids.filtered(lambda l: not l.is_offhire and
                                                             not l.is_do_trip_exp).mapped('balance'))

            if self._context.get('from_sale_order_form', False):
                do_to_create = rec.no_delivery_order

            total_req_qty = do_to_create * rec.no_delivery_order_qty

            if total_product_balance < total_req_qty and so_id.sale_type == 'cement':
                if self._context.get('from_sale_order_form', False):
                    raise UserError(_("The total requested load (%d) exceeds the total product quantity(%d).")
                                    % (total_req_qty, total_product_balance))
                else:
                    raise UserError(_("The total requested load (%d) exceeds the total product quantity(%d) "
                                      "of %s.") % (total_req_qty, total_product_balance, so_id.name))

            if product_id_temp:
                if so_id.sale_type == 'cement':
                    product_id = product_id_temp[0]
                    product_uom = rec.uom_id
                elif so_id.sale_type == 'hauling':
                    # Product should not be required if Hauling Sale Type
                    product_id = self.product_id
                    product_uom = rec.uom_id

            # If Cement / CIF or Hauling / Time Chartered
            if (so_id.sale_type == 'cement' and so_id.sale_operation == 'cif') or \
               (so_id.sale_type == 'hauling' and so_id.hauling_type == 'time'):

                while do_ctr <= do_to_create:
                    remaining_load = rec.no_delivery_order_qty
                    load_added = line_balance = 0.0
                    do_id = rec.create_delivery_order(so_id, remaining_load, product_id, product_uom)
                    rec.do_created += 1

                    for line_id in so_line_ids.sorted(lambda l: l.sequence):
                        line_id._get_do_details()

                        if load_added < rec.no_delivery_order_qty:
                            if not line_balance:
                                line_balance = line_id.balance

                            if line_balance <= remaining_load:
                                load_added += line_balance
                                alloc_qty = line_balance
                                line_balance -= line_balance
                                remaining_load -= alloc_qty
                            else:
                                load_added += remaining_load
                                alloc_qty = remaining_load
                                line_balance -= remaining_load
                                remaining_load -= remaining_load

                            # Create Line DO allocation
                            if alloc_qty > 0.0:
                                do_alloc_vals = {'so_line_id': line_id.id,
                                                 'delivery_order_id': do_id.id,
                                                 'alloc_qty': alloc_qty}
                                line_do_allocation.create(do_alloc_vals)

                            load_added += line_balance
                            line_id.delivery_order_ids += do_id
                    do_ctr += 1

            # If Hauling / Voyage
            # Create DO per line
            if so_id.sale_type == 'hauling' and so_id.hauling_type == 'voyage':
                requested_load = rec.no_delivery_order_qty
                if rec.no_delivery_order > len(so_line_ids.filtered(lambda s: not s.delivery_order_id)):
                    raise UserError(_("The number of Delivery Orders you are trying to create exceed the "
                                      "number of pending DO/SO Lines available in the Sales Order."))
                while do_ctr <= do_to_create:
                    for line_id in so_line_ids.sorted(lambda l: l.sequence):
                        line_id._get_do_details()
                        if line_id.balance < requested_load and so_id.sale_type == 'cement':
                            if self._context.get('from_sale_order_form', False):
                                raise UserError(_("The product quantity balance for order line sequence no. %d is less "
                                                  "than the requested quantity per delivery order.") % line_id.sequence)
                            else:
                                raise UserError(_("The product quantity balance for order line sequence no. %d (%s) is less "
                                                  "than the requested quantity per delivery order.")
                                                % line_id.sequence, so_id.name)
                        else:
                            if rec.do_created < rec.no_delivery_order:
                                do_id = rec.create_delivery_order(so_id, requested_load, product_id, product_uom)
                                line_id.delivery_order_id = do_id
                                line_id.delivery_order_ids += do_id
                                alloc_qty = requested_load

                                if line_id.balance > requested_load:
                                    alloc_qty = requested_load
                                elif line_id.balance <= requested_load:
                                    alloc_qty = line_id.balance

                                if alloc_qty > 0.0:
                                    do_alloc_vals = {'so_line_id': line_id.id,
                                                     'delivery_order_id': do_id.id,
                                                     'alloc_qty': alloc_qty}
                                    line_do_allocation.create(do_alloc_vals)
                                do_ctr += 1
                                rec.do_created += 1

    def create_delivery_order(self, so_id, req_load_qty, product_id, product_uom):
        cement_plant = so_id.cement_plant_id
        if not cement_plant:
            cement_plant = self.cement_plant_id

        batching_plant = so_id.batching_plant_id
        if not batching_plant:
            batching_plant = self.batching_plant_id

        delivery_order = self.env['logistics.delivery.order']
        do_vals = {'sale_id': so_id.id,
                   'product_id': product_id and product_id.id or False,
                   'uom_id': product_uom and product_uom.id,
                   'cement_plant_id': cement_plant.id,
                   'batching_plant_id': batching_plant.id or False,
                   'requested_load': req_load_qty,
                   'schedule_date': fields.Datetime.now(),
                   }
        do_id = delivery_order.create(do_vals)
        return do_id


class SaleMergeDeliveryOrder(models.TransientModel):
    _name = 'sale.merge.logistics.delivery.order'
    _description = "Sales Merge Delivery Order (Logistics)"

    @api.constrains('no_delivery_order', 'no_delivery_order_qty')
    def _check_values(self):
        for rec in self:
            if rec.no_delivery_order <= 0.0:
                raise UserError(_("The indicated no. of delivery order should be positive."))
            if rec.no_delivery_order_qty <= 0.0:
                raise UserError(_("The indicated quantity per delivery order should be positive."))

    no_delivery_order = fields.Integer('No. of Delivery Orders', default="1")
    no_delivery_order_qty = fields.Float('Quantity per Delivery Order', default="1000")
    excess_qty = fields.Float('Excess Quantity', help="Indicates the excess quantity based on the requested "
                                                      "quantity per delivery order")
    so_id = fields.Many2one('sale.order', help="Indicates the sale order record that will shoulder the "
                                               "remaining/excess quantity")
    so_ids = fields.Many2many('sale.order', string='Domain SO')
    with_excess = fields.Boolean(help="Indicates if there's an excess quantity")
    do_created = fields.Integer("No. of Delivery Orders created")

    @api.onchange('no_delivery_order', 'no_delivery_order_qty', 'so_ids')
    def onchange_delivery_order(self):
        active_ids = self._context.get('active_ids')
        so_ids = self.env['sale.order']

        for active_id in active_ids:
            so_id = self.env['sale.order'].browse(active_id)

            # Block creation if Credit Status does not allow
            if so_id.partner_id.sale_warn == 'block' and 'overdue' in so_id.partner_id.sale_warn_msg:
                message = "%s has existing invoices that are overdue." % so_id.partner_id.name
                raise UserError(_(message))
            else:
                if so_id.for_do_logistics:
                    so_ids += so_id

                    order_line_ids = self.env['sale.order.line']
                    for line_id in so_ids.order_line.filtered(lambda l: not l.is_offhire and not l.is_do_trip_exp
                                                                        and l.balance > 0.0):
                        order_line_ids += line_id
                else:
                    raise UserError(_('%s has an existing delivery order.') % so_id.name)

        # Validate selected sales orders
        self.with_context(from_onchange=True).validate_so_ids(so_ids, order_line_ids)

    def prepare_merge_delivery_order(self):
        active_ids = self._context.get('active_ids')
        for rec in self:
            so_ids = self.env['sale.order']

            for active_id in active_ids:
                so_id = self.env['sale.order'].browse(active_id)

                # Block creation if Credit Status does not allow
                if so_id.partner_id.sale_warn == 'block' and 'overdue' in so_id.partner_id.sale_warn_msg:
                    message = self.partner_id.sale_warn_msg
                    raise UserError(_(message))
                else:
                    if so_id.for_do_logistics:
                        so_ids += so_id
                    else:
                        raise UserError(_('%s has an existing delivery order.') % so_id.name)

            self.so_ids = so_ids

            # Create Delivery Order
            order_line_ids = self.env['sale.order.line']
            for line_id in so_ids.order_line.filtered(lambda l: not l.is_offhire and not l.is_do_trip_exp
                                                      and l.balance > 0.0):
                order_line_ids += line_id

            total_product_balance = sum(order_line_ids.filtered(lambda l: not l.is_offhire and
                                                                not l.is_do_trip_exp).mapped('balance'))
            # Error message if the balance is less than the requested load qty
            if total_product_balance < rec.no_delivery_order_qty:
                raise UserError(_('The total product quantity (%d) is less than the requested quantity '
                                  'per delivery order. Change the quantity per delivery order to '
                                  'proceed.')
                                % total_product_balance)

            else:
                if rec.do_created < rec.no_delivery_order:
                    for order_line_id in order_line_ids:
                        order_line_id.do_merge_alloc = order_line_id.balance

                        if rec.with_excess and order_line_id.order_id == rec.so_id:
                            total_product_qty = sum(so_ids.order_line.filtered(lambda l: not l.is_offhire and
                                                                                not l.is_do_trip_exp).mapped('balance'))
                            if rec.no_delivery_order == 1:
                                if total_product_qty > rec.no_delivery_order_qty:
                                    rec.excess_qty = total_product_qty - rec.no_delivery_order_qty
                                    order_line_id.do_merge_alloc = order_line_id.balance - rec.excess_qty
                            else:
                                total_req_qty = self.no_delivery_order * self.no_delivery_order_qty
                                if total_product_qty > total_req_qty:
                                    rec.excess_qty = total_product_qty - total_req_qty
                                    order_line_id.do_merge_alloc = order_line_id.balance - rec.excess_qty

                    rec.create_merge_do_details(so_ids, order_line_ids)

    def validate_so_ids(self, so_ids, so_line_ids):
        if so_ids:
            # Check if all are Cement sale type
            if not all(x.sale_type == 'cement' for x in so_ids):
                raise UserError(_('You cannot merge delivery order with Standard or Hauling sale type.'))
            # Check if the same Cement Plant
            if not all(x.cement_plant_id == so_ids[0].cement_plant_id for x in so_ids):
                raise UserError(_('You cannot merge delivery order with different Cement Plant.'))
            # Check if the same product
            if not all(x.product_id == so_line_ids[0].product_id for x in so_line_ids) or \
               not all(x.product_uom == so_line_ids[0].product_uom for x in so_line_ids):
                raise UserError(_('You cannot merge delivery order with different products.'))

            # Check if there will be an excess quantity
            total_product_qty = sum(so_line_ids.filtered(lambda l: not l.is_offhire and
                                                                   not l.is_do_trip_exp).mapped('balance'))
            if self.no_delivery_order == 1:
                # Check if there's an excess quantity
                if total_product_qty > self.no_delivery_order_qty:
                    self.so_ids = so_ids
                    self.excess_qty = total_product_qty - self.no_delivery_order_qty
                    self.with_excess = True
                else:
                    self.so_ids = self.with_excess = False
                    self.excess_qty = 0.0
            else:
                total_req_qty = self.no_delivery_order * self.no_delivery_order_qty
                if total_product_qty > total_req_qty:
                    self.so_ids = so_ids
                    self.excess_qty = total_product_qty - total_req_qty
                    self.with_excess = True
                else:
                    self.so_ids = self.with_excess = False
                    self.excess_qty = 0.0

    def create_merge_do_details(self, so_ids, so_line_ids):
        for rec in self:
            if so_line_ids:
                product_id = product_uom = False
                line_do_allocation = self.env['sale.order.line.do.allocation']
                delivery_order_allocation = self.env['logistics.delivery.order.allocation']
                product_id_temp = so_line_ids[0].filtered(lambda l: not l.is_offhire and
                                                                    not l.is_do_trip_exp).product_id

                total_product_balance = sum(so_line_ids.filtered(lambda l: not l.is_offhire and
                                                                           not l.is_do_trip_exp).mapped('balance'))

                do_ctr = 1
                do_to_create = rec.no_delivery_order
                total_req_qty = do_to_create * rec.no_delivery_order

                if total_product_balance < total_req_qty:
                    raise UserError(_("The total requested load (%d) exceeds the total product quantity(%d).")
                                        % (total_req_qty, total_product_balance))

                if product_id_temp:
                    product_id = product_id_temp[0]
                    product_uom = product_id_temp[0].uom_id

                # If Cement / CIF or Hauling / Time Chartered
                if so_ids[0].sale_type == 'cement' and so_ids[0].sale_operation == 'cif':
                    while do_ctr <= do_to_create:
                        remaining_load = rec.no_delivery_order_qty
                        load_added = line_alloc = 0.0
                        do_id = rec.create_merge_delivery_order(so_ids, so_line_ids, remaining_load, product_id, product_uom)
                        do_line_ids = self.env['sale.order.line']
                        rec.do_created += 1
                        for line_id in so_line_ids.filtered(lambda l: l.do_merge_alloc > 0.0).sorted(lambda l: l.sequence):
                            line_id._get_do_details()

                            if load_added < rec.no_delivery_order_qty:
                                if not line_alloc:
                                    line_alloc = line_id.do_merge_alloc

                                if line_alloc <= remaining_load:
                                    load_added += line_alloc
                                    alloc_qty = line_alloc
                                    line_alloc -= line_alloc
                                    remaining_load -= alloc_qty
                                else:
                                    # Update
                                    line_id.do_merge_alloc = remaining_load

                                    load_added += remaining_load
                                    alloc_qty = remaining_load
                                    line_alloc -= remaining_load
                                    remaining_load -= remaining_load

                                # Create Line DO allocation
                                if alloc_qty > 0.0:
                                    do_alloc_vals = {'so_line_id': line_id.id,
                                                     'delivery_order_id': do_id.id,
                                                     'alloc_qty': alloc_qty}
                                    line_do_allocation.create(do_alloc_vals)

                                line_id.delivery_order_ids += do_id
                                do_line_ids += line_id

                                # Create allocations
                                alloc_vals = {'sale_id': line_id.order_id.id,
                                              'delivery_order_id': do_id.id,
                                              'requested_load': alloc_qty,
                                              'uom_id': product_uom.id,
                                              'batching_plant_id': line_id.order_id.batching_plant_id.id
                                              }
                                delivery_order_allocation.create(alloc_vals)

                                do_id.sale_id = do_id.allocation_ids[0].sale_id
                                do_id.batching_plant_id = do_id.allocation_ids[0].batching_plant_id
                                line_id.do_merge_alloc = 0.0

                        do_ctr += 1

    def create_merge_delivery_order(self, so_ids, so_line_ids, req_load_qty, product_id, product_uom):
        delivery_order = self.env['logistics.delivery.order']
        do_vals = {'product_id': product_id.id,
                   'uom_id': product_uom.id,
                   'cement_plant_id': so_ids[0].cement_plant_id and so_ids[0].cement_plant_id.id,
                   'requested_load': req_load_qty,
                   'schedule_date': fields.Datetime.now(),
                   'is_multiple_sale': True,
                   }
        do_id = delivery_order.create(do_vals)
        return do_id