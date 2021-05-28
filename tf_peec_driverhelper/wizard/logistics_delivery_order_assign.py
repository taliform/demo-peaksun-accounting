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
from odoo import fields, models, _
from odoo.exceptions import ValidationError


class DeliveryOrderAssign(models.TransientModel):
    _inherit = 'logistics.delivery.order.assign'

    req_plant_ids = fields.Many2many('res.partner', string='Plant Accreditations')
    req_doc_ids = fields.Many2many('tf.hr.logistic_doc.type', string='Documents Required')
    req_license_ids = fields.Many2many('tf.hr.license.type', string='Licenses Required')
    req_truck_ids = fields.Many2many('fleet.vehicle.model', string='Allowed Trucks')
    req_plant_driver = fields.Boolean('Plant Accreditations Driver')
    req_plant_helper = fields.Boolean('Plant Accreditations Helper')
    req_doc_driver = fields.Boolean('Documents Required Driver')
    req_doc_helper = fields.Boolean('Documents Required Helper')
    req_license_driver = fields.Boolean('Licenses Required Driver')
    req_license_helper = fields.Boolean('Licenses Required Helper')
    req_truck_driver = fields.Boolean('Allowed Trucks Driver')
    req_truck_helper = fields.Boolean('Allowed Trucks Helper')
    qualified_ids = fields.Many2many('logistics.delivery.unit', string='Qualified Delivery Units')
    searched = fields.Boolean()

    def action_assign(self):
        self.ensure_one()
        if self.delivery_unit_id:
            if self.delivery_order_id.delivery_unit_id:
                self.delivery_order_id.delivery_unit_id.write({'delivery_order_id': False})

            # if self.delivery_unit_id.delivery_order_id:
            #     raise ValidationError(_('The selected Delivery Unit currently has a Delivery Order assigned to it. '
            #                             'Please re-open the wizard to get the latest available Delivery Units.'))

            if self._context.get('action', False) == 'assign':
                self.delivery_order_id.write({
                    'delivery_unit_id': self.delivery_unit_id.id,
                    'state': 'assigned'
                })
            else:
                self.delivery_order_id.delivery_unit_id = self.delivery_unit_id

            self.delivery_unit_id.write({
                'delivery_order_id': self.delivery_order_id.id
            })

    def action_search(self):
        self.ensure_one()

        Employee = self.env['hr.employee']
        DeliveryUnit = self.env['logistics.delivery.unit']
        PlantAccreditation = self.env['tf.hr.plant.accreditation']
        DocAccreditation = self.env['tf.hr.doc.accreditation']
        LicenseAccreditation = self.env['tf.hr.license.accreditation']

        # Search employees with accreditations to specified plants
        plants_accredited = []
        for req_plant in self.req_plant_ids:
            # Each plant will have its own accredited employees
            plants_accredited.append(
                PlantAccreditation.search([
                    ('status', '=', 'accredited'),
                    ('plant_id', '=', req_plant.id)
                ]).mapped('employee_id')
            )
        # Search employees with accreditations to specified docs
        docs_accredited = []
        for req_doc in self.req_doc_ids:
            # Each doc will have its own accredited employees
            docs_accredited.append(
                DocAccreditation.search([
                    ('status', '=', 'active'),
                    ('type_id', '=', req_doc.id)
                ]).mapped('employee_id')
            )
        # Search employees with specified licenses
        licenses_accredited = []
        for req_license in self.req_license_ids:
            # Each license will have its own accredited employees
            licenses_accredited.append(
                LicenseAccreditation.search([
                    ('status', '=', 'active'),
                    ('type_id', '=', req_license.id)
                ]).mapped('employee_id')
            )
        available_units = DeliveryUnit.search([
            '|',
            ('delivery_order_id', '=', False),
            '&',
            ('delivery_order_id', '!=', False), ('delivery_order_state', 'in', ['unloaded', 'validation'])
        ])

        # Get qualified units
        qualified_units = DeliveryUnit
        plant_units = doc_units = license_units = DeliveryUnit
        criteria_units = []

        for unit in available_units:
            # Check for plant accreditation
            if self.req_plant_driver or self.req_plant_helper:
                plant_driver_checked = False
                plant_helper_checked = False
                for plant in plants_accredited:
                    # Check if drivers are qualified in plant
                    if self.req_plant_driver and unit.driver_ids in plant:
                        plant_driver_checked = True
                    elif not self.req_plant_driver:
                        plant_driver_checked = True
                    else:
                        plant_driver_checked = False

                    # Check if helpers are qualified in plant
                    if self.req_plant_helper and unit.helper_ids in plant:
                        plant_helper_checked = True
                    elif not self.req_plant_helper:
                        plant_helper_checked = True
                    else:
                        plant_helper_checked = False

                if plant_driver_checked and plant_helper_checked:
                    plant_units += unit

            # Check for doc accreditation
            if self.req_doc_driver or self.req_doc_helper:
                doc_driver_checked = False
                doc_helper_checked = False
                for doc in docs_accredited:
                    # Check if drivers are qualified in plant
                    if self.req_doc_driver and unit.driver_ids in doc:
                        doc_driver_checked = True
                    elif not self.req_doc_driver:
                        doc_driver_checked = True
                    else:
                        doc_driver_checked = False

                    # Check if helpers are qualified in plant
                    if self.req_doc_helper and unit.helper_ids in doc:
                        doc_helper_checked = True
                    elif not self.req_doc_helper:
                        doc_helper_checked = True
                    else:
                        doc_helper_checked = False

                if doc_driver_checked and doc_helper_checked:
                    doc_units += unit

            # Check for license accreditation
            if self.req_license_driver or self.req_license_helper:
                license_driver_checked = False
                license_helper_checked = False
                for license in licenses_accredited:
                    # Check if drivers are qualified in plant
                    if self.req_license_driver and unit.driver_ids in license:
                        license_driver_checked = True
                    elif not self.req_license_driver:
                        license_driver_checked = True
                    else:
                        license_driver_checked = False

                    # Check if helpers are qualified in plant
                    if self.req_license_helper and unit.helper_ids in license:
                        license_helper_checked = True
                    elif not self.req_license_helper:
                        license_helper_checked = True
                    else:
                        license_helper_checked = False

                if license_driver_checked and license_helper_checked:
                    license_units += unit

        if not self.req_plant_driver and not self.req_plant_helper \
                and not self.req_doc_driver and not self.req_doc_helper \
                and not self.req_license_driver and not self.req_license_helper \
                and not self.req_truck_driver and not self.req_truck_helper:
            # If no criteria is selected
            qualified_units = available_units.sorted(key=lambda u: u.state)
        else:
            # Get the intersection of all found units
            if self.req_plant_driver or self.req_plant_helper:
                criteria_units.append(plant_units)
            if self.req_doc_driver or self.req_doc_helper:
                criteria_units.append(doc_units)
            if self.req_license_driver or self.req_license_helper:
                criteria_units.append(license_units)
            if criteria_units:
                qualified_units = criteria_units[0]
                for unit in criteria_units:
                    qualified_units = qualified_units & unit
                    qualified_units = qualified_units.sorted(key=lambda u: u.state)

        view_id = self.env.ref('tf_peec_logistics.logistics_delivery_order_assign_view_form').id
        context = dict(self._context)
        context.update({
            'default_delivery_order_id': self.delivery_order_id.id or False,
            'default_delivery_unit_id': self.delivery_unit_id.id or False,
            'default_req_plant_ids': self.req_plant_ids.ids,
            'default_req_doc_ids': self.req_doc_ids.ids,
            'default_req_license_ids': self.req_license_ids.ids,
            'default_req_truck_ids': self.req_truck_ids.ids,
            'default_req_plant_driver': self.req_plant_driver,
            'default_req_plant_helper': self.req_plant_helper,
            'default_req_doc_driver': self.req_doc_driver,
            'default_req_doc_helper': self.req_doc_helper,
            'default_req_license_driver': self.req_license_driver,
            'default_req_license_helper': self.req_license_helper,
            'default_req_truck_driver': self.req_truck_driver,
            'default_req_truck_helper': self.req_truck_helper,
            'default_qualified_ids': qualified_units.ids,
            'default_searched': True,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Search Delivery Unit'),
            'res_model': 'logistics.delivery.order.assign',
            'view_mode': 'form',
            'views': [[view_id, 'form']],
            'target': 'new',
            'context': context,
        }
