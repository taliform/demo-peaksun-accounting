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
import werkzeug

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_STATES = [
    ('unassigned', 'Unassigned'),
    ('assigned', 'Assigned'),
    ('in_transit_cp', 'In Transit to CP'),
    ('cp', 'CP'),
    ('loading', 'Loading'),
    ('loaded', 'Loaded'),
    ('in_transit_bp', 'In Transit to BP'),
    ('bp', 'BP'),
    ('unloading', 'Unloading'),
    ('unloaded', 'Unloaded'),
    ('validation', 'Validation'),
    ('closed', 'Closed')
]


class DeliveryOrder(models.Model):
    _name = 'logistics.delivery.order'
    _description = 'Delivery Order'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _check_company_auto = True
    _order = 'schedule_date desc'

    name = fields.Char('Reference', states={'unassigned': [('readonly', False)]}, default='New', copy=False,
                       required=True, tracking=True, index=True)
    state = fields.Selection(_STATES, default='unassigned', required=True, tracking=True)
    order_date = fields.Datetime('Order Date', default=fields.Datetime.now, tracking=True, copy=False)
    schedule_date = fields.Datetime('Schedule Date', required=True, tracking=True, copy=False)
    delivery_unit_id = fields.Many2one('logistics.delivery.unit', 'Delivery Unit', readonly=True, tracking=True,
                                       copy=False)
    garage_id = fields.Many2one('res.partner', 'Garage', default=lambda s: s.env.company.logistics_default_origin,
                                required=True, tracking=True)
    cement_plant_id = fields.Many2one('res.partner', 'Cement Plant', required=True, tracking=True)
    batching_plant_id = fields.Many2one('res.partner', 'Batching Plant', tracking=True)
    journey_plan_id = fields.Many2one(related='trip_log_id.journey_plan_id', store=True)
    departure_date = fields.Datetime('Departure Date', tracking=True, copy=False)
    return_date = fields.Datetime('Return Date', tracking=True, copy=False)
    estimated_return_date = fields.Datetime('Estimated Return Time', tracking=True, copy=False)
    picking_id = fields.Many2one(related='atw_id.picking_id', string='Vendor Delivery Receipt', tracking=True, store=True)
    atw_id = fields.Many2one('logistics.atw', 'ATW', tracking=True, index=True, copy=False)
    vendor_dr_no = fields.Char(related='atw_id.vendor_dr_no', readonly=False, index=True, copy=False)
    product_id = fields.Many2one('product.product', 'Cement Product', required=True, tracking=True)
    uom_id = fields.Many2one('uom.uom', 'Cement Unit of Measure',
                             default=lambda s: s.env.company.logistics_cement_bag_uom_id, required=True)
    requested_load = fields.Float('Requested Load', required=True, tracking=True)
    document_ids = fields.One2many('logistics.delivery.document', 'delivery_order_id', 'Documents')
    validated_by = fields.Many2one('res.users', 'Validated By', tracking=True)
    remarks = fields.Text()
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda s: s.env.company, index=True)
    trip_count = fields.Integer('No. of Trip Logs', compute='_compute_trip_count')
    expense_count = fields.Integer('No. of Trip Expenses', compute='_compute_expense_count')
    weight_count = fields.Integer('No. of Weight Logs', compute='_compute_weight_count')
    loading_count = fields.Integer('No. of Loading Logs', compute='_compute_loading_count')
    unloading_count = fields.Integer('No. of Unloading Logs', compute='_compute_unloading_count')
    sale_id = fields.Many2one('sale.order', 'Sale Order', index=True)
    next_sale_id = fields.Many2one('sale.order', 'Next Sale Order')
    customer_id = fields.Many2one(related='sale_id.partner_id', string='Customer')
    purchase_id = fields.Many2one('purchase.order', related='atw_id.purchase_id', store=True)
    trip_log_id = fields.Many2one('logistics.log.trip', 'Current Trip Log', readonly=True, copy=False)
    trip_ids = fields.One2many('logistics.log.trip', 'delivery_order_id', 'Trip Logs')
    expense_ids = fields.One2many('logistics.log.expense', 'delivery_order_id', 'Trip Expenses')
    is_loaded_weighed = fields.Boolean('Is Cement Loaded Weighed?', copy=False)
    is_unloaded_weighed = fields.Boolean('Is Cement Unloaded Weighed?', copy=False)
    is_returning = fields.Boolean('Is Returning?', copy=False)
    is_multiple_sale = fields.Boolean('Is Multiple Sales Order?', copy=False)
    allocation_ids = fields.One2many('logistics.delivery.order.allocation', 'delivery_order_id', 'Allocations')
    maintenance_ids = fields.One2many('maintenance.request', 'delivery_order_id', 'Maintenance Requests')
    picking_out_id = fields.Many2one('stock.picking', 'Customer Delivery Receipt')
    delivered_qty = fields.Float('Delivered Quantity')
    received_qty = fields.Float(related='atw_id.bags_qty', string='Received Quantity')

    def _stat_count_delivery_order(self, model, ids):
        stat_data = self.env[model].read_group(
            [('delivery_order_id', 'in', ids)], ['delivery_order_id'], ['delivery_order_id'])
        mapped_data = dict([(m['delivery_order_id'][0], m['delivery_order_id_count']) for m in stat_data])
        return mapped_data

    def _compute_trip_count(self):
        """ Count the number of trip logs """
        mapped_data = self._stat_count_delivery_order('logistics.log.trip', self.ids)
        for delivery_order in self:
            delivery_order.trip_count = mapped_data.get(delivery_order.id, 0)

    def _compute_expense_count(self):
        """ Count the number of trip expenses """
        mapped_data = self._stat_count_delivery_order('logistics.log.expense', self.ids)
        for delivery_order in self:
            delivery_order.expense_count = mapped_data.get(delivery_order.id, 0)

    def _compute_weight_count(self):
        """ Count the number of weight logs """
        mapped_data = self._stat_count_delivery_order('logistics.log.weight', self.ids)
        for delivery_order in self:
            delivery_order.weight_count = mapped_data.get(delivery_order.id, 0)

    def _compute_loading_count(self):
        """ Count the number of loading logs """
        mapped_data = self._stat_count_delivery_order('logistics.log.loading', self.ids)
        for delivery_order in self:
            delivery_order.loading_count = mapped_data.get(delivery_order.id, 0)

    def _compute_unloading_count(self):
        """ Count the number of unloading logs """
        mapped_data = self._stat_count_delivery_order('logistics.log.unloading', self.ids)
        for delivery_order in self:
            delivery_order.unloading_count = mapped_data.get(delivery_order.id, 0)

    @api.constrains('requested_load')
    def _check_requested_load(self):
        for delivery_order in self:
            if not delivery_order.requested_load > 0.0:
                raise ValidationError(_('Requested Load must be a positive amount.'))

    @api.onchange('sale_id')
    def _onchange_sale_id(self):
        self.ensure_one()

        if self.sale_id and self.sale_id.order_line:
            self.product_id = self.sale_id.order_line[0].product_id
            self.uom_id = self.sale_id.order_line[0].product_uom

    @api.onchange('allocation_ids')
    def _onchange_allocation_ids(self):
        self.ensure_one()

        allocations = self.allocation_ids.sorted(lambda a: a.sequence)

        if allocations:
            self.sale_id = allocations[0].sale_id
            self.batching_plant_id = allocations[0].batching_plant_id

        if len(allocations) > 1:
            self.next_sale_id = allocations[1].sale_id

    @api.model_create_multi
    def create(self, vals_list):
        required_types = self.env['logistics.delivery.document.type'].search([('required', '=', True)])
        document_ids = [(0, 0, {'type_id': document.id}) for document in required_types]

        for vals in vals_list:
            # Assign sequence
            if vals.get('name', _('New')) == _('New'):
                IrSequence = self.env['ir.sequence']
                seq_date = None
                if 'order_date' in vals:
                    seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['order_date']))
                if 'company_id' in vals:
                    vals['name'] = IrSequence.with_context(force_company=vals['company_id']).next_by_code(
                        self._name, sequence_date=seq_date) or _('New')
                else:
                    vals['name'] = IrSequence.next_by_code(self._name, sequence_date=seq_date) or _('New')

            # Add required documents
            vals['document_ids'] = document_ids

        result = super(DeliveryOrder, self).create(vals_list)
        return result

    def action_assign(self):
        self.ensure_one()
        view_id = self.env.ref('tf_peec_logistics.logistics_delivery_order_assign_view_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assign Delivery Unit'),
            'res_model': 'logistics.delivery.order.assign',
            'view_mode': 'form',
            'views': [[view_id, 'form']],
            'target': 'new',
            'context': {'default_delivery_order_id': self.id, 'action': 'assign'}
        }

    def action_reassign(self):
        res = self.action_assign()
        res['name'] = _('Reassign Delivery Unit')
        return res

    def _action_start_trip(self, start_trip_type, title=_('Start Trip')):
        self.ensure_one()

        last_odometer = self.env['fleet.vehicle.odometer'].search([
            ('vehicle_id', '=', self.delivery_unit_id.tractor_head_id.id),
        ], order='date desc, id desc', limit=1)

        last_odometer_reading = 0
        if last_odometer:
            last_odometer_reading = last_odometer.value

        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'logistics.delivery.order.start.trip',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_delivery_order_id': self.id,
                'default_delivery_unit_id': self.delivery_unit_id.id,
                'default_odometer_reading': last_odometer_reading,
                'start_trip_type': start_trip_type
            }
        }

    def _action_end_trip(self, end_trip_type, title=_('End Trip')):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'logistics.delivery.order.end.trip',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_delivery_order_id': self.id,
                'default_delivery_unit_id': self.delivery_unit_id.id,
                'default_trip_log_id': self.trip_log_id.id,
                'end_trip_type': end_trip_type
            }
        }

    def action_start_trip_cp(self):
        return self._action_start_trip('cp', _('Start Trip to Cement Plant'))

    def action_end_trip_cp(self):
        return self._action_end_trip('cp', _('End Trip to Cement Plant'))

    def action_start_loading(self):
        self.ensure_one()

        # Search for unvalidated DOs
        unvalidated = self.env['logistics.delivery.order'].search([
            ('delivery_unit_id', '=', self.delivery_unit_id.id),
            ('id', '!=', self.id,),
            ('validated_by', '=', False)
        ])
        if unvalidated:
            raise ValidationError(_('Delivery Unit still has unvalidated deliveries pending. '
                                    'You are not allowed to load until all past Delivery Orders are validated.\n'
                                    'Ref: %s') % (', '.join(unvalidated.mapped('name')),))

        last_weight_log = self.env['logistics.log.weight'].search([
            ('delivery_order_id', '=', self.id),
            ('load_state', '=', 'empty')
        ], order='weighing_date desc', limit=1)

        if not last_weight_log:
            raise ValidationError(_('No empty weight log found. Please log tare weight before loading cement.'))

        if not self.atw_id:
            raise ValidationError(_('No ATW found. Please create ATW before loading cement.'))

        if self.atw_id.state == 'unmatched':
            raise ValidationError(_('ATW record is not matched with any Purchase Order. '
                                    'Please match the ATW before loading cement.'))

        self.env['logistics.log.loading'].create({
            'delivery_order_id': self.id,
            'delivery_unit_id': self.delivery_unit_id.id,
            'location_id': self.cement_plant_id.id,
            'start_date': fields.Datetime.now(),
        })

        if self.state != 'cp':
            raise ValidationError(_('The delivery order state already changed prior to your action. '
                                    'Please refresh record.'))
        self.write({'state': 'loading'})

    def action_end_loading(self):
        self.ensure_one()

        loading_log = self.env['logistics.log.loading'].search([
            ('delivery_order_id', '=', self.id),
            ('end_date', '=', False)
        ], order='start_date desc', limit=1)

        loading_log.write({
            'end_date': fields.Datetime.now()
        })

        if self.state != 'loading':
            raise ValidationError(_('The delivery order state already changed prior to your action. '
                                    'Please refresh record.'))

        self.write({'state': 'loaded'})

    def action_start_trip_bp(self):
        return self._action_start_trip('bp', _('Start Trip to Batching Plant'))

    def action_end_trip_bp(self):
        return self._action_end_trip('bp', _('End Trip to Batching Plant'))

    def action_start_unloading(self):
        self.ensure_one()

        last_weight_log = self.env['logistics.log.weight'].search([
            ('delivery_order_id', '=', self.id),
            ('load_state', '=', 'loaded')
        ], order='weighing_date desc', limit=1)

        if not last_weight_log:
            raise ValidationError(_('No loaded weight log found. Please log net weight before unloading cement.'))

        self.env['logistics.log.unloading'].create({
            'delivery_order_id': self.id,
            'delivery_unit_id': self.delivery_unit_id.id,
            'location_id': self.batching_plant_id.id,
            'start_date': fields.Datetime.now(),
        })

        if self.state != 'bp':
            raise ValidationError(_('The delivery order state already changed prior to your action. '
                                    'Please refresh record.'))
        self.write({'state': 'unloading'})

    def action_end_unloading(self):
        self.ensure_one()

        unloading_log = self.env['logistics.log.unloading'].search([
            ('delivery_order_id', '=', self.id),
            ('end_date', '=', False)
        ], order='start_date desc', limit=1)

        unloading_log.write({
            'end_date': fields.Datetime.now()
        })

        if self.state != 'unloading':
            raise ValidationError(_('The delivery order state already changed prior to your action. '
                                    'Please refresh record.'))

        self.write({'state': 'unloaded'})

    def action_start_trip_garage(self):
        return self._action_start_trip('garage', _('Start Trip to Garage'))

    def action_end_trip_garage(self):
        return self._action_end_trip('garage', _('End Trip to Garage'))

    def action_for_validation(self):
        self.ensure_one()

        if self.state != 'unloaded':
            raise ValidationError(_('The delivery order state already changed prior to your action. '
                                    'Please refresh record.'))

        self.write({'state': 'validation'})

    def action_validate(self):
        self.ensure_one()

        if self.state != 'validation':
            raise ValidationError(_('The delivery order state already changed prior to your action. '
                                    'Please refresh record.'))

        vals = {
            'validated_by': self.env.user.id
        }

        last_trip = self.trip_ids[-1]
        if (self.is_returning and self.trip_log_id.state == 'done') or last_trip.destination_id == self.garage_id:
            vals['state'] = 'closed'
            self.delivery_unit_id.write({'delivery_order_id': False})

        self.write(vals)

    def action_close(self):
        self.ensure_one()

        if self.state == 'validation' and self.validated_by:
            self.write({'state': 'closed'})

            # If Delivery Unit has already been assigned to another DO, do not clear DO field in DU
            if self.delivery_unit_id.delivery_order_id == self:
                self.delivery_unit_id.write({'delivery_order_id': False})

    def action_log_weight(self):
        self.ensure_one()

        last_weight_log = self.env['logistics.log.weight'].search([
            ('delivery_order_id', '=', self.id),
        ], order='weighing_date desc', limit=1)

        # Get last weight log for its tare weight in case it was logging for an empty vehicle
        tare_weight = 0
        load_state = 'empty'
        if last_weight_log and last_weight_log.load_state == 'empty':
            tare_weight = last_weight_log.tare_weight
            load_state = 'loaded'

        return {
            'type': 'ir.actions.act_window',
            'name': _('Log Weight'),
            'res_model': 'logistics.log.weight',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_delivery_order_id': self.id,
                'default_delivery_unit_id': self.delivery_unit_id.id,
                'default_tare_weight': tare_weight,
                'default_load_state': load_state,
            }
        }

    def action_create_atw(self):
        ATW = self.env['logistics.atw']
        for delivery_order in self:
            atw = ATW.create(
                {
                    'delivery_order_id': delivery_order.id,
                    'sale_id': delivery_order.sale_id.id or False,
                    'cement_plant_id': delivery_order.cement_plant_id.id,
                    'product_id': delivery_order.product_id.id,
                    'quantity': delivery_order.requested_load,
                    'uom_id': delivery_order.uom_id.id,
                }
            )
            delivery_order.atw_id = atw

    def _action_view_records(self, action_external_id):
        self.ensure_one()
        action = self.env.ref(action_external_id).read()[0]
        action['domain'] = [('delivery_order_id', 'in', self.ids)]
        action['context'] = {
            'default_delivery_order_id': self.id,
            'default_delivery_unit_id': self.delivery_unit_id.id,
            'default_trip_log_id': self.trip_log_id.id
        }
        return action

    def action_view_trip_logs(self):
        return self._action_view_records('tf_peec_logistics.action_logistics_log_trip')

    def action_view_trip_expenses(self):
        return self._action_view_records('tf_peec_logistics.action_logistics_log_expense')

    def action_view_weight_logs(self):
        return self._action_view_records('tf_peec_logistics.action_logistics_log_weight')

    def action_view_loading_logs(self):
        return self._action_view_records('tf_peec_logistics.action_logistics_log_loading')

    def action_view_unloading_logs(self):
        return self._action_view_records('tf_peec_logistics.action_logistics_log_unloading')

    def get_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url_params = {
            'id': self.id,
            'action': self.env.ref('tf_peec_logistics.action_logistics_delivery_order').id,
            'model': self._name,
            'view_type': 'form',
        }
        url = werkzeug.urls.url_join(
            base_url, 'web?#%s' % werkzeug.urls.url_encode(url_params)
        )
        return url


