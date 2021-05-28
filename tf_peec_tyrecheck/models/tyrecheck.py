import logging

import requests
from werkzeug.urls import url_encode

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TyreCheck(models.AbstractModel):
    _name = 'tyrecheck'
    _description = 'TyreCheck'

    name = fields.Char('Name')
    tyrecheck_id = fields.Char('TyreCheck ID')

    @api.constrains('tyrecheck_id')
    def _check_tyrecheck_id(self):
        for rec in self:
            if rec.tyrecheck_id and rec.search_count([('tyrecheck_id', '=', rec.tyrecheck_id)]) > 1:
                raise ValidationError(_('TyreCheck ID is already used in a different %s.' % (self._description,)))

    def _get_token(self, host=False, username=False, password=False):
        """ This function is used to get the authorization token. """
        if not host:
            host = self.env.company.tyrecheck_host
        if not username:
            username = self.env.company.tyrecheck_username
        if not password:
            password = self.env.company.tyrecheck_password

        data = {
            'grant_type': 'password',
            'username': username,
            'password': password
        }

        host = "%s/api/token" % (host,)
        response = requests.post(host, data=data)

        if response.status_code == 200:
            response_json = response.json()
            token = response_json['access_token']
        else:
            raise ValidationError(_('Error retrieving TyreCheck Authorization Token.'))

        return token

    def _get_record(self, resource_name, resource_id_name, record_id='', query='', token=''):
        # if not record_id and not query:
        #     raise ValidationError(_('At least one of either Record ID or TQL Query must be provided.'))

        if record_id:
            # Overwrite query since providing TyreId always results in 1 record.
            query = "%s = '%s'" % (resource_id_name, record_id,)

        # Build request URL
        host = "%s/api/api/%s" % (self.env.company.tyrecheck_host, resource_name)
        params = {
            'getQty': True,
            'query': query
        }
        host = "%s?%s" % (host, url_encode(params))

        # Include token to header
        if not token:
            token = self._get_token()
        headers = {'Authorization': 'Bearer %s' % (token,)}

        # Execute request
        response = requests.get(host, headers=headers)
        if response.status_code == 200:
            response_json = response.json()
        else:
            _logger.error("Error %s:\n%s" % (response.status_code, response.text))
            raise ValidationError(_('Error retrieving TyreCheck %s Records.') % (resource_name,))

        if response_json['qty'] == 1 and record_id:
            return response_json['items'][0]

        return response_json

    def _get_tyre(self, tyre_id='', query='', token=''):
        """ This function retrieves the tcTyre record using provided TyreId (tyre_id) or a TQL query (query)."""
        return self._get_record('tcTyre', 'TyreId', tyre_id, query, token)

    def _get_vehicle_tyre(self, vehicle_tyre_id='', query='', token=''):
        """ This function retrieves the tcVehicleTyre record using
        provided VehicleTyreId (vehicle_tyre_id) or a TQL query (query)."""
        return self._get_record('tcVehicleTyre', 'VehicleTyreId', vehicle_tyre_id, query, token)

    def _get_vehicle_axle(self, vehicle_axle_id='', query='', token=''):
        """ This function retrieves the tcVehicleTyre record using
        provided VehicleAxleId (vehicle_axle_id) or a TQL query (query)."""
        return self._get_record('tcVehicleAxle', 'VehicleAxleId', vehicle_axle_id, query, token)

    def _get_vehicle(self, vehicle_id='', query='', token=''):
        """ This function retrieves the tcVehicle record using
        provided VehicleId (vehicle_id) or a TQL query (query)."""
        return self._get_record('tcVehicle', 'VehicleId', vehicle_id, query, token)

    def _get_product(self, product_id='', query='', token=''):
        """ This function retrieves the tcProduct record using
        provided ProductId (product_id) or a TQL query (query)."""
        return self._get_record('tcProduct', 'ProductId', product_id, query, token)

    def _get_service_center(self, service_center_id='', query='', token=''):
        """ This function retrieves the tcServiceCenter record using
        provided ServiceCenterId (service_center_id) or a TQL query (query)."""
        return self._get_record('tcServiceCenter', 'ServiceCenterId', service_center_id, query, token)

    def _get_company(self, company_id='', query='', token=''):
        """ This function retrieves the tcCompany record using
        provided CompanyId (company_id) or a TQL query (query)."""
        return self._get_record('tcCompany', 'SecurityLevelId', company_id, query, token)

    def _action_update(self, get_function, name_key, id_key, token=''):
        _logger.info(_('Updating %s') % (self._name,))
        if not token:
            token = self._get_token()
        records = getattr(self, get_function)(token=token)
        if records['qty'] > 0:
            # Delete all records
            self.search([]).unlink()
            record_vals = []
            for record in records['items']:
                record_vals.append({
                    'name': record[name_key],
                    'tyrecheck_id': record[id_key]
                })
            self.create(record_vals)


