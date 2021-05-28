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
from odoo.exceptions import RedirectWarning
from odoo.osv import expression


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    _sql_constraints = [('body_num_unique', 'unique(body_num)',
                         'Body number is already being used by another vehicle.'),
                        ('mv_file_num', 'unique(mv_file_num)',
                         'MV File Number is already being used by another vehicle.')
                        ]

    _VEHICLE_TYPES = [
        ('tractor', "Tractor Head"),
        ('carrier', "Bulk Carrier"),
        ('flatbed', "Flatbed Trailer"),
        ('service', "Service Vehicle"),
        ('others', "Others")
    ]

    def _domain_equipment_vocation_id(self):
        key = int(self.env['ir.config_parameter'].sudo().get_param('tf_peec_maintenance.vmrs_code_key_1_id'))
        return [('code_key_id', '=', key)]

    type = fields.Selection(_VEHICLE_TYPES, "Vehicle Type", help="Indicates the vehicle type.")
    body_num = fields.Char("Body Number", help="Indicates the vehicle's body number.", required=True, copy=False)
    mv_file_num = fields.Char("MV File Number", required=True, copy=False,
                              help="Indicates the vehicle's MV File Number.")
    engine_num = fields.Char("Engine Number", help="Indicates the vehicle's engine number.")
    config_id = fields.Many2one('fleet.vehicle.drive.configuration', "Drive Configuration",
                                groups="fleet.fleet_group_manager")
    tank_id = fields.Many2one('fleet.vehicle.tank', "Vehicle Tank", help="Indicates the vehicle's suspension type.")
    suspension_id = fields.Many2one('fleet.vehicle.suspension.type', "Suspension Type",
                                    help="Indicates the vehicle's suspension type.")
    location_id = fields.Many2one('fleet.location', "Vehicle Location",
                                  help="Indicates the vehicle's current physical location.")
    lto_office_id = fields.Many2one('res.partner', "LTO Office")
    pair_id = fields.Many2one('fleet.vehicle', "Vehicle Pair", domain=[('type', '=', 'flatbed')])
    odometer_ids = fields.One2many('fleet.vehicle.odometer', 'vehicle_id', "Odometers")
    acquisition_date = fields.Date('Acquisition Date', required=False,
                                   default=fields.Date.today, help="Indicates the vehicle's acquisition date.")
    registered_date = fields.Date("First Registered Date", help="Indicates the current CR Date.")
    cr_date = fields.Date("Current CR Date", help="Indicates the date of LTO registration.")
    capacity = fields.Float("Capacity", help="Indicates the vehicle's capacity")
    km_total = fields.Float("Total Km. Run", readonly=True, compute='_compute_km_total', store=True, copy=False,
                            help="Indicates the total km. run by the vehicle based on Odometer readings.")
    car_value = fields.Float(string="Catalog Value (VAT Incl.)", help='Value of the bought vehicle',
                             groups="fleet.fleet_group_manager")
    net_car_value = fields.Float(string="Purchase Value", help="Purchase Value of the car",
                                 groups="fleet.fleet_group_manager")
    residual_value = fields.Float(string="Residual Value", groups="fleet.fleet_group_manager",
                                  help="Indicates the vehicle's residual value.")
    equipment_vocation_id = fields.Many2one('vmrs.code', string="Equipment Vocation",
                                            domain=_domain_equipment_vocation_id,
                                            help="Indicates the vehicle's applicable VMRS code for equipment vocation.")
    inventory_location_id = fields.Many2one('stock.location', 'Inventory Location')
    owner_id = fields.Many2one('res.partner', 'Registerd Owner')

    @api.onchange('type')
    def _onchange_type(self):
        for rec in self:
            if rec.type != 'tractor' and rec.pair_id:
                rec.pair_id = False

    @api.depends('odometer_ids', 'odometer_ids.value')
    def _compute_km_total(self):
        for rec in self:
            odometer_ids = rec.odometer_ids
            if odometer_ids:
                odometer_dates = odometer_ids.filtered(lambda o: o.value == 0.0).mapped('date')
                if odometer_dates:
                    max_date = max(odometer_dates)
                    peak_values = odometer_ids.filtered(lambda o: o.date > max_date).mapped('value')
                    if peak_values:
                        rec.km_total = sum(peak_values)
                    else:
                        rec.km_total = 0.0
                else:
                    rec.km_total = 0.0
            else:
                rec.km_total = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        result = super(FleetVehicle, self).create(vals_list)
        result.create_inventory_location()
        return result

    def create_inventory_location(self):
        for vehicle in self:
            StockLocation = self.env['stock.location']
            location_id = self.env['ir.config_parameter'].sudo().get_param('tf_peec_fleet.fleet_location_parent_id')

            # Only create or search if doesn't already have an inventory location
            if not vehicle.inventory_location_id:
                # Search if there's a location with the vehicle set
                existing_location = StockLocation.search([('vehicle_id', '=', vehicle.id)])

                if not existing_location:
                    vehicle_location = StockLocation.create({
                        'location_id': int(location_id),
                        'name': vehicle.body_num,
                        'usage': 'production',
                        'company_id': self.env.company.id,
                        'vehicle_id': vehicle.id,
                    })
                    vehicle.write({
                        'inventory_location_id': vehicle_location.id
                    })
                else:
                    vehicle.write({
                        'inventory_location_id': existing_location.id
                    })

    def name_get(self):
        result = []
        for vehicle in self:
            name = "%s: %s" % (
                vehicle.body_num,
                vehicle.name
            )
            result.append((vehicle.id, name))
        return result

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if operator == 'ilike' and not (name or '').strip():
            domain = []
        else:
            domain = [
                '|',
                    ('name', operator, name),
                    '|',
                        ('driver_id.name', operator, name),
                        ('body_num', operator, name)
            ]
        rec = self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
        return models.lazy_name_get(self.browse(rec).with_user(name_get_uid))