class DeliveryOrderAllocation(models.Model):
    _name = 'logistics.delivery.order.allocation'
    _description = 'Delivery Order Allocation'
    _order = 'sequence'

    sequence = fields.Integer('Sequence')
    delivery_order_id = fields.Many2one('logistics.delivery.order', 'Delivery Order')
    sale_id = fields.Many2one('sale.order', 'Sales Order', required=True)
    requested_load = fields.Float('Requested Load')
    uom_id = fields.Many2one('uom.uom', 'Load UoM')
    batching_plant_id = fields.Many2one('res.partner', 'Batching Plant')
    state = fields.Selection([('pending', 'Pending'), ('done', 'Done')], 'State', default='pending')
    picking_id = fields.Many2one('stock.picking', ' Delivery Receipt')
    delivered_qty = fields.Float('Delivered Quantity')

    @api.onchange('sale_id')
    def _onchange_sale_id(self):
        if self.sale_id:
            self.uom_id = self.sale_id.order_line[0].product_uom


class DeliveryDocumentType(models.Model):
    _name = 'logistics.delivery.document.type'
    _description = 'Delivery Document Type'

    name = fields.Char(required=True)
    required = fields.Boolean(help="Indicates if the document type will be required for Delivery Orders. "
                                   "If required, the Document Type will automatically be populated in new "
                                   "Delivery Orders. Non required document types can be added to Delivery Orders "
                                   "upon need manually.")


