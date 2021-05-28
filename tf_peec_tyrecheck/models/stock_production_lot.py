import json
import logging

import requests
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from werkzeug.urls import url_encode

_logger = logging.getLogger(__name__)


class StockProductionLot(models.Model):
    _inherit = 'stock.production.lot'

    is_tire = fields.Boolean(related='product_id.is_tire')
    tyrecheck_id = fields.Char('TyreCheck ID', copy=False, index=True)
    tyrecheck_product_id = fields.Many2one('tyrecheck.product', 'TyreCheck Product')
    tyrecheck_service_center_id = fields.Many2one('tyrecheck.service.center', 'TyreCheck Service Center')
    tyrecheck_company_id = fields.Many2one('tyrecheck.company', 'TyreCheck Company')
    tyrecheck_last_vehicle = fields.Char('TyreCheck Last Vehicle', tracking=True)
    tyrecheck_last_vehicle_tyre = fields.Char('TyreCheck Last Vehicle Tyre', tracking=True)
    tyrecheck_last_sync = fields.Datetime('Last Sync', readonly=True)
    tyrecheck_current_tread_depth = fields.Float('Current Tread Depth', tracking=True)
    tyrecheck_value = fields.Monetary('Current Value', tracking=True)
    purchase_price = fields.Monetary('Purchase Price', tracking=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    @api.constrains('tyrecheck_id')
    def _check_tyrecheck_id(self):
        for serial in self:
            if serial.tyrecheck_id and serial.search_count([('tyrecheck_id', '=', serial.tyrecheck_id)]) > 1:
                raise ValidationError(_('TyreCheck ID is already used in a different serial number.'))

    # @api.depends('name')
    # def _compute_purchase_price(self):
    #     for lot in self:
    #         stock_moves = self.env['stock.move.line'].search([
    #             ('lot_id', '=', lot.id),
    #             ('state', '=', 'done')
    #         ]).mapped('move_id')
    #         stock_moves = stock_moves.search([('id', 'in', stock_moves.ids)]).filtered(
    #             lambda move: move.picking_id.location_id.usage == 'supplier' and move.state == 'done')
    #         if stock_moves:
    #             lot.purchase_price = stock_moves[0].price_unit

    # @api.onchange('purchase_price')
    # def _onchange_purchase_price(self):
    #     for lot in self:
    #         lot.tyrecheck_value = lot.purchase_price

    @api.model_create_multi
    def create(self, vals_list):
        result = super(StockProductionLot, self).create(vals_list)

        for lot in result:
            if lot.product_id.is_tire:
                stock_moves = self.env['stock.move.line'].search([
                    ('lot_name', '=', lot.name),
                ]).mapped('move_id')
                stock_moves = stock_moves.search([('id', 'in', stock_moves.ids)]).filtered(
                    lambda move: move.picking_id.location_id.usage == 'supplier')
                if stock_moves:
                    lot.purchase_price = stock_moves[0].price_unit
                    lot.tyrecheck_value = stock_moves[0].price_unit

                # Do TyreCheck Processing
                lot.action_tyrecheck_sync()

        return result

    def _create_tyre(self, token=''):
        # Build request URL
        host = "%s/api/api/tcTyre" % (self.env.company.tyrecheck_host,)
        data = {
            'TyreSerialNumber': self.name,
        }
        # host = "%s?%s" % (host, url_encode(params))

        # Include token to header
        if not token:
            token = self.env['tyrecheck']._get_token()
        headers = {'Authorization': 'Bearer %s' % (token,)}

        # Execute request
        response = requests.post(host, headers=headers, data=json.dumps(data))
        if response.status_code == 200:
            response_json = response.json()
            return response_json
        else:
            _logger.error("Error %s:\n%s" % (response.status_code, response.text))
            return {}

    def _get_fleet_vehicle(self, vehicle_id, vehicle_reg_num='', token=''):
        Vehicle = self.env['fleet.vehicle']
        if vehicle_id:
            vehicle = Vehicle.search([('tyrecheck_id', '=', vehicle_id)])
            return vehicle
        elif vehicle_reg_num:
            vehicle = Vehicle.search([('body_num', '=', vehicle_reg_num)])
            return vehicle
        elif vehicle_id and not vehicle_reg_num:
            tc_vehicle = self.env['tyrecheck']._get_vehicle(vehicle_id, token=token)
            odoo_vehicle = self.env['fleet.vehicle'].search(
                [('body_num', '=', tc_vehicle['VehicleRegistrationNumber'])])
            return odoo_vehicle
        else:
            return Vehicle

    def action_tyrecheck_test(self):
        for lot in self:
            TyreCheck = self.env['tyrecheck']
            token = TyreCheck._get_token()
            # tires = TyreCheck._get_record('tcInspectedTyre', 'TyreId', lot.tyrecheck_id, '', token)
            query = "TyreId = '%s'" % (lot.tyrecheck_id,)
            inspected_tyre = TyreCheck._get_record('tcInspectedTyre', 'TyreId', '', query, token)
            tyre = TyreCheck._get_tyre(lot.tyrecheck_id,token=token)
            vehicle_tyre = TyreCheck._get_vehicle_tyre(tyre['LastVehicleTyreId'])
            vehicle_axle = TyreCheck._get_vehicle_axle(vehicle_tyre['VehicleAxleId'])
            print(tyre)
            print(vehicle_tyre)
            print(vehicle_axle)
            # vehicle_tyre = TyreCheck._get_vehicle_tyre('ed468950-0e87-4f91-ad7b-b99c4f5ffd54', token=token)
            # vehicle_axle = TyreCheck._get_vehicle_axle(vehicle_tyre['VehicleAxleId'], token=token)
            # vehicle = TyreCheck._get_vehicle(vehicle_axle['VehicleId'], token=token)
            current_vehicle = lot.tyrecheck_last_vehicle
            print(inspected_tyre['items'])
            for it in inspected_tyre['items']:
                vehicle_tyre = TyreCheck._get_record('tcVehicleTyre', 'VehicleTyreId', it['VehicleTyreId'], query,
                                                     token)
                vehicle_axle = TyreCheck._get_vehicle_axle(vehicle_tyre['VehicleAxleId'], token=token)
                vehicle = TyreCheck._get_vehicle(vehicle_axle['VehicleId'], token=token)

                if vehicle_axle['VehicleId'] == current_vehicle:
                    print('This is the same vehicle')
                else:
                    print('The vehicle has changed')
                    # Set this item to the current vehicle
                    current_vehicle = vehicle_axle['VehicleId']
                    # Get Tread Depth at time of change vehicle
                    query = "InspectionId = '%s' AND TyreId = '%s'" % (it['InspectionId'], lot.tyrecheck_id)
                    inspection = TyreCheck._get_record('tcInspectionMeasurement', 'InspectionMeasurementId', '', query,
                                                       token)
                    tread_depth_on_change = 0
                    if inspection['qty'] > 0:
                        for inspection_measurement in inspection['items']:
                            if inspection_measurement['InspectionMeasurementValue']['MeasurementType'] == 0:
                                tread_depth_on_change = inspection_measurement['InspectionMeasurementValue'][
                                    'DisplayValue']

                    if tread_depth_on_change < lot.tyrecheck_current_tread_depth:
                        # If decreased
                        difference = lot.tyrecheck_current_tread_depth - tread_depth_on_change
                        # Get value of difference
                        # Value per 1/32 inch = Current Value / Current Tread Depth
                        unit_value = lot.tyrecheck_value / lot.tyrecheck_current_tread_depth
                        value_of_decrease = unit_value * difference
                        print("New Expense is %s" % value_of_decrease)
                        print('New value is %s' % (lot.tyrecheck_value - value_of_decrease))
                # print(it['InspectionId'], vehicle['VehicleId'], inspection)

    @api.model
    def _create_vehicle_cost(self, amount, vehicle, tire_serial):
        """ This function creates the vehicle cost """

        VehicleCost = self.env['fleet.vehicle.cost']
        cost = VehicleCost.create({
            'vehicle_id': vehicle.id,
            'cost_subtype_id': self.env.company.tyrecheck_tread_depth_cost_type_id.id,
            'amount': amount
        })

        # Create Journal Entry
        move = False
        if self.env.company.tread_depth_expense_credit_account_id \
                and self.env.company.tread_depth_expense_debit_account_id \
                and self.env.company.tread_depth_expense_journal_id:
            AccountMove = self.env['account.move']
            move = AccountMove.create({
                'date': fields.Date.today(),
                'journal_id': self.env.company.tread_depth_expense_journal_id.id,
                'line_ids': [
                    (0, 0, {
                        'account_id': self.env.company.tread_depth_expense_credit_account_id.id,
                        'name': 'Tire / Serial: %s Tread Depth Expense' % (tire_serial.name,),
                        'credit': amount,
                    }),
                    (0, 0, {
                        'account_id': self.env.company.tread_depth_expense_debit_account_id.id,
                        'name': 'Tire / Serial: %s Tread Depth Expense' % (tire_serial.name,),
                        'debit': amount,
                    }),
                ]
            })

        return cost, move

    @api.model
    def _create_deferred_expense(self, amount, vehicle_id, tire_serial):
        """ This function creates the deferred expense """

        DeferredExpense = self.env['tyrecheck.deferred.expense']
        DeferredExpense.create({
            'amount': amount,
            'tyrecheck_vehicle_id': vehicle_id,
            'lot_id': tire_serial.id
        })

    def action_tyrecheck_sync(self):
        for lot in self:
            TyreCheck = self.env['tyrecheck']
            token = TyreCheck._get_token()
            tire_vals = {
                'tyrecheck_last_sync': fields.Datetime.now()
            }

            if not lot.tyrecheck_id:
                # Search in TyreCheck if the serial number is already in the system
                tires = TyreCheck._get_tyre(query="TyreSerialNumber = '%s'" % (lot.name.replace(' ', '\t'),),
                                            token=token)

                if tires['qty'] == 1:
                    tire = tires['items'][0]
                    tire_vals['tyrecheck_id'] = tire['TyreId']
                elif tires['qty'] > 1:
                    raise ValidationError(_('Serial is used on more than 1 Tire record in TyreCheck. '
                                            'Please check and resolve the issue in TyreCheck first.'))
                else:
                    # If no tire record found in TyreCheck, create a new Tire record.
                    tire = self._create_tyre(token=token)
                    if tire:
                        tire_vals['tyrecheck_id'] = tire['TyreId']
            else:
                tire = TyreCheck._get_tyre(lot.tyrecheck_id, token=token)

            tread_depth_decreased = False
            tread_depth_increased = False
            vehicle_changed = False
            last_vehicle_id = False
            vehicle_id = False
            vehicle = False
            odoo_vehicle = self.env['fleet.vehicle']
            # original_tread_depth = lot.tyrecheck_current_tread_depth

            # Only do additional processing, if the tire record is in TyreCheck
            if tire:
                # Update tread depth if changed
                current_tread_depth = tire['TyreAverageTreadDepth']
                if current_tread_depth != lot.tyrecheck_current_tread_depth:
                    # tire_vals['tyrecheck_current_tread_depth'] = current_tread_depth
                    if current_tread_depth and current_tread_depth > self.tyrecheck_current_tread_depth:
                        # Tread depth has increased, tire must increase in value
                        tread_depth_increased = True
                    elif current_tread_depth and current_tread_depth < self.tyrecheck_current_tread_depth:
                        # Tread depth has decreased, create corresponding expense
                        tread_depth_decreased = True

                vehicle_tyre_id = tire['LastVehicleTyreId']
                if vehicle_tyre_id:
                    vehicle_tyre = TyreCheck._get_vehicle_tyre(vehicle_tyre_id, token=token)
                    vehicle_axle = TyreCheck._get_vehicle_axle(vehicle_tyre['VehicleAxleId'], token=token)
                    vehicle = TyreCheck._get_vehicle(vehicle_axle['VehicleId'], token=token)
                    vehicle_id = vehicle_axle['VehicleId']
                    if self.tyrecheck_last_vehicle and self.tyrecheck_last_vehicle != vehicle['VehicleId']:
                        # Vehicle has changed
                        vehicle_changed = True
                        last_vehicle_id = self.tyrecheck_last_vehicle
                    # tire_vals['tyrecheck_last_vehicle'] = vehicle['VehicleId']
                    # tire_vals['tyrecheck_last_vehicle_tyre'] = tire['LastVehicleTyreId']

                lot.write(tire_vals)

                # Do updates depending on last information retrieved
                if tread_depth_decreased:
                    print("Processing for Tread Depth Decreased")

                    if vehicle:
                        print("Looking for Vehicle record in Odoo")
                        odoo_vehicle = self._get_fleet_vehicle(
                            vehicle['VehicleId'],
                            vehicle['VehicleRegistrationNumber'],
                            token=token
                        )

                    # Process tread depth decrease depending on if vehicle changed or not
                    if vehicle_changed:
                        print("Processing for vehicle changes")

                        # Get tyre inspections of the tire record
                        query = "TyreId = '%s'" % (lot.tyrecheck_id,)
                        inspected_tyre = TyreCheck._get_record('tcInspectedTyre', 'TyreId', '', query, token)
                        current_vehicle = lot.tyrecheck_last_vehicle

                        current_value = lot.tyrecheck_value
                        print("Current Value is %s" % current_value)

                        tread_depth_on_change = 0

                        # Iterate over all tire inspections
                        for it in inspected_tyre['items']:
                            vehicle_tyre = TyreCheck._get_record('tcVehicleTyre', 'VehicleTyreId', it['VehicleTyreId'],
                                                                 query, token)
                            vehicle_axle = TyreCheck._get_vehicle_axle(vehicle_tyre['VehicleAxleId'], token=token)
                            # vehicle = TyreCheck._get_vehicle(vehicle_axle['VehicleId'], token=token)

                            # Everytime vehicle changes, create necessary expenses if tread depth changed
                            if vehicle_axle['VehicleId'] != current_vehicle:
                                print('The vehicle has changed from "%s" to "%s"' % (current_vehicle, vehicle_axle['VehicleId']))

                                # Set this item to the current vehicle
                                current_vehicle = vehicle_axle['VehicleId']

                                # Get Tread Depth at time of change vehicle
                                query = "InspectionId = '%s' AND TyreId = '%s'" % (it['InspectionId'], lot.tyrecheck_id)
                                inspection = TyreCheck._get_record('tcInspectionMeasurement', 'InspectionMeasurementId',
                                                                   '',
                                                                   query, token)

                                if inspection['qty'] > 0:
                                    for inspection_measurement in inspection['items']:
                                        if inspection_measurement['InspectionMeasurementValue']['MeasurementType'] == 0:
                                            tread_depth_on_change = \
                                            inspection_measurement['InspectionMeasurementValue'][
                                                'DisplayValue']
                                print("Tread Depth on Change is %s" % tread_depth_on_change)
                                if tread_depth_on_change < lot.tyrecheck_current_tread_depth:
                                    # If decreased
                                    difference = lot.tyrecheck_current_tread_depth - tread_depth_on_change
                                    print("Tread Depth decreased by %s" % difference)
                                    # Get value of difference
                                    # Value per 1/32 inch = Current Value / Current Tread Depth
                                    unit_value = current_value / lot.tyrecheck_current_tread_depth
                                    value_of_decrease = unit_value * difference
                                    current_value = current_value - value_of_decrease
                                    print("Current Value after decrease is %s" % current_value)

                                    # Look for vehicle record
                                    odoo_vehicle = self._get_fleet_vehicle(current_vehicle)
                                    if odoo_vehicle:
                                        print("Creating vehicle cost")
                                        # Create expense records to the vehicle
                                        self._create_vehicle_cost(value_of_decrease, odoo_vehicle, lot)
                                    else:
                                        print("Creating deferred expense")
                                        # If no Odoo vehicle is found, create deferred record
                                        self._create_deferred_expense(value_of_decrease, current_vehicle, lot)
                        # Update current value
                        lot.write({
                            'tyrecheck_value': current_value,
                            'tyrecheck_current_tread_depth': tread_depth_on_change
                        })
                    else:
                        print("Processing for Same vehicle / No vehicle change")
                        difference = lot.tyrecheck_current_tread_depth - current_tread_depth
                        # Get value of difference
                        # Value per 1/32 inch = Current Value / Current Tread Depth
                        unit_value = lot.tyrecheck_value / lot.tyrecheck_current_tread_depth
                        value_of_decrease = unit_value * difference
                        current_value = lot.tyrecheck_value - value_of_decrease

                        if odoo_vehicle:
                            print("Creating vehicle cost")
                            # If vehicle did not change and tread depth has decreased
                            # and vehicle record is found
                            self._create_vehicle_cost(value_of_decrease, odoo_vehicle, lot)
                        else:
                            print("Creating deferred expense")
                            # If no vehicle record in Odoo is found, defer the expense to the vehicle
                            self._create_deferred_expense(value_of_decrease, vehicle_id, lot)

                        # Update current value
                        lot.write({
                            'tyrecheck_value': current_value,
                            'tyrecheck_current_tread_depth': current_tread_depth
                        })

                if tread_depth_increased:
                    # Update the tire value to accommodate the retreading
                    pass

    def action_view_deferred_expenses(self):
        self.ensure_one()
        action = self.env.ref('tf_peec_tyrecheck.action_tyrecheck_deferred_expense').read()[0]
        action['domain'] = [('lot_id', 'in', self.ids)]
        return action
