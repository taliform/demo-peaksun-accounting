# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2021 Taliform Inc.
#
# Author: Ana Trajano <ana@taliform.com>
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
from odoo.exceptions import UserError, ValidationError


class SaleOffhire(models.Model):
    _name = 'sale.offhire'
    _description = "Sale Offhire"
    _rec_name = 'description'

    @api.depends('so_line_id', 'so_id.order_line')
    def _check_so_line(self):
        for rec in self:
            rec.added = False
            if rec.so_line_id:
                rec.added = True

    @api.constrains('lt_hrs', 'miss_hrs', 'mnt_privilege', 'offhire_rate')
    def _verify_hrs(self):
        for rec in self:
            if rec.lt_hrs and rec.lt_hrs < 0.0:
                raise ValidationError(_('The indicated late hours should not be negative.'))
            if rec.miss_hrs and rec.miss_hrs < 0.0:
                raise ValidationError(_('The indicated missing hours should not be negative.'))
            if rec.mnt_privilege and rec.mnt_privilege < 0.0:
                raise ValidationError(_('The indicated maintenance privilege should not be negative.'))
            if rec.offhire_rate and rec.offhire_rate < 0.0:
                raise ValidationError(_('The indicated offhire rate should not be negative.'))

    so_id = fields.Many2one('sale.order', 'Sales Order', ondelete='cascade', copy=False,
                            help="Indicates the Sales Order related to the offhire record")
    so_line_id = fields.Many2one('sale.order.line', 'Sales Order Line', copy=False)
    do_id = fields.Many2one('logistics.delivery.order', 'Delivery Order', copy=False,
                            help="Indicates the Delivery Order related to the offhire record")
    do_unit_id = fields.Many2one('logistics.delivery.unit', 'Delivery Unit', copy=False,
                                 help="Indicates the Delivery Unit related to the offhire record")
    lt_hrs = fields.Float('Late Hours', help="Indicates the recorded late hours")
    miss_hrs = fields.Float('Missing Hours', help="Indicates the missing hours")
    offhire_rate = fields.Float('Offhire Rate', help="Indicates the rate to be added in the order line")
    mnt_privilege = fields.Float('Maintenance Privilege', copy=False,
                                 help="Indicates the number of hours to use as maintenance privilege, "
                                      "which will be consumed when offhire records are recognized in the Sales Order")
    description = fields.Char(copy=False, help="Indicates the description of the offhire record")
    date = fields.Date('Offhire Date', help="Indicates the date of the offhire record")
    waive = fields.Boolean(help="Indicates if the recorded offhire should be waived, in which case the hours in the "
                                "record will not reflect even when selected")
    added = fields.Boolean(compute='_check_so_line', store=True, copy=False, help="Added to Sales Order")

    @api.model_create_multi
    def create(self, vals_list):
        records = super(SaleOffhire, self).create(vals_list)
        for rec in records:
            if rec.so_id:
                if rec.so_id.state == 'closed':
                    raise UserError(_('You cannot add an offhire record to a closed sales order.'))
                elif rec.so_id.state == 'cancel':
                    raise UserError(_('You cannot add an offhire record to a cancelled sales order.'))
        return records

    def _prepare_order_line(self, name, product_qty=0.0, price_unit=0.0, tax_id=False):
        self.ensure_one()
        product_id = self.env['product.product'].search([('name', '=', 'Offhire')])
        return {
            'name': name,
            'product_id': product_id and product_id[0].id,
            'product_uom_qty': product_qty,
            'price_unit': -price_unit,
            'tax_id': tax_id,
            'is_offhire': True,
        }