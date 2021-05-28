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


class DeliveryOrderState(models.Model):
    _name = 'logistics.delivery.order.state'
    _description = 'Delivery Order State'

    name = fields.Char()
    display = fields.Char()

    def name_get(self):
        return [(dos.id, dos.display) for dos in self]


class DashboardGroup(models.Model):
    _name = 'logistics.dashboard.group'
    _description = 'Dashboard Group'

    name = fields.Char('Group Name', copy=False, required=True, tracking=True, index=True)
    model = fields.Selection([('delivery_order', 'Delivery Order'), ('delivery_unit', 'Delivery Unit')],
                             default='delivery_order', index=True)
    at_locations = fields.Many2many('res.partner', string='At Locations')
    in_states = fields.Many2many('logistics.delivery.order.state', string='In States')
    is_under_repair = fields.Boolean('Under Repair')
    is_loaded = fields.Boolean('Loaded')
    is_unassigned = fields.Boolean('Unassigned')
    count = fields.Integer('Count', compute='_compute_count')

    def _search_filtered_records(self):
        search_domain = []

        if self.model == 'delivery_order':
            model = 'logistics.delivery.order'

            if self.at_locations:
                search_domain.append(('delivery_unit_id.location_id', 'in', self.at_locations.ids))
            if self.in_states:
                states = [state.name for state in self.in_states]
                search_domain.append(('state', 'in', states))

            if self.is_loaded:
                search_domain += [('is_cement_loaded', '=', True), ('is_cement_unloaded', '=', False)]

            if self.is_unassigned:
                search_domain += [('delivery_unit_id', '=', False)]

        else:
            model = 'logistics.delivery.unit'

            if self.at_locations:
                search_domain.append(('location_id', 'in', self.at_locations.ids))

            if self.in_states:
                states = [state.name for state in self.in_states]
                search_domain.append(('delivery_order_state', 'in', states))

            if self.is_loaded:
                search_domain += [('delivery_order_id.is_cement_loaded', '=', True), ('delivery_order_id.is_cement_unloaded', '=', False)]

            if self.is_unassigned:
                search_domain += [('delivery_order_id', '=', False)]

        records = self.env[model].search(search_domain)
        return records

    def _compute_count(self):
        for dg in self:
            records = dg._search_filtered_records()
            dg.count = len(records)

    def action_open_records(self):
        self.ensure_one()

        if self.model == 'delivery_order':
            action_external_id = 'tf_peec_logistics.action_logistics_delivery_order'
        else:
            action_external_id = 'tf_peec_logistics.action_logistics_delivery_unit'

        records = self._search_filtered_records()

        action = self.env.ref(action_external_id).read()[0]
        action['domain'] = [('id', 'in', records.ids)]
        return action
