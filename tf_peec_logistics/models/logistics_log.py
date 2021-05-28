# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Allen Guarnes <allen@taliform.com>
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
from odoo.exceptions import ValidationError


class LogTrip(models.Model):
    _name = 'logistics.log.trip'
    _description = 'Trip Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    name = fields.Char('Reference', default='New', copy=False, required=True, tracking=True, index=True)
    delivery_order_id = fields.Many2one('logistics.delivery.order', 'Delivery Order', required=True, index=True)
    delivery_unit_id = fields.Many2one('logistics.delivery.unit', 'Delivery Unit', required=True, index=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda s: s.env.company, index=True)
    origin_id = fields.Many2one('res.partner', 'Origin', index=True)
    destination_id = fields.Many2one('res.partner', 'Destination', index=True)
    is_inspection_done = fields.Boolean('Inspection Done', readonly=True)
    is_loaded = fields.Boolean('Loaded', readonly=True)
    target_sucf = fields.Float('Override Target SUCF')
    actual_sucf = fields.Float('Actual SUCF')
    departure_date = fields.Datetime('Departure Date', index=True)
    arrival_date = fields.Datetime('Arrival Date', index=True)
    time_elapsed = fields.Float('Time Elapsed', compute='_compute_time_elapsed', store=True)
    distance_travelled = fields.Float('Distance Travelled (km)', compute='_compute_distance_travelled', store=True)
    expense_count = fields.Integer('No. of Trip Expenses', compute='_compute_expense_count')
    start_odometer_id = fields.Many2one('fleet.vehicle.odometer', 'Start Odometer')
    end_odometer_id = fields.Many2one('fleet.vehicle.odometer', 'End Odometer')
    manual_reason = fields.Text('Reason for Manual Date')
    state = fields.Selection([('in_progress', 'In Progress'), ('done', 'Done')], default='in_progress')
    journey_plan_id = fields.Many2one('logistics.journey.plan', 'Journey Plan', compute='_compute_journey_plan',
                                      store=True, index=True)
    target_sucf_id = fields.Many2one('logistics.target.sucf', 'Target SUCF', compute='_compute_target_sucf', store=True)
    maintenance_ids = fields.One2many('maintenance.request', 'trip_log_id', 'Maintenance Requests')

    def _stat_count_trip_log(self, model, ids):
        stat_data = self.env[model].read_group(
            [('trip_log_id', 'in', ids)], ['trip_log_id'], ['trip_log_id'])
        mapped_data = dict([(m['trip_log_id'][0], m['trip_log_id_count']) for m in stat_data])
        return mapped_data

    def _compute_expense_count(self):
        """ Count the number of trip expenses """
        mapped_data = self._stat_count_trip_log('logistics.log.expense', self.ids)
        for trip_log in self:
            trip_log.expense_count = mapped_data.get(trip_log.id, 0)

    @api.depends('departure_date', 'arrival_date')
    def _compute_time_elapsed(self):
        for trip_log in self:
            if trip_log.departure_date and trip_log.arrival_date:
                start = fields.Datetime.from_string(trip_log.departure_date)
                end = fields.Datetime.from_string(trip_log.arrival_date)
                diff = end - start
                # trip_log.time_elapsed = (end - start).seconds / 60.0 / 60.0
                trip_log.time_elapsed = float(diff.days) * 24 + (float(diff.seconds) / 3600)
            else:
                trip_log.time_elapsed = 0

    @api.depends('start_odometer_id', 'end_odometer_id', 'start_odometer_id.value', 'end_odometer_id.value')
    def _compute_distance_travelled(self):
        for trip_log in self:
            if trip_log.start_odometer_id and trip_log.end_odometer_id:
                if trip_log.end_odometer_id.value > trip_log.start_odometer_id.value:
                    trip_log.distance_travelled = trip_log.end_odometer_id.value - trip_log.start_odometer_id.value
                else:
                    trip_log.distance_travelled = trip_log.end_odometer_id.value
            else:
                trip_log.distance_travelled = 0

    @api.depends('origin_id', 'destination_id')
    def _compute_journey_plan(self):
        for trip_log in self:
            journey_plan = self.env['logistics.journey.plan'].search([
                ('origin_id', '=', trip_log.origin_id.id),
                ('destination_id', '=', trip_log.destination_id.id)
            ], limit=1)
            if journey_plan:
                trip_log.journey_plan_id = journey_plan
            else:
                trip_log.journey_plan_id = False

    @api.depends('origin_id', 'destination_id')
    def _compute_target_sucf(self):
        for trip_log in self:
            target_sucf = self.env['logistics.target.sucf'].search([
                ('origin_id', '=', trip_log.origin_id.id),
                ('destination_id', '=', trip_log.destination_id.id)
            ], limit=1)
            if target_sucf:
                trip_log.target_sucf_id = target_sucf
                trip_log.target_sucf = target_sucf.target
            else:
                trip_log.target_sucf_id = False

    @api.onchange('delivery_order_id')
    def _onchange_delivery_order_id(self):
        for trip_log in self:
            if trip_log.delivery_order_id:
                trip_log.delivery_unit_id = trip_log.delivery_order_id.delivery_unit_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Assign sequence
            if vals.get('name', _('New')) == _('New'):
                IrSequence = self.env['ir.sequence']
                seq_date = None
                print(vals)
                if vals.get('departure_date', False):
                    seq_date = fields.Datetime.context_timestamp(self,
                                                                 fields.Datetime.to_datetime(vals['departure_date']))
                if 'company_id' in vals:
                    vals['name'] = IrSequence.with_context(force_company=vals['company_id']).next_by_code(
                        self._name, sequence_date=seq_date) or _('New')
                else:
                    vals['name'] = IrSequence.next_by_code(self._name, sequence_date=seq_date) or _('New')

        result = super(LogTrip, self).create(vals_list)
        return result

    def action_view_trip_expenses(self):
        self.ensure_one()
        action = self.env.ref('tf_peec_logistics.action_logistics_log_expense').read()[0]
        action['context'] = {'default_trip_log_id': self.id}
        action['domain'] = [('trip_log_id', '=', self.id)]
        return action