class DeliveryDocument(models.Model):
    _name = 'logistics.delivery.document'
    _inherit = ['portal.mixin']
    _description = 'Delivery Document'

    delivery_order_id = fields.Many2one('logistics.delivery.order', 'Delivery Order')
    type_id = fields.Many2one('logistics.delivery.document.type', 'Delivery Document Type', ondelete='restrict')
    required = fields.Boolean(related='type_id.required')
    picture1 = fields.Image(string='Picture 1')
    picture2 = fields.Image(string='Picture 2')
    picture3 = fields.Image(string='Picture 3')
    submitted = fields.Boolean()

    def _get_picture_id(self, picture_field):
        attachment = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('res_field', '=', picture_field)
        ], limit=1)
        attachment.generate_access_token()
        return "%s?access_token=%s" % (attachment.id, attachment.access_token)

    @api.onchange('picture1', 'picture2', 'picture3')
    def _onchange_pictures(self):
        for document in self:
            if document.picture1 or document.picture2 or document.picture3:
                document.submitted = True
            else:
                document.submitted = False


class DeliveryUnit(models.Model):
    _name = 'logistics.delivery.unit'
    _description = 'Delivery Unit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    name = fields.Char('Reference', default='New', copy=False, required=True, tracking=True, index=True)
    tractor_head_id = fields.Many2one('fleet.vehicle', 'Tractor Head', tracking=True)
    trailer_id = fields.Many2one('fleet.vehicle', 'Trailer', tracking=True)
    driver_ids = fields.Many2many('hr.employee', 'logistics_delivery_unit_hr_employee_driver_rel', string='Driver',
                                  tracking=True)
    helper_ids = fields.Many2many('hr.employee', 'logistics_delivery_unit_hr_employee_helper_rel', string='Helpers',
                                  tracking=True)
    driver_domain_ids = fields.Many2many('hr.employee', 'delivery_unit_driver_pairing_domain_rel', compute='_compute_domain')
    helper_domain_ids = fields.Many2many('hr.employee', 'delivery_unit_helper_pairing_domain_rel',
                                         compute='_compute_domain')
    delivery_order_id = fields.Many2one('logistics.delivery.order', 'Current Delivery Order', tracking=True)
    delivery_order_state = fields.Selection(related='delivery_order_id.state', string='State (Delivery Order)',
                                            store=True, index=True)
    location_id = fields.Many2one('res.partner', 'Last Location', tracking=True)
    tractor_head_availability = fields.Boolean('Tractor Head Availability', compute='_compute_vehicle_availability',
                                               store=True)
    trailer_availability = fields.Boolean('Trailer Availability', compute='_compute_vehicle_availability', store=True)
    driver_availability = fields.Boolean('Driver Availability', compute='_compute_personnel_availability', store=True)
    helper_availability = fields.Boolean('Helper Availability', compute='_compute_personnel_availability', store=True)
    unavailable_personnel = fields.Many2many('hr.employee', 'logistics_delivery_unit_unavailable_personnel_rel',
                                             string='Unavailable Personnel', compute='_compute_personnel_availability',
                                             store=True)
    unavailable_vehicles = fields.Many2many('fleet.vehicle', 'logistics_delivery_unit_unavailable_vehicle_rel',
                                            string='Unavailable Vehicles', compute='_compute_vehicle_availability',
                                            store=True)
    state = fields.Selection([('inactive', 'Inactive'), ('active', 'Active')], compute='_compute_state', store=True,
                             tracking=True, index=True)
    status = fields.Selection([('normal', 'Normal'), ('blocked', 'Blocked'), ('done', 'Done')], default='normal')
    active = fields.Boolean(default=True, tracking=True)

    @api.depends('tractor_head_id.state_id', 'trailer_id.state_id')
    def _compute_vehicle_availability(self):
        available = self.env.company.logistics_vehicle_available_states
        for delivery_unit in self:
            unavailable_vehicles = self.env['fleet.vehicle']
            if not delivery_unit.tractor_head_id \
                    or (delivery_unit.tractor_head_id and delivery_unit.tractor_head_id.state_id not in available):
                delivery_unit.tractor_head_availability = False
                unavailable_vehicles += delivery_unit.tractor_head_id
            else:
                delivery_unit.tractor_head_availability = True

            if not delivery_unit.trailer_id \
                    or (delivery_unit.trailer_id and delivery_unit.trailer_id.state_id not in available):
                delivery_unit.trailer_availability = False
                unavailable_vehicles += delivery_unit.trailer_id
            else:
                delivery_unit.trailer_availability = True

            delivery_unit.unavailable_vehicles = unavailable_vehicles

    @api.depends('driver_ids.dh_availability', 'helper_ids.dh_availability')
    def _compute_personnel_availability(self):
        for delivery_unit in self:
            unavailable_personnel = self.env['hr.employee']
            for driver in delivery_unit.driver_ids:
                driver_availability = True
                if driver.dh_availability != 'available':
                    driver_availability = False
                    unavailable_personnel += driver
                delivery_unit.driver_availability = driver_availability

            for helper in delivery_unit.helper_ids:
                helper_availability = True
                if helper.dh_availability != 'available':
                    helper_availability = False
                    unavailable_personnel += helper
                delivery_unit.helper_availability = helper_availability

            delivery_unit.unavailable_personnel = unavailable_personnel

    @api.depends('tractor_head_availability', 'trailer_availability', 'driver_availability', 'helper_availability')
    def _compute_state(self):
        for delivery_unit in self:
            employees = delivery_unit.driver_ids + delivery_unit.helper_ids
            if delivery_unit.tractor_head_availability \
                    and delivery_unit.trailer_availability \
                    and delivery_unit.driver_availability \
                    and delivery_unit.helper_availability:
                delivery_unit.state = 'active'
            else:
                delivery_unit.state = 'inactive'

    @api.depends('driver_ids', 'helper_ids')
    def _compute_domain(self):
        HrEmployee = self.env['hr.employee']
        for rec in self:
            if rec.driver_ids and not rec.helper_ids:
                for driver_id in rec.driver_ids:
                    rec.driver_domain_ids = HrEmployee.search([('select_dh', '=', 'driver'),
                                                               ('contract_id.dh_rate_type',
                                                                '=', driver_id.contract_id.dh_rate_type)])
                    rec.helper_domain_ids = HrEmployee.search([('select_dh', '=', 'helper'),
                                                               ('contract_id.dh_rate_type',
                                                                '=', driver_id.contract_id.dh_rate_type)])
            elif not rec.driver_ids and rec.helper_ids:
                for helper_id in rec.helper_ids:
                    rec.driver_domain_ids = HrEmployee.search([('select_dh', '=', 'driver'),
                                                               ('contract_id.dh_rate_type',
                                                                '=', helper_id.contract_id.dh_rate_type)])
                    rec.helper_domain_ids = HrEmployee.search([('select_dh', '=', 'helper'),
                                                               ('contract_id.dh_rate_type',
                                                                '=', helper_id.contract_id.dh_rate_type)])
            elif not rec.driver_ids and not rec.helper_ids:
                rec.driver_domain_ids = HrEmployee.search([('select_dh', '=', 'driver')])
                rec.helper_domain_ids = HrEmployee.search([('select_dh', '=', 'helper')])

            #If this condition is removed error occurs when opening DH Pairing for some reason.
            else:
                rec.driver_domain_ids
                rec.helper_domain_ids

    @api.onchange('driver_ids')
    def _onchange_driver_ids(self):
        for delivery_unit in self:
            pairings = self.env['logistics.dh.pairing'].search([('driver_ids', 'in', delivery_unit.driver_ids.ids)])
            if pairings:
                delivery_unit.helper_ids = pairings[0].helper_ids

    @api.onchange('helper_ids')
    def _onchange_helper_ids(self):
        for delivery_unit in self:
            pairings = self.env['logistics.dh.pairing'].search([('helper_ids', 'in', delivery_unit.helper_ids.ids)])
            if pairings:
                delivery_unit.driver_ids = pairings[0].driver_ids

    @api.onchange('tractor_head_id')
    def _onchange_tractor_head_id(self):
        for delivery_unit in self:
            pairings = self.env['fleet.vehicle.pairing'].search(
                [('tractor_head_id', '=', delivery_unit.tractor_head_id.id)])
            if pairings:
                delivery_unit.tractor_head_id = pairings[0].tractor_head_id

    @api.onchange('trailer_id')
    def _onchange_trailer_id(self):
        for delivery_unit in self:
            pairings = self.env['fleet.vehicle.pairing'].search([('trailer_id', '=', delivery_unit.trailer_id.id)])
            if pairings:
                delivery_unit.trailer_id = pairings[0].trailer_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Assign sequence
            if vals.get('name', _('New')) == _('New'):
                IrSequence = self.env['ir.sequence']
                if 'company_id' in vals:
                    vals['name'] = IrSequence.with_context(force_company=vals['company_id']).next_by_code(
                        self._name) or _('New')
                else:
                    vals['name'] = IrSequence.next_by_code(self._name) or _('New')
        result = super(DeliveryUnit, self).create(vals_list)

        # Update the delivery units of the employees
        for rec in result:
            print(rec.name)
            employees = rec.driver_ids + rec.helper_ids
            vehicles = rec.tractor_head_id + rec.trailer_id
            print(employees)
            # Double check if employees still do not have a delivery unit assigned
            employees_with_du = employees.filtered(lambda e: e.delivery_unit_id)
            vehicles_with_du = vehicles.filtered(lambda e: e.delivery_unit_id)
            if employees_with_du:
                raise ValidationError(_('Cannot create new Delivery Unit. The following employees were already '
                                        'assigned to a different Delivery Unit prior to saving this record:\n'
                                        '- %s') % ("\n- ".join(["%s (%s)" % (e.display_name, e.delivery_unit_id.name)
                                                                for e in employees_with_du])))
            elif vehicles_with_du:
                raise ValidationError(_('Cannot create new Delivery Unit. The following vehicles were already '
                                        'assigned to a different Delivery Unit prior to saving this record:\n'
                                        '- %s') % ("\n- ".join(["%s (%s)" % (v.display_name, v.delivery_unit_id.name)
                                                                for v in vehicles_with_du])))
            else:
                print('here')
                employees.write({'delivery_unit_id': rec.id})
                vehicles.write({'delivery_unit_id': rec.id})

        return result

    def _write_personnel_updater(self, entity_name, new_entity_ids):
        entities = self.env['hr.employee'].browse(new_entity_ids)
        for rec in self:
            current_entities = getattr(rec, entity_name)
            new_entities = entities
            removed_entities = current_entities - new_entities
            for re in removed_entities:
                re.write({'delivery_unit_id': False})
            additional_entities = new_entities - current_entities
            for ae in additional_entities:
                if ae.delivery_unit_id:
                    raise ValidationError(_('Cannot add the following employee in Delivery Unit because they are '
                                            'already currently assigned to a Delivery Unit:\n- %s (%s)')
                                          % (ae.display_name, ae.delivery_unit_id.name))
                ae.write({'delivery_unit_id': rec.id})

    def _write_vehicle_updater(self, entity_name, entity_id):
        new_vehicle = self.env['fleet.vehicle'].browse([entity_id])
        for rec in self:
            # Check if vehicle really changed or just redundantly updating the vehicle
            current_vehicle = getattr(rec, entity_name)
            if current_vehicle != new_vehicle:
                if new_vehicle.delivery_unit_id:
                    raise ValidationError(_('Cannot add the following vehicle in Delivery Unit because it is '
                                            'already currently assigned to a Delivery Unit:\n- %s (%s)')
                                          % (new_vehicle.display_name, new_vehicle.delivery_unit_id.name))
                else:
                    current_vehicle.write({'delivery_unit_id': False})
                    new_vehicle.write({'delivery_unit_id': rec.id})

    def write(self, vals):
        if 'active' in vals:
            if not vals['active']:
                employees = self.mapped('driver_ids') + self.mapped('helper_ids')
                employees.write({'delivery_unit_id': False})
            else:
                # If unarchiving, check if the employees are already in other active delivery unit
                employees = self.mapped('driver_ids') + self.mapped('helper_ids')
                employees_with_du = employees.filtered(lambda e: e.delivery_unit_id)
                if employees_with_du:
                    raise ValidationError(_('Cannot unarchive delivery unit. The following employees currently have an '
                                            'existing Delivery Unit:\n'
                                            '%s') % (", ".join(["%s (%s)" % (e.display_name, e.delivery_unit_id.name)
                                                                for e in employees_with_du])))
                else:
                    for rec in self:
                        employees_to_update = rec.driver_ids + rec.helper_ids
                        employees_to_update.write({'delivery_unit_id': rec.id})

        if 'driver_ids' in vals:
            self._write_personnel_updater('driver_ids', vals.get('driver_ids')[0][2])

        if 'helper_ids' in vals:
            self._write_personnel_updater('helper_ids', vals.get('helper_ids')[0][2])

        if 'tractor_head_id' in vals:
            self._write_vehicle_updater('tractor_head_id', vals.get('tractor_head_id'))

        if 'trailer_id' in vals:
            self._write_vehicle_updater('trailer_id', vals.get('trailer_id'))

        return super(DeliveryUnit, self).write(vals)

    def unlink(self):
        for rec in self:
            employees = rec.driver_ids + rec.helper_ids
            vehicles = rec.tractor_head_id + rec.trailer_id
            for employee in employees:
                if employee.delivery_unit_id == rec:
                    employee.write({'delivery_unit_id': False})
            for vehicle in vehicles:
                if vehicle.delivery_unit_id == rec:
                    vehicle.write({'delivery_unit_id': False})

        return super(DeliveryUnit, self).unlink()


