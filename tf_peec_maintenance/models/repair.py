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


class RepairOrder(models.Model):
    _inherit = "repair.order"

    _TO_REPAIR_TYPES = [
        ('equipment', "Equipment"),
        ('vehicle', "Vehicle"),
        ('product', "Product"),
        ('others', "Others")
    ]

    def _get_code_key_14(self):
        key = int(self.env['ir.config_parameter'].sudo().get_param('tf_peec_maintenance.vmrs_code_key_14_id'))
        return [('code_key_id', '=', key)]

    to_repair = fields.Selection(_TO_REPAIR_TYPES, "To Repair", help="", default="product")
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', track_visibility='onchange')
    equipment_id = fields.Many2one('maintenance.equipment', string='Equipment', track_visibility='onchange')
    installation_loc = fields.Many2one('stock.location', string='Installation Location', track_visibility='onchange')
    maintenance_request_id = fields.Many2one('maintenance.request', string='Maintenance Request')

    product_uom = fields.Many2one(
        'uom.uom', 'Product Unit of Measure',
        readonly=True, required=False, states={'draft': [('readonly', False)]},
        domain="[('category_id', '=', product_uom_category_id)]")
    product_id = fields.Many2one(
        'product.product', string='Product',
        readonly=True, required=False, states={'draft': [('readonly', False)]})
    partner_id = fields.Many2one('res.partner', string='Partner')
    reason_for_repair_id = fields.Many2one('vmrs.code', string='Reason for Repair', domain=_get_code_key_14, copy=False)
    operations = fields.One2many(
        'repair.line', 'repair_id', 'Parts',
        copy=True, readonly=True, states={'draft': [('readonly', False)], 'confirmed': [('readonly', False)],
                                          'under_repair': [('readonly', False)]})
    fees_lines = fields.One2many(
        'repair.fee', 'repair_id', 'Operations',
        copy=True, readonly=True, states={'draft': [('readonly', False)], 'confirmed': [('readonly', False)],
                                          'under_repair': [('readonly', False)]})

    @api.onchange('maintenance_request_id')
    def _onchange_maintenance_request_id(self):
        for rec in self:
            mr = rec.maintenance_request_id
            if mr:
                rec.to_repair = mr.to_maintain
                rec.product_id = mr.product_id
                rec.vehicle_id = mr.vehicle_id
                rec.equipment_id = mr.equipment_id

    def action_repair_start(self):
        res = super(RepairOrder, self).action_repair_start()
        StockMove = self.env['stock.move']
        maintenance_stage = self.env['maintenance.stage'].search([('repair_order_stage', '=', 'under_repair')], limit=1)

        for rec in self:
            if rec.to_repair == "vehicle":
                rec.maintenance_request_id.write({
                    "stage_id": maintenance_stage.id
                })
            for repair_line in rec.operations:
                stock_move_vals = {
                    'origin': rec.name,
                    'product_id': repair_line.product_id.id,
                    'location_id': repair_line.location_id.id,
                    'location_dest_id': repair_line.location_dest_id.id,
                    'name': repair_line.name,
                    'product_uom': repair_line.product_uom.id,
                    'product_uom_qty': repair_line.product_uom_qty,
                    'state': 'done'
                }
                StockMove.create(stock_move_vals)
        return res

    def action_validate(self):
        for rec in self:
            if rec.to_repair != 'product':
                if rec.state == 'draft' and rec.invoice_method == 'b4repair':
                    rec.state = '2binvoiced'
                else:
                    rec.state = 'confirmed'
            else:
                return super(RepairOrder, self).action_validate()

    def action_repair_end(self):
        StockMove = self.env['stock.move']
        maintenance_stage = self.env['maintenance.stage'].search([('repair_order_stage', '=', 'done')], limit=1)
        for rec in self:
            if rec.to_repair == 'vehicle':
                rec.maintenance_request_id.write({
                    "stage_id": maintenance_stage.id
                })
            for repair_line in rec.operations:
                stock_move_vals = {
                    'origin': rec.name,
                    'product_id': repair_line.product_id.id,
                    'location_id': repair_line.location_id.id,
                    'location_dest_id': rec.installation_loc.id,
                    'name': repair_line.name,
                    'product_uom': repair_line.product_uom.id,
                    'product_uom_qty': repair_line.product_uom_qty,
                    'state': 'done'
                }
                StockMove.create(stock_move_vals)
            if rec.to_repair != 'product':
                if rec.state == 'under_repair' and rec.invoice_method == 'after_repair':
                    rec.state = '2binvoiced'
                else:
                    rec.state = 'done'
            else:
                return super(RepairOrder, self).action_repair_end()