class LogExpense(models.Model):
    _name = 'logistics.log.expense'
    _description = 'Trip Expense'

    trip_log_id = fields.Many2one('logistics.log.trip', 'Trip Log', index=True)
    delivery_order_id = fields.Many2one('logistics.delivery.order', 'Delivery Order', index=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda s: s.env.company, index=True)
    product_id = fields.Many2one('product.product', 'Product', required=True, index=True)
    name = fields.Char('Description', required=True, index=True)
    expense_date = fields.Datetime('Expense Date', default=fields.Datetime.now, index=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary()
    is_billable = fields.Boolean('Bill to Customer')
    sale_line_id = fields.Many2one('sale.order.line', 'Sale Order Line', readonly=True)
    qty_invoiced = fields.Float(related='sale_line_id.qty_invoiced', store=True)

    @api.constrains('amount')
    def _check_amount(self):
        for trip_expense in self:
            currency = trip_expense.currency_id
            if currency.is_zero(trip_expense.amount):
                raise ValidationError(_('The amount of a trip expense cannot be 0.'))

    @api.constrains('expense_date')
    def _check_expense_date(self):
        for trip_expense in self:
            if trip_expense.trip_log_id.departure_date \
                    and trip_expense.expense_date < trip_expense.trip_log_id.departure_date:
                raise ValidationError(_('The expense date cannot be earlier than the trip log\'s departure date.'))

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for trip_expense in self:
            if trip_expense.product_id:
                trip_expense.name = trip_expense.product_id.name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Add new sales order line if expense is tagged as billable to customer
            trip_log_id = vals.get('trip_log_id', False)
            if vals.get('is_billable', False) and trip_log_id:
                trip_log = self.env['logistics.log.trip'].browse([trip_log_id])
                if trip_log.delivery_order_id.sale_id:
                    order_line = self.env['sale.order.line'].create({
                        'order_id': trip_log.delivery_order_id.sale_id.id,
                        'product_id': vals.get('product_id'),
                        'name': vals.get('name'),
                        'product_uom_qty': 1.0,
                        'price_unit': vals.get('amount')
                    })
                    vals['sale_line_id'] = order_line.id

        result = super(LogExpense, self).create(vals_list)
        return result

    def write(self, vals):
        for trip_expense in self:
            # Add new sales order line if expense is tagged as billable to customer
            if vals.get('is_billable', False) and not trip_expense.sale_line_id:
                if trip_expense.delivery_order_id.sale_id:
                    order_line = self.env['sale.order.line'].create({
                        'order_id': trip_expense.delivery_order_id.sale_id.id,
                        'product_id': vals.get('product_id') or trip_expense.product_id.id,
                        'name': vals.get('name') or trip_expense.name,
                        'product_uom_qty': 1.0,
                        'price_unit': vals.get('amount') or trip_expense.amount
                    })
                    vals['sale_line_id'] = order_line.id

            # Update sale line if there are changes
            if trip_expense.sale_line_id:
                if trip_expense.qty_invoiced == 0.0:
                    update_vals = {}
                    if 'amount' in vals:
                        update_vals['price_unit'] = vals.get('amount', 0)
                    if 'product_id' in vals:
                        update_vals['product_id'] = vals.get('product_id', False)
                    if 'name' in vals:
                        update_vals['name'] = vals.get('name', False)
                    trip_expense.sale_line_id.write(update_vals)
                else:
                    raise ValidationError(_('Expense has already been invoiced in a Sales Order '
                                            'and can no longer be removed or updated.'))

        result = super(LogExpense, self).write(vals)
        return result


class LogWeight(models.Model):
    _name = 'logistics.log.weight'
    _description = 'Weight Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'weighing_date desc'
    _check_company_auto = True

    name = fields.Char('Reference', default='New', copy=False, required=True, tracking=True, index=True)
    delivery_order_id = fields.Many2one('logistics.delivery.order', 'Delivery Order', required=True, tracking=True)
    delivery_unit_id = fields.Many2one('logistics.delivery.unit', 'Delivery Unit', required=True, tracking=True)
    product_id = fields.Many2one(related='delivery_order_id.product_id', string='Loaded Product')
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda s: s.env.company, index=True)
    weighing_date = fields.Datetime('Weighing Date', default=fields.Datetime.now, required=True)
    checker_id = fields.Many2one('res.partner', 'Checker', tracking=True)
    checker_name = fields.Char('Checker Name')
    tare_weight = fields.Float('Tare Weight', tracking=True)
    gross_weight = fields.Float('Gross Weight', tracking=True)
    net_weight = fields.Float('Net Weight', tracking=True, compute='_compute_net_weight', stored=True)
    bags_qty = fields.Float('No. of Bags', tracking=True, compute='_compute_net_weight', stored=True)
    previous_gross_weight = fields.Float('Previous Gross Weight', tracking=True,
                                         compute='_compute_previous_gross_weight')
    expected_weight = fields.Float('Expected Weight', tracking=True)
    tolerance = fields.Float('Tolerance (+/-)',
                             help='Indicates the max difference between Net Weight and Expected Weight')
    is_tolerance_exceeded = fields.Boolean('Tolerance Exceeded', compute='_compute_is_tolerance_exceeded', store=True,
                                           copy=False)
    approver_id = fields.Many2one('hr.employee', 'Approved By', readonly=True, tracking=True, copy=False)
    load_state = fields.Selection([('empty', 'Empty'), ('loaded', 'Loaded')], 'Load State', default='empty',
                                  tracking=True)
    uom_id = fields.Many2one('uom.uom', 'Weight UoM', default=lambda s: s.env.company.logistics_cement_weight_uom_id,
                             readonly=True)
    bag_uom_id = fields.Many2one(related='delivery_order_id.uom_id', string='Bag UoM', store=True)
    state = fields.Selection([('normal', 'Normal'), ('approved', 'Approved'), ('rejected', 'Rejected')],
                             default='normal', tracking=True, copy=False)

    @api.constrains('gross_weight', 'tare_weight')
    def _check_gross_weight(self):
        for weight_log in self:
            if weight_log.gross_weight and weight_log.gross_weight < weight_log.tare_weight:
                raise ValidationError(_('Gross weight cannot be lower than the Tare weight. '
                                        'Please check the tare weight again.'))

    @api.depends('gross_weight', 'tare_weight')
    def _compute_net_weight(self):
        for weight_log in self:
            if weight_log.gross_weight and not weight_log.previous_gross_weight:
                net_weight = weight_log.gross_weight - weight_log.tare_weight
                weight_log.net_weight = net_weight
                weight_log.bags_qty = weight_log.uom_id._compute_quantity(net_weight, weight_log.bag_uom_id)

                # Weight needs to be converted to bags
                weight_log.bags_qty = weight_log.uom_id._compute_quantity(net_weight, weight_log.bag_uom_id)
            elif weight_log.load_state == 'empty' and weight_log.previous_gross_weight and weight_log.tare_weight:
                weight_log.net_weight = 0
                unloaded_weight = weight_log.previous_gross_weight - weight_log.tare_weight
                weight_log.bags_qty = weight_log.uom_id._compute_quantity(unloaded_weight, weight_log.bag_uom_id)
            elif weight_log.load_state == 'loaded' and weight_log.previous_gross_weight and weight_log.gross_weight:
                weight_log.net_weight = 0
                unloaded_weight = weight_log.previous_gross_weight - weight_log.gross_weight
                weight_log.bags_qty = weight_log.uom_id._compute_quantity(unloaded_weight, weight_log.bag_uom_id)
            else:
                weight_log.net_weight = 0
                weight_log.bags_qty = 0

    @api.depends('delivery_order_id')
    def _compute_previous_gross_weight(self):
        for weight_log in self:
            prev = weight_log.search([
                ('delivery_order_id', '=', weight_log.delivery_order_id.id),
                ('load_state', '=', 'loaded'),
                ('weighing_date', '<', weight_log.weighing_date)
            ], order='weighing_date desc', limit=1)
            if prev:
                weight_log.previous_gross_weight = prev.gross_weight
            else:
                weight_log.previous_gross_weight = 0

    @api.depends('tare_weight', 'expected_weight', 'tolerance', 'load_state')
    def _compute_is_tolerance_exceeded(self):
        for weight_log in self:
            if weight_log.load_state == 'empty' \
                    and weight_log.expected_weight > 0 \
                    and abs(weight_log.expected_weight - weight_log.tare_weight) > weight_log.tolerance:
                weight_log.is_tolerance_exceeded = True
            else:
                weight_log.is_tolerance_exceeded = False

    @api.onchange('delivery_order_id', 'load_state')
    def _onchange_delivery_order(self):
        for weight_log in self:
            if weight_log.delivery_order_id and weight_log.load_state == 'empty':
                last_weight_log = self.env['logistics.log.weight'].search([
                    ('delivery_order_id', '=', weight_log.delivery_order_id.id),
                    ('load_state', '=', 'empty')
                ], order='weighing_date desc', limit=1)
                if last_weight_log:
                    weight_log.expected_weight = last_weight_log.tare_weight
                else:
                    weight_log.expected_weight = 0

    @api.onchange('checker_id')
    def _onchange_checker_id(self):
        for weight_log in self:
            if weight_log.checker_id:
                weight_log.checker_name = weight_log.checker_id.display_name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Assign sequence
            if vals.get('name', _('New')) == _('New'):
                IrSequence = self.env['ir.sequence']
                seq_date = None
                if vals.get('weighing_date', False):
                    seq_date = fields.Datetime.context_timestamp(self,
                                                                 fields.Datetime.to_datetime(vals['weighing_date']))
                if 'company_id' in vals:
                    vals['name'] = IrSequence.with_context(force_company=vals['company_id']).next_by_code(
                        self._name, sequence_date=seq_date) or _('New')
                else:
                    vals['name'] = IrSequence.next_by_code(self._name, sequence_date=seq_date) or _('New')

        result = super(LogWeight, self).create(vals_list)

        for weight_log in result:
            delivery_order = weight_log.delivery_order_id
            if delivery_order:
                atw = delivery_order.atw_id
                if atw and not atw.weight_log_id and weight_log.load_state == 'loaded':
                    # Link loaded weight log to ATW
                    atw_vals = {
                        'weight_log_id': weight_log.id,
                    }
                    # Receive the actual amount of cement from Purchase Order
                    pickings = atw.purchase_id.picking_ids.filtered(lambda p: p.state != 'done')
                    if pickings:
                        picking = pickings[0]
                        move_line = picking.move_ids_without_package[0]
                        move_line.write({
                            'move_line_ids': [(0, 0, {
                                'location_id': move_line.location_id.id,
                                'location_dest_id': move_line.location_dest_id.id,
                                'qty_done': weight_log.bags_qty,
                                'picking_id': picking.id,
                                'product_id': weight_log.product_id.id,
                                'product_uom_id': weight_log.bag_uom_id.id,
                            })]
                        })
                        picking.with_context(cancel_backorder=False).action_done()
                        atw_vals['picking_id'] = picking.id
                    atw.write(atw_vals)

                # Updated boolean indicators in delivery order
                cp_load = self._context.get('cp_load', False)
                bp_unload = self._context.get('bp_unload', False)
                if cp_load:
                    delivery_order.write({'is_loaded_weighed': True})
                elif bp_unload:
                    delivery_order.write({'is_unloaded_weighed': True})

                    # Deliver the actual amount of cement from Sales Order
                    if delivery_order.sale_id:
                        pickings = delivery_order.sudo().sale_id.picking_ids.filtered(lambda p: p.state != 'done')
                        if pickings:
                            picking = pickings[0]

                            # Determine which weight to compare to, since there can be multiple batching plants
                            # to unload from, there can be instances where you're comparing weights from a previous
                            # loaded weight log
                            # if weight_log.load_state == 'empty':
                            #     current_weight = weight_log.tare_weight
                            # else:
                            #     current_weight = weight_log.gross_weight
                            #
                            # unloaded_qty = weight_log.previous_gross_weight - current_weight
                            # unloaded_qty_in_bags = weight_log.uom_id._compute_quantity(
                            #     unloaded_qty,
                            #     weight_log.bag_uom_id
                            # )

                            move_line = picking.move_ids_without_package[0]
                            move_line.write({
                                'move_line_ids': [(0, 0, {
                                    'location_id': move_line.location_id.id,
                                    'location_dest_id': move_line.location_dest_id.id,
                                    'qty_done': weight_log.bags_qty,
                                    'picking_id': picking.id,
                                    'product_id': weight_log.product_id.id,
                                    'product_uom_id': weight_log.bag_uom_id.id,
                                })]
                            })
                            picking.with_context(cancel_backorder=False).action_done()

                            # Add Picking to DO
                            delivery_order.write({
                                'picking_out_id': picking.id,
                                'delivered_qty': delivery_order.delivered_qty + weight_log.bags_qty
                            })

                            # Update Sale Order to Next Allocation if applicable
                            if delivery_order.next_sale_id:
                                for allocation in delivery_order.allocation_ids:
                                    if allocation.sale_id == delivery_order.sale_id:
                                        allocation.write({
                                            'state': 'done',
                                            'picking_id': picking.id,
                                            'delivered_qty': weight_log.bags_qty
                                        })
                                        break
                                pending_allocations = delivery_order.allocation_ids.filtered(
                                    lambda a: a.state == 'pending')
                                if pending_allocations:
                                    next = pending_allocations[0]
                                    delivery_order.write({
                                        'sale_id': next.sale_id.id,
                                        'batching_plant_id': next.batching_plant_id.id,
                                        'uom_id': next.uom_id.id,
                                        'requested_load': next.requested_load,
                                    })
        return result

    def _action_approve_reject(self, state):
        errors = []
        current_employee = self.env.user.employee_id
        if not current_employee:
            errors.append(_('Current user does not have an employee record. '
                            'Only employees are allowed to approve weight logs.'))
        for weight_log in self:
            if weight_log.load_state == 'empty':
                errors.append(_('Empty weight logs do not require any approval. Please refresh record.'))
            if weight_log.state != 'normal':
                errors.append(_('Weight Log has already been approved or rejected prior to your action. '
                                'Please refresh record.'))
            if not errors:
                weight_log.approver_id = current_employee
                weight_log.state = state
            else:
                raise ValidationError('\n'.join(errors))

    def action_approve(self):
        self._action_approve_reject('approved')

    def action_reject(self):
        self._action_approve_reject('rejected')