class DriverHelperPairing(models.Model):
    _name = 'logistics.dh.pairing'
    _description = 'Driver/Helper Pairing'

    driver_ids = fields.Many2many('hr.employee', 'logistics_dh_pairing_driver_rel', string='Drivers',
                                  tracking=True)
    helper_ids = fields.Many2many('hr.employee', 'logistics_dh_pairing_helper_rel', string='Helpers',
                                  tracking=True)
    driver_domain_ids = fields.Many2many('hr.employee', 'logistics_driver_pairing_domain_rel',
                                         compute='_compute_domain')
    helper_domain_ids = fields.Many2many('hr.employee', 'logistics_helper_pairing_domain_rel',
                                         compute='_compute_domain')
    remarks = fields.Text('Remarks')

    @api.depends('driver_ids', 'helper_ids')
    def _compute_domain(self):
        HrEmployee = self.env['hr.employee']
        for rec in self:
            if rec.driver_ids and not rec.helper_ids:
                for driver_id in rec.driver_ids:
                    rec.driver_domain_ids = HrEmployee.search([('select_dh', '=', 'driver'),
                                                               ('contract_id.dh_rate_type',
                                                                '=', driver_id.contract_id.dh_rate_type)])
                    rec.helper_domain_ids = HrEmployee.search([('select_dh', '=', 'helper'),
                                                               ('contract_id.dh_rate_type',
                                                                '=', driver_id.contract_id.dh_rate_type)])
            elif not rec.driver_ids and rec.helper_ids:
                for helper_id in rec.helper_ids:
                    rec.driver_domain_ids = HrEmployee.search([('select_dh', '=', 'driver'),
                                                               ('contract_id.dh_rate_type',
                                                                '=', helper_id.contract_id.dh_rate_type)])
                    rec.helper_domain_ids = HrEmployee.search([('select_dh', '=', 'helper'),
                                                               ('contract_id.dh_rate_type',
                                                                '=', helper_id.contract_id.dh_rate_type)])
            elif not rec.driver_ids and not rec.helper_ids:
                rec.driver_domain_ids = HrEmployee.search([('select_dh', '=', 'driver')])
                rec.helper_domain_ids = HrEmployee.search([('select_dh', '=', 'helper')])

            #If this condition is removed error occurs when opening DH Pairing for some reason.
            else:
                rec.driver_domain_ids
                rec.helper_domain_ids

