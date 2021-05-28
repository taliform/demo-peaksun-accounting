# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2021 Taliform Inc.
#
# Author: Joshua <Joshua@taliform.com>
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


class MaintenanceRequest(models.Model):
    _name = "maintenance.request"
    _inherit = ['maintenance.request', 'portal.mixin']

    _TO_MAINTAIN_TYPES = [
        ('equipment', "Equipment"),
        ('vehicle', "Vehicle"),
        ('product', "Product"),
        ('others', "Others")
    ]
    equipment_id = fields.Many2one('maintenance.equipment', string='Equipment', track_visibility='onchange')
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', track_visibility='onchange')
    to_maintain = fields.Selection(_TO_MAINTAIN_TYPES, "To Maintain", help="", default="equipment")
    product_id = fields.Many2one('product.product', string='Product', track_visibility='onchange', required=False)
    prod_lot_serial_num = fields.Many2one('stock.production.lot', string='Product Lot / Serial Number',
                                          track_visibility='onchange')
    repair_order_ids = fields.One2many('repair.order', 'maintenance_request_id', 'Repair Order')
    repair_order_count = fields.Integer('Repair Orders Count', compute="_get_repair_count", store=True)
    can_create_repair_order = fields.Boolean(compute="_can_create_repair_order", store=True)

    def archive_equipment_request(self):
        cancel_stage = self.env['maintenance.stage'].search([('cancel', '=', True)], limit=1)
        if not cancel_stage:
            raise ValidationError(_('Please set up a Request Cancelled stage in Maintenance Stages Configuration.'))
        self.write({'archive': True, 'stage_id': cancel_stage.id})

    def action_create_repair_order(self):
        RepairOrder = self.env['repair.order']
        sequence_obj = self.env['ir.sequence']
        for rec in self:
            order_vals = {
                'name': sequence_obj.next_by_code('repair.order'),
                'maintenance_request_id': rec.id,
                'equipment_id': rec.equipment_id.id,
                'vehicle_id': rec.vehicle_id.id,
                'product_id': rec.product_id.id,
                'to_repair': rec.to_maintain,
                'state': 'draft'
            }
            repair_order = RepairOrder.create(order_vals)

            # Open the repair order
            form_view_id = self.env.ref('repair.view_repair_order_form').id
            return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'repair.order',
                'res_id': repair_order.id,
                'views': [(form_view_id, 'form')],
                'type': 'ir.actions.act_window',
                'target': 'current',
            }

    def action_view_repair_orders(self):
        tree_view_id = self.env.ref('repair.view_repair_order_tree').id
        form_view_id = self.env.ref('repair.view_repair_order_form').id
        title = 'Repair Orders'
        return {
            'name': title,
            'view_type': 'form',
            'view_mode': 'tree, form',
            'res_model': 'repair.order',
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.repair_order_ids.ids)],
            'target': 'current',
        }

    def write(self, vals):
        res = super(MaintenanceRequest, self).write(vals)
        if 'stage_id' in vals:
            self._can_create_repair_order()
            stage = self.env['maintenance.stage'].browse(vals['stage_id'])
            for rec in self:
                if rec.to_maintain == 'vehicle':
                    maintenance_stage = rec.stage_id
                    vehicle_id = rec.vehicle_id
                    if maintenance_stage.repair_order_stage:
                        repair_ids = rec.repair_order_ids
                        for repair_id in repair_ids:
                            repair_id.write({
                                'state': maintenance_stage.repair_order_stage
                            })
                    if maintenance_stage.vehicle_status:
                        vehicle_id.write({
                            'state_id': maintenance_stage.vehicle_status
                        })
                    if stage.done:
                        vehicle_id.write({
                            'est_next_preventive_maintenance_distance': vehicle_id.preventive_maintenance_distance + vehicle_id.odometer
                        })
        return res

    @api.depends('repair_order_ids')
    def _get_repair_count(self):
        for rec in self:
            rec.repair_order_count = len(rec.repair_order_ids)

    @api.depends('stage_id')
    def _can_create_repair_order(self):
        for rec in self:
            rec.can_create_repair_order = True
            if rec.stage_id.done:
                rec.can_create_repair_order = False


class MaintenanceStage(models.Model):
    _inherit = "maintenance.stage"

    _REPAIR_ORDER_STAGES = [
        ('quotation', 'Quotation'),
        ('cancelled', 'Cancelled'),
        ('confirmed', 'Confirmed'),
        ('under_repair', 'Under Repair'),
        ('ready', 'Ready to Repair'),
        ('2binvoiced', 'To Be Invoiced'),
        ('invoice_except', 'Invoice Exception'),
        ('done', 'Repaired')
    ]
    repair_order_stage = fields.Selection(_REPAIR_ORDER_STAGES, "Repair Order Stage", help="", default="")
    vehicle_status = fields.Many2one('fleet.vehicle.state', string="Vehicle Status")
    cancel = fields.Boolean('Request Cancelled')