class LogLoading(models.Model):
    _name = 'logistics.log.loading'
    _description = 'Loading Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    name = fields.Char('Reference', default='New', copy=False, required=True, tracking=True, index=True)
    delivery_order_id = fields.Many2one('logistics.delivery.order', 'Delivery Order', required=True)
    delivery_unit_id = fields.Many2one('logistics.delivery.unit', 'Delivery Unit', required=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda s: s.env.company, index=True)
    location_id = fields.Many2one('res.partner', 'Loading Location')
    start_date = fields.Datetime('Start Date')
    end_date = fields.Datetime('End Date')
    time_elapsed = fields.Float('Time Elapsed', compute='_compute_time_elapsed', store=True)

    @api.depends('start_date', 'end_date')
    def _compute_time_elapsed(self):
        for loading_log in self:
            if loading_log.start_date and loading_log.end_date:
                start = fields.Datetime.from_string(loading_log.start_date)
                end = fields.Datetime.from_string(loading_log.end_date)
                diff = end - start
                loading_log.time_elapsed = float(diff.days) * 24 + (float(diff.seconds) / 3600)
            else:
                loading_log.time_elapsed = 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Assign sequence
            if vals.get('name', _('New')) == _('New'):
                IrSequence = self.env['ir.sequence']
                seq_date = None
                if vals.get('start_date', False):
                    seq_date = fields.Datetime.context_timestamp(self,
                                                                 fields.Datetime.to_datetime(vals['start_date']))
                if 'company_id' in vals:
                    vals['name'] = IrSequence.with_context(force_company=vals['company_id']).next_by_code(
                        self._name, sequence_date=seq_date) or _('New')
                else:
                    vals['name'] = IrSequence.next_by_code(self._name, sequence_date=seq_date) or _('New')

        result = super(LogLoading, self).create(vals_list)
        return result


