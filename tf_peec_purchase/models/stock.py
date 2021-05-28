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
from odoo.exceptions import ValidationError, RedirectWarning
from odoo.tools.float_utils import float_compare, float_is_zero


class StockProductionLot(models.Model):
    _inherit = "stock.production.lot"

    tire_services_ids = fields.One2many('purchase.order.line', 'serial_id', readonly=True,
                                        help="Indicates the purchase orders lines where the lot / serial number was "
                                             "referenced (for tire services).")

    tire_services_count = fields.Integer("Tire Services Count", compute='_compute_tire_services_count', store=True)

    @api.depends('tire_services_ids')
    def _compute_tire_services_count(self):
        for rec in self:
            rec.tire_services_count = len(rec.tire_services_ids)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def process_requests(self):
        for rec in self.move_lines:
            if not float_is_zero(rec.quantity_done, precision_rounding=rec.product_uom.rounding):
                compare = float_compare(rec.quantity_done, rec.product_uom_qty,
                                        precision_rounding=rec.product_uom.rounding)
                if compare > -1:
                    rec.purchase_line_id.request_line_ids.action_delivered()
                    # if purchase line came directly from purchase request
                    cs_line_id = rec.purchase_line_id.cs_line_id
                    # if purchase line came through canvass sheet
                    if cs_line_id.po_line_ids.mapped('order_id').filtered(lambda o: not o.is_shipped):
                        rec.purchase_line_id.request_line_ids.action_partial()
                    else:
                        cs_line_id.request_line_ids.action_delivered()
                else:
                    rec.purchase_line_id.request_line_ids.action_partial()
                    rec.purchase_line_id.cs_line_id.request_line_ids.action_partial()

    def button_validate(self):
        res = super(StockPicking, self).button_validate()
        self.process_requests()
        return res


class StockImmediateTransfer(models.TransientModel):
    _inherit = 'stock.immediate.transfer'

    def process(self):
        res = super(StockImmediateTransfer, self).process()
        for picking in self.pick_ids:
            picking.process_requests()
        return res