class RepairLine(models.Model):
    _inherit = 'repair.line'

    @api.onchange('type', 'repair_id')
    def onchange_operation_type(self):
        """ On change of operation type it sets source location, destination location
        and to invoice field.
        @param product: Changed operation type.
        @param guarantee_limit: Guarantee limit of current record.
        @return: Dictionary of values.
        """
        if not self.type:
            self.location_id = False
            self.location_dest_id = False
        elif self.type == 'add':
            self.onchange_product_id()
            args = self.repair_id.company_id and [('company_id', '=', self.repair_id.company_id.id)] or []
            warehouse = self.env['stock.warehouse'].search(args, limit=1)
            self.location_id = warehouse.lot_stock_id
            self.location_dest_id = self.repair_id.installation_loc.id
        else:
            self.price_unit = 0.0
            self.tax_id = False
            self.location_id = self.repair_id.installation_loc.id
            self.location_dest_id = self.env['stock.location'].search([('scrap_location', '=', True)], limit=1).id

    # Overwrite _onchange_product_uom to retrieve Cost price instead of public price
    @api.onchange('product_uom')
    def _onchange_product_uom(self):
        partner = self.repair_id.partner_id
        pricelist = self.repair_id.pricelist_id
        if partner:
            if pricelist and self.product_id and self.type != 'remove':
                price = pricelist.get_product_price(self.product_id, self.product_uom_qty, partner, uom_id=self.product_uom.id)
                if price is False:
                    warning = {
                        'title': _('No valid pricelist line found.'),
                        'message':
                            _("Couldn't find a pricelist line matching this product and quantity.\nYou have to change either the product, the quantity or the pricelist.")}
                    return {'warning': warning}
                else:
                    self.price_unit = price
        elif self.product_id and self.type != 'remove':
            self.price_unit = self.product_id.standard_price
        else:
            self.price_unit = 0


class RepairFee(models.Model):
    _inherit = 'repair.fee'

    def _get_code_key_15(self):
        key = int(self.env['ir.config_parameter'].sudo().get_param('tf_peec_maintenance.vmrs_code_key_15_id'))
        return [('code_key_id', '=', key)]

    def _get_code_key_18(self):
        key = int(self.env['ir.config_parameter'].sudo().get_param('tf_peec_maintenance.vmrs_code_key_18_id'))
        return [('code_key_id', '=', key)]

    def _get_code_key_34(self):
        key = int(self.env['ir.config_parameter'].sudo().get_param('tf_peec_maintenance.vmrs_code_key_34_id'))
        return [('code_key_id', '=', key)]

    work_accomplished_id = fields.Many2one('vmrs.code', string='Work Accomplished', domain=_get_code_key_15, copy=False)
    failure_code_id = fields.Many2one('vmrs.code', string='Failure Code', domain=_get_code_key_18, copy=False)
    system_lvl_id = fields.Many2one('vmrs.code', string='System Level', copy=False)
    assembly_lvl_id = fields.Many2one('vmrs.code', string="Assembly Level", copy=False)
    component_lvl_id = fields.Many2one('vmrs.code', string="Component Level", copy=False)
    supplier_iden_id = fields.Many2one('vmrs.code', string="Brand ID", domain=_get_code_key_34, copy=False)

    @api.constrains('assembly_lvl_id', 'component_lvl_id')
    def _check_assembly_component_lvl_ids(self):
        for rec in self:
            if rec.system_lvl_id:
                if rec.assembly_lvl_id.parent_id != rec.system_lvl_id:
                    raise ValidationError(_('Assembly Level selected not child of System Level.'))
                if rec.component_lvl_id.parent_id != rec.assembly_lvl_id:
                    raise ValidationError(_('Component Level selected not child of Assembly Level.'))

    @api.onchange('product_id')
    def _onchange_product_id(self):
        self.work_accomplished_id = self.product_id.work_accomplished_id

        system_lvl_key = int(self.env['ir.config_parameter'].sudo().get_param('tf_peec_maintenance.vmrs_code_key_31_id'))
        assembly_lvl_key = int(self.env['ir.config_parameter'].sudo().get_param('tf_peec_maintenance.vmrs_code_key_32_id'))
        component_lvl_key = int(self.env['ir.config_parameter'].sudo().get_param('tf_peec_maintenance.vmrs_code_key_33_id'))

        return {'domain': {
            'system_lvl_id': [('code_key_id', '=', system_lvl_key)],
            'assembly_lvl_id': [('code_key_id', '=', assembly_lvl_key)],
            'component_lvl_id': [('code_key_id', '=', component_lvl_key)],
        }}

    @api.onchange('system_lvl_id')
    def _onchange_system_lvl_id(self):
        self.ensure_one()
        key = int(self.env['ir.config_parameter'].sudo().get_param('tf_peec_maintenance.vmrs_code_key_32_id'))
        self.assembly_lvl_id = False
        self.component_lvl_id = False
        return {'domain': {'assembly_lvl_id': [('code_key_id', '=', key), ('id', 'child_of', self.system_lvl_id.id)]}}

    @api.onchange('assembly_lvl_id')
    def _onchange_assembly_lvl_id(self):
        self.ensure_one()
        key = int(self.env['ir.config_parameter'].sudo().get_param('tf_peec_maintenance.vmrs_code_key_33_id'))
        self.component_lvl_id = False
        return {'domain': {'component_lvl_id': [('code_key_id', '=', key), ('id', 'child_of', self.assembly_lvl_id.id)]}}


class RepairOrderFailureCode(models.Model):
    _name = 'repair.order.failure'
    _description = 'Repair Order Failure Code'

    repair_order_id = fields.Many2one('repair.order', string='Repair Order')
    part = fields.Many2one('product.product', string='Part')
    lot_serial_num = fields.Many2one('stock.production.lot', string='Lot / Serial Number')
    failure_codes = fields.Many2many('vmrs.code', string='Failure Codes', copy=False)