class LogUnloading(models.Model):
    _name = 'logistics.log.unloading'
    _description = 'Unloading Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    name = fields.Char('Reference', default='New', copy=False, required=True, tracking=True, index=True)
    delivery_order_id = fields.Many2one('logistics.delivery.order', 'Delivery Order', required=True)
    delivery_unit_id = fields.Many2one('logistics.delivery.unit', 'Delivery Unit', required=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda s: s.env.company, index=True)
    location_id = fields.Many2one('res.partner', 'Loading Location')
    start_date = fields.Datetime('Start Date')
    end_date = fields.Datetime('End Date')
    time_elapsed = fields.Float('Time Elapsed', compute='_compute_time_elapsed', store=True)

    @api.depends('start_date', 'end_date')
    def _compute_time_elapsed(self):
        for loading_log in self:
            if loading_log.start_date and loading_log.end_date:
                start = fields.Datetime.from_string(loading_log.start_date)
                end = fields.Datetime.from_string(loading_log.end_date)
                diff = end - start
                loading_log.time_elapsed = float(diff.days) * 24 + (float(diff.seconds) / 3600)
            else:
                loading_log.time_elapsed = 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Assign sequence
            if vals.get('name', _('New')) == _('New'):
                IrSequence = self.env['ir.sequence']
                seq_date = None
                if vals.get('start_date', False):
                    seq_date = fields.Datetime.context_timestamp(self,
                                                                 fields.Datetime.to_datetime(vals['start_date']))
                if 'company_id' in vals:
                    vals['name'] = IrSequence.with_context(force_company=vals['company_id']).next_by_code(
                        self._name, sequence_date=seq_date) or _('New')
                else:
                    vals['name'] = IrSequence.next_by_code(self._name, sequence_date=seq_date) or _('New')

        result = super(LogUnloading, self).create(vals_list)
        return result
