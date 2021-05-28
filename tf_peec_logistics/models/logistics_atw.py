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
import werkzeug

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AuthorityToWithdraw(models.Model):
    _name = 'logistics.atw'
    _description = 'Authority To Withdraw'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    name = fields.Char('Reference', default='New', copy=False, required=True, tracking=True, index=True)
    delivery_order_id = fields.Many2one('logistics.delivery.order', 'Delivery Order', company_dependent=True,
                                        index=True)
    cement_plant_id = fields.Many2one('res.partner', 'Cement Plant', required=True, index=True)
    sale_id = fields.Many2one('sale.order', 'Sales Order', index=True, tracking=True)
    purchase_id = fields.Many2one('purchase.order', 'Purchase Order', index=True, tracking=True)
    picking_id = fields.Many2one('stock.picking', 'Delivery Receipt')
    weight_log_id = fields.Many2one('logistics.log.weight', 'Weight Log')
    bags_qty = fields.Float(related='weight_log_id.bags_qty', store=True)
    bag_uom_id = fields.Many2one('uom.uom', compute='_compute_bag_uom_id', store=True)
    vendor_id = fields.Many2one(related='purchase_id.partner_id', string='Vendor', store=True)
    vendor_atw_no = fields.Char('Vendor ATW No.', index=True)
    vendor_dr_no = fields.Char('Vendor DR No.')
    is_delivered = fields.Boolean('Is Delivered?', compute='_compute_is_delivered', store=True)
    partner_ref = fields.Char('PO / SO No.', related='purchase_id.partner_ref', store=True, index=True)
    product_id = fields.Many2one('product.product', 'Cement Product', required=True, index=True)
    quantity = fields.Float(required=True, tracking=True)
    uom_id = fields.Many2one('uom.uom', 'Cement Unit of Measure',
                             default=lambda s: s.env.company.logistics_cement_bag_uom_id, required=True)
    packaging = fields.Selection([('bagged', 'Bagged'), ('bulk', 'Bulk')], 'Packaging', default='bagged', tracking=True)
    atw_date = fields.Datetime('ATW Date', default=fields.Datetime.now, tracking=True, index=True)
    state = fields.Selection([('unmatched', 'Unmatched'), ('matched', 'Matched')], compute='_compute_state', store=True,
                             tracking=True, index=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda s: s.env.company, index=True)
    currency_id = fields.Many2one('res.currency', 'Currency', required=True, default=lambda s: s.env.company.currency_id, index=True)
    withdrawal_amount = fields.Float('Withdrawal Amount')

    @api.depends('weight_log_id', 'withdrawal_amount')
    def _compute_bag_uom_id(self):
        for rec in self:
            if rec.weight_log_id:
                rec.bag_uom_id = rec.weight_log_id.bag_uom_id
            elif not rec.weight_log_id and rec.withdrawal_amount:
                rec.bag_uom_id = self.env.company.logistics_cement_bag_uom_id
            else:
                rec.bag_uom_id = False

    @api.depends('purchase_id')
    def _compute_state(self):
        for atw in self:
            if atw.purchase_id:
                atw.state = 'matched'
            else:
                atw.state = 'unmatched'

    @api.depends('delivery_order_id')
    def _compute_is_delivered(self):
        for atw in self:
            if atw.delivery_order_id:
                if atw.delivery_order_id.state in ['unloaded', 'validation', 'closed']:
                    atw.is_delivered = True
                else:
                    atw.is_delivered = False
            else:
                atw.is_delivered = False

    @api.onchange('delivery_order_id')
    def _onchange_delivery_order_id(self):
        for rec in self:
            if rec.delivery_order_id:
                rec.product_id = rec.delivery_order_id.product_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Assign sequence
            if vals.get('name', _('New')) == _('New'):
                IrSequence = self.env['ir.sequence']
                seq_date = None
                if 'atw_date' in vals:
                    seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['atw_date']))
                if 'company_id' in vals:
                    vals['name'] = IrSequence.with_context(force_company=vals['company_id']).next_by_code(
                        self._name, sequence_date=seq_date) or _('New')
                else:
                    vals['name'] = IrSequence.next_by_code(self._name, sequence_date=seq_date) or _('New')

        result = super(AuthorityToWithdraw, self).create(vals_list)

        for atw in result:
            if not atw.purchase_id:
                # Send notifications according to Logistics Settings
                notification_type = self.env.company.logistics_atw_notification_type
                if notification_type == 'user' and self.env.company.logistics_atw_user_id:
                    self._notify_users(self.env.company.logistics_atw_user_id, atw)
                elif notification_type == 'group' and self.env.company.logistics_atw_group_id:
                    group_users = self.env.company.logistics_atw_group_id.sudo().users
                    self._notify_users(group_users, atw)

        return result

    def write(self, vals):
        result = super(AuthorityToWithdraw, self).write(vals)

        for atw in self:
            new_purchase = vals.get('purchase_id', False)
            new_delivery_order = vals.get('delivery_order_id', False)

            if (new_purchase and atw.delivery_order_id) \
                    or (new_delivery_order and atw.purchase_id) \
                    or (new_purchase and new_delivery_order):
                if new_delivery_order:
                    delivery_order = self.env['logistics.delivery.order'].browse([new_delivery_order])
                elif atw.delivery_order_id:
                    delivery_order = atw.delivery_order_id

                    # Notify Delivery Unit users that ATW has been matched
                    delivery_unit = atw.delivery_order_id.delivery_unit_id
                    drivers = delivery_unit.driver_ids.mapped('user_id')
                    helpers = delivery_unit.helper_ids.mapped('user_id')
                    to_notify = drivers + helpers
                    message = _('An ATW of a Delivery Order has been matched.<br>'
                                'Open <a href="%(do_url)s">%(do_name)s</a>') % ({
                        'do_name': delivery_order.name,
                        'do_url': delivery_order.get_url()
                    })
                    self._notify_users(to_notify, atw, title='ATW Matched', message=message, suppress_activity=True,
                                       sticky=True)

        return result

    def _notify_users(self, users, atw, title='', message='', activity_type='tf_peec_logistics.mail_act_match_atw',
                      activity_message='', suppress_activity=False, sticky=False):
        if message == '':
            message = _('A new ATW record was created and needs to be matched with a Purchase Order.<br>'
                        'Open <a href="%(atw_url)s">%(atw_name)s</a>') % ({
                'atw_name': atw.name,
                'atw_url': atw.get_url()
            })
        if activity_message == '':
            activity_message = _('A new ATW record was created and needs to be matched with a Purchase Order.')
        if title == '':
            title = 'New ATW to Match'

        if len(users) > 1:
            for user in users:
                user.notify_default(title=title, message=message, sticky=sticky)
        elif users:
            if not suppress_activity:
                atw.activity_schedule(
                    activity_type,
                    user_id=users.id,
                    note=activity_message
                )
            users.notify_default(title=title, message=message, sticky=sticky)

    def get_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url_params = {
            'id': self.id,
            'action': self.env.ref('tf_peec_logistics.action_logistics_atw').id,
            'model': self._name,
            'view_type': 'form',
        }
        url = werkzeug.urls.url_join(
            base_url, 'web?#%s' % werkzeug.urls.url_encode(url_params)
        )
        return url

    def get_unit_price(self):
        self.ensure_one()

        if self.purchase_id:
            po_uom = self.purchase_id.order_line[0].product_uom
            po_unit_price = self.purchase_id.order_line[0].price_unit
            if self.bag_uom_id != po_uom:
                # _compute_quantity(self, qty, to_unit, round=True, rounding_method='UP', raise_if_failure=True):
                #po_uom._compute_quantity()
                return po_unit_price * self.bag_uom_id.factor_inv
                # in_po_unit = self.bag_uom_id._compute_quantity(self.bags_qty, po_uom)
                # if in_po_unit > self.bags_qty:
                #     # This means bags uom is greater than 1 unit of po's uom
                #     return po_unit_price * self.bag_uom_id.factor_inv
                # else:
                #     return po_unit_price * self.bag_uom_id.factor_inv
            else:
                return po_unit_price

    def get_total_amount(self):
        self.ensure_one()
        return self.get_unit_price() * self.bags_qty

    def name_get(self):
        result = []
        for atw in self:
            if atw.vendor_atw_no:
                name = "%s (%s)" % (
                    atw.name,
                    atw.vendor_atw_no
                )
            else:
                name = "%s" % (
                    atw.name,
                )
            result.append((atw.id, name))
        return result

    def action_withdraw_cement(self):
        for rec in self:
            # Receive the actual amount of cement from Purchase Order
            pickings = rec.purchase_id.picking_ids.filtered(lambda p: p.state != 'done')
            if pickings:
                picking = pickings[0]
                move_line = picking.move_ids_without_package[0]
                move_line.write({
                    'move_line_ids': [(0, 0, {
                        'location_id': move_line.location_id.id,
                        'location_dest_id': move_line.location_dest_id.id,
                        'qty_done': rec.withdrawal_amount,
                        'picking_id': picking.id,
                        'product_id': rec.product_id.id,
                        'product_uom_id': rec.bag_uom_id.id,
                    })]
                })
                picking.with_context(cancel_backorder=False).action_done()
                rec.write({'picking_id': picking.id})

            # Try to reserve amount that was just received
            pickings = rec.sale_id.picking_ids.filtered(lambda p: p.state != 'done')
            if pickings:
                picking = pickings[0]
                picking.action_assign()
