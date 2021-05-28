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
from odoo.exceptions import ValidationError


class PickingType(models.Model):
    _inherit = "stock.picking.type"

    is_internal_out = fields.Boolean("Is Internal Stock Transfer")

    def unlink(self):
        if self & (self.env.ref('tf_peec_stock.tf_peec_stock_transfer_type') +
                   self.env.ref('tf_peec_stock.tf_peec_stock_incoming_type')):
            raise ValidationError("You may not delete operation types 'Stock Transfer' and 'Incoming Stock' as they "
                                  "are part of an internal system process.")
        return super(PickingType, self).unlink()


class Picking(models.Model):
    _inherit = "stock.picking"

    is_internal_out = fields.Boolean(related='picking_type_id.is_internal_out')
    loc_internal_dest_id = fields.Many2one(
        'stock.location', "Internal Destination Location",
        default=lambda self: self.env.ref('stock.stock_location_stock', False),
        check_company=True, readonly=True, required=True,
        states={'draft': [('readonly', False)]},
        help="Destination location of the automatically generated incoming internal transfer."
    )
    incoming_picking_id = fields.Many2one(
        'stock.picking', "Incoming Transfer Counterpart",
        check_company=True, readonly=True, copy=False,
        help="Counterpart incoming internal transfer."
    )
    outgoing_picking_id = fields.Many2one(
        'stock.picking', "Outgoing Transfer Counterpart",
        check_company=True, readonly=True, copy=False,
        help="Counterpart outgoing internal transfer."
    )
    show_destination_warning = fields.Boolean('Show Destination Warning', store=True, compute='_compute_show_warning',
                                              compute_sudo=True)
    show_in_destination_warning = fields.Boolean('Show Internal Destination Warning', store=True,
                                                 compute='_compute_show_warning', compute_sudo=True)

    @api.depends('loc_internal_dest_id', 'location_id', 'location_dest_id', 'picking_type_id')
    def _compute_show_warning(self):
        for rec in self:
            location_id = rec.location_id
            if rec.picking_type_id.is_internal_out:
                if location_id == rec.location_dest_id:
                    rec.show_destination_warning = True
                else:
                    rec.show_destination_warning = False
                if location_id == rec.loc_internal_dest_id:
                    rec.show_in_destination_warning = True
                else:
                    rec.show_in_destination_warning = False
            else:
                rec.show_destination_warning = False
                rec.show_in_destination_warning = False

    def action_confirm(self):
        for rec in self:
            location_id = rec.location_id
            if rec.picking_type_id.is_internal_out and rec.picking_type_id.sequence_code == 'OUT-TRANSFER':
                if location_id == rec.location_dest_id or location_id == rec.loc_internal_dest_id:
                    raise ValidationError("Error: Source Location may not be the same with the Destination or "
                                          "Internal Destination Location.")

        return super(Picking, self).action_confirm()

    def create_incoming_picking(self):
        self.ensure_one()
        move_ids = []
        incoming_type_id = self.env.ref('tf_peec_stock.tf_peec_stock_incoming_type')
        location_id = self.location_dest_id.id
        location_dest_id = self.loc_internal_dest_id.id

        for move_id in self.move_ids_without_package:
            name = move_id.product_id._get_description(incoming_type_id)
            vals = {
                'name': name,
                'company_id': self.company_id,
                'picking_type_id': incoming_type_id.id,
                'location_id': location_id,
                'location_dest_id': location_dest_id,
                'product_id': move_id.product_id.id,
                'product_uom': move_id.product_uom,
                'product_uom_qty': move_id.product_uom_qty,
                'description_picking': name
            }
            move_ids.append((0, 0, vals))

        incoming_picking_id = self.create({
            'partner_id': self.partner_id,
            'scheduled_date': self.scheduled_date,
            'origin': self.name,
            'picking_type_id': self.env.ref('tf_peec_stock.tf_peec_stock_incoming_type').id,
            'location_id': location_id,
            'location_dest_id': location_dest_id,
            'outgoing_picking_id': self.id,
            'move_ids_without_package': move_ids
        })

        incoming_picking_id.action_confirm()
        incoming_picking_id.action_assign()
        self.incoming_picking_id = incoming_picking_id

    def button_validate(self):
        res = super(Picking, self).button_validate()
        origin = self.origin
        if self.is_internal_out and ((origin and "Return" not in origin) or not origin):
            self.create_incoming_picking()
        return res