class FleetVehicleLogFuel(models.Model):
    _inherit = "fleet.vehicle.log.fuel"

    def _get_default_location_id(self):
        location_id = self.env['ir.config_parameter'].sudo().get_param('tf_peec_fleet.location_id')
        if location_id:
            return int(location_id)
        else:
            return False

    fuel_source = fields.Selection([('garage', "Garage"), ('vendor', "Vendor")], "Fuel Source",
                                   help="Indicates the source of fuel.")
    distance_travelled = fields.Float("Distance Travelled",
                                      help="Indicates the distance traveled based on Last Odometer reading.")
    measurement = fields.Float("Measurement", help="Indicates the measurement done by the inspector.")
    volume_actual = fields.Float("Actual Volume", help="Indicates the actual volume of tank based on measurement.")
    short_over = fields.Float("Short/Over", help="Indicates whether refuel is short/over target SUCF.")
    balance = fields.Float("Running Balance", help="Indicates the tank's current volume after refueling.")
    inspector_id = fields.Many2one('hr.employee', "Inspector",
                                   help="Indicates the person who conducted the inspection.")
    card_id = fields.Many2one('fleet.card', "Fleet Card", help="Indicates the fleet card the purchases used.")
    fuel_id = fields.Many2one('product.product', "Fuel", domain="[('type','=','product')]",
                              help="Indicates the fuel used in stock.")
    picking_id = fields.Many2one('stock.picking', "Consumption Record",
                                 help="Indicates the related fuel transfer record.")
    location_id = fields.Many2one('stock.location', "Fuel Source Location",
                                  default=_get_default_location_id)

    @api.model
    def create(self, vals):
        res = super(FleetVehicleLogFuel, self).create(vals)

        picking_obj = self.env['stock.picking']
        immediate_transfer_obj = self.env['stock.immediate.transfer']
        params = self.env['ir.config_parameter'].sudo()
        picking_type_id = int(params.get_param('tf_peec_fleet.picking_type_id'))
        picking_type = self.env['stock.picking.type']
        if picking_type_id:
            picking_type = self.env['stock.picking.type'].browse([picking_type_id])

        if res.vehicle_id and res.vehicle_id.inventory_location_id:
            location_dest_id = res.vehicle_id.inventory_location_id.id
        else:
            location_dest_id = int(params.get_param('tf_peec_fleet.location_dest_id'))

        log_ids = res.filtered(lambda r: r.fuel_source == 'garage')
        if log_ids:
            if not picking_type_id:
                dummy, action_id = self.env['ir.model.data'].get_object_reference('fleet',
                                                                                  'fleet_config_settings_action')
                msg = "Operation type for fuel consumption has not been configured."
                raise RedirectWarning(msg, action_id, ('Go to the fleet configuration panel'))
            if not location_dest_id:
                dummy, action_id = self.env['ir.model.data'].get_object_reference('fleet',
                                                                                  'fleet_config_settings_action')
                msg = "Destination Location for fuel consumption has not been configured."
                raise RedirectWarning(msg, action_id, ('Go to the fleet configuration panel'))

        for rec in log_ids:
            location_id = rec.location_id
            name = "Refuel %s: on %s" % (rec.vehicle_id.name, fields.Datetime.now())

            if picking_type.sequence_code == 'OUT-TRANSFER':
                vals = {
                    'name': name,
                    'origin': name,
                    'scheduled_date': rec.date,
                    'picking_type_id': picking_type_id,
                    'location_id': location_id.id,
                    'location_dest_id': picking_type.default_location_dest_id.id,
                    'loc_internal_dest_id': location_dest_id,
                    'user_id': res.purchaser_id.id,
                    'move_ids_without_package': [(0, 0, {
                        'name': name,
                        'company_id': self.env.user.company_id.id,
                        'picking_type_id': picking_type_id,
                        'location_id': location_id.id,
                        'location_dest_id': picking_type.default_location_dest_id.id,
                        'product_id': rec.fuel_id.id,
                        'product_uom': self.env.ref('uom.product_uom_litre'),
                        'product_uom_qty': rec.liter
                    })]
                }
            else:
                vals = {
                    'name': name,
                    'origin': name,
                    'scheduled_date': rec.date,
                    'picking_type_id': picking_type_id,
                    'location_id': location_id.id,
                    'location_dest_id': location_dest_id,
                    'user_id': res.purchaser_id.id,
                    'move_ids_without_package': [(0, 0, {
                        'name': name,
                        'company_id': self.env.user.company_id.id,
                        'picking_type_id': picking_type_id,
                        'location_id': location_id.id,
                        'location_dest_id': location_dest_id,
                        'product_id': rec.fuel_id.id,
                        'product_uom': self.env.ref('uom.product_uom_litre'),
                        'product_uom_qty': rec.liter
                    })]
                }
            print(vals)
            picking_id = picking_obj.create(vals)
            picking_id.action_confirm()
            picking_id.action_assign()
            transfer_id = immediate_transfer_obj.create({'pick_ids': [(4, picking_id.id)]})
            transfer_id.process()

            if picking_type.sequence_code == 'OUT-TRANSFER':
                picking_id.create_incoming_picking()

            if picking_id.move_lines and picking_id.move_lines.stock_valuation_layer_ids:
                valuation_id = picking_id.move_lines[0].stock_valuation_layer_ids[0]
                unit_cost = valuation_id.unit_cost
                rec.write({
                    'price_per_liter': unit_cost,
                    'amount': unit_cost * rec.liter,
                    'picking_id': picking_id,
                })
        return res

    # TODO after logistics
    # trip_log_id = fields.Many2one('', "Trip Log", 
    #                               help="Indicates the corresponding Trip Log, if re-fuel done during an active trip.")
    # sucf_target = fields.Integer(related='trip_log_id.sucf_target',
    #                              help="Indicates the target SUCF, based on the Trip Log.")
    # sucf_actual = fields.Float(related='trip_log_id.sucf_actual',
    #                            help="Indicates the actual SUCF, based on the distance travelled and amount fueled.")

    # def update_inventory(self):