class TyreCheckTire(models.Model):
    _name = 'tyrecheck.tire'
    _description = 'TyreCheck Tire'
    _inherit = 'tyrecheck'

    def action_update(self, token=''):
        self._action_update('_get_tyre', 'TyreSerialNumber', 'TyreId', token=token)


class TyreCheckProduct(models.Model):
    _name = 'tyrecheck.product'
    _description = 'TyreCheck Product'
    _inherit = 'tyrecheck'

    def action_update(self, token=''):
        self._action_update('_get_product', 'ProductName', 'ProductId', token=token)


class TyreCheckVehicle(models.Model):
    _name = 'tyrecheck.vehicle'
    _description = 'TyreCheck Vehicle'
    _inherit = 'tyrecheck'

    def action_update(self, token=''):
        self._action_update('_get_vehicle', 'VehicleRegistrationNumber', 'VehicleId', token=token)


class TyreCheckServiceCenter(models.Model):
    _name = 'tyrecheck.service.center'
    _description = 'TyreCheck Service Center'
    _inherit = 'tyrecheck'

    def action_update(self, token=''):
        self._action_update('_get_service_center', 'ServiceCenterName', 'ServiceCenterId', token=token)


class TyreCheckCompany(models.Model):
    _name = 'tyrecheck.company'
    _description = 'TyreCheck Company'
    _inherit = 'tyrecheck'

    def action_update(self, token=''):
        self._action_update('_get_company', 'SecurityLevelName', 'SecurityLevelId', token=token)

    def action_update_all(self):
        token = self.env['tyrecheck']._get_token()
        self.env['tyrecheck.tire'].action_update(token=token)
        self.env['tyrecheck.company'].action_update(token=token)
        self.env['tyrecheck.service.center'].action_update(token=token)
        self.env['tyrecheck.product'].action_update(token=token)
        self.env['tyrecheck.vehicle'].action_update(token=token)


class TyreCheckDeferredExpense(models.Model):
    _name = 'tyrecheck.deferred.expense'
    _description = 'TyreCheck Deferred Expense'

    lot_id = fields.Many2one('stock.production.lot', 'Tire Serial')
    amount = fields.Float()
    posted = fields.Boolean()
    tyrecheck_vehicle_id = fields.Char('TyreCheck Vehicle')
    cost_id = fields.Many2one('fleet.vehicle.cost', 'Vehicle Cost')
    move_id = fields.Many2one('account.move', 'Journal Entry')

    def action_post_expense(self):
        for expense in self:
            print('hello')

            # Get vehicle record
            Lot = self.env['stock.production.lot']

            vehicle = Lot._get_vehicle(expense.tyrecheck_vehicle_id)
            if vehicle:
                expense_vals = {
                    'posted': True
                }

                VehicleCost = self.env['fleet.vehicle.cost']
                cost = VehicleCost.create({
                    'vehicle_id': vehicle.id,
                    'cost_subtype_id': self.env.company.tyrecheck_tread_depth_cost_type_id.id,
                    'amount': expense.amount,
                })

                expense_vals['cost_id'] = cost.id

                # Create Journal Entry
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
                                'name': 'Tire / Serial: %s Tread Depth Expense' % (expense.lot_id.name,),
                                'credit': expense.amount,
                            }),
                            (0, 0, {
                                'account_id': self.env.company.tread_depth_expense_debit_account_id.id,
                                'name': 'Tire / Serial: %s Tread Depth Expense' % (expense.lot_id.name,),
                                'debit': expense.amount,
                            }),
                        ]
                    })
                    expense_vals['move_id'] = move.id

                expense.write(expense_vals)