class FleetVehicleLogContract(models.Model):
    _inherit = "fleet.vehicle.log.contract"

    exp_odomtr = fields.Float("Contract Expiration Odometer",
                              help="Indicates the Odometer reading when the contract expires.")
    cost_frequency = fields.Selection(selection_add=[('odometer', 'Odometer')])
    odomtr_interval = fields.Float("Recurring Cost Odometer Interval",
                                   help="Indicates the Odometer interval on which recurring costs are created.")
    renewal_reading = fields.Float("Estimated Contract Renewal Reading",
                                   help="Indicates the estimated Odometer upon next expiration or renewal.")
    next_recurring = fields.Float("Estimated Next Recurring Cost Reading",
                                  help="Indicates the estimated odometer upon next recurring cost.")
    reg_name = fields.Char("Registered Name", help="Indicates the registered name.")
    reg_num = fields.Char("Certificate of Registration Number",
                          help="Indicates the certificate of registration number.")
    receipt_num = fields.Char("Original Receipt Number", help="Indicates the original receipt number.")
    body_num = fields.Char(related='vehicle_id.body_num', store=True)
    license_plate = fields.Char(related='vehicle_id.license_plate', store=True)
    model_id = fields.Many2one(related='vehicle_id.model_id', store=True)


class FleetVehicleOdometer(models.Model):
    _inherit = 'fleet.vehicle.odometer'

    @api.model
    def create(self, vals):
        res = super(FleetVehicleOdometer, self).create(vals)

        for rec in res:
            contract_ids = rec.vehicle_id.log_contracts
            odomtr_value = rec.value

            # Check estimated next recurring cost reading
            recurring_cost_ids = contract_ids.filtered(lambda c: c.next_recurring <= odomtr_value)
            for contract_id in recurring_cost_ids:
                data = {
                    'amount': contract_id.cost_generated,
                    'date': fields.Date.context_today(rec),
                    'vehicle_id': contract_id.vehicle_id.id,
                    'cost_subtype_id': contract_id.cost_subtype_id.id,
                    'contract_id': contract_id.id,
                    'auto_generated': True
                }
                self.env['fleet.vehicle.cost'].create(data)

            # Check estimated contract renewal reading
            expiring_contract_ids = contract_ids.filtered(lambda c: c.renewal_reading <= odomtr_value)
            if expiring_contract_ids:
                expiring_contract_ids.write({'state': 'expired'})

        return res


class FleetVehicleCost(models.Model):
    _inherit = 'fleet.vehicle.cost'

    repair_order_id = fields.Many2one('repair.order', "Repair Order ID", copy=False)


class FleetVehiclePairing(models.Model):
    _name = 'fleet.vehicle.pairing'
    _description = 'Vehicle Pairing'

    tractor_head_id = fields.Many2one('fleet.vehicle', string='Tractor Head', required=True)
    trailer_id = fields.Many2one('fleet.vehicle', string='Trailer', required=True)
    remarks = fields.Text('Remarks')
