# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Joshua <joshua@taliform.com>
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


class AccountAsset(models.Model):
    _inherit = 'account.asset'


    parent_id = fields.Many2one('account.asset', string='Parent', domain=[('state', '=', 'open')])
    fleet_asset = fields.Boolean(default=False, string='Asset Under Fleet')
    fleet_record = fields.Many2one('fleet.vehicle', string='Fleet Record', track_visibility='onchange')


    @api.onchange('fleet_record')
    def _onchange_fleet_record(self):
        for rec in self:
            rec._vehicle_validation()
            fleet_rec = rec.fleet_record
            rec.acquisition_date = fleet_rec.acquisition_date
            rec.original_value = fleet_rec.net_car_value
            rec.salvage_value = fleet_rec.residual_value


    def _vehicle_validation(self):
        for rec in self:
            if rec.fleet_asset:
                fleet_records = self.search([('fleet_record', '=', rec.fleet_record.id)])
                if fleet_records:
                    raise ValidationError('Vehicle record has already been tagged to another asset record.')

    def set_to_running(self):
        AssetSell = self.env['account.asset.sell']
        for rec in self:
            asset_sell_rec = AssetSell.browse(rec.id)
            if asset_sell_rec.action == 'sell':
                raise ValidationError("You cannot rerun an asset record that's already been sold.")
        return super(AccountAsset, self).set_to_running()

    @api.depends('value_residual', 'salvage_value', 'children_ids.book_value', 'gross_increase_count', 'children_ids')
    def _compute_book_value(self):
        res = super(AccountAsset, self)._compute_book_value()
        for rec in self:
            total_child_book_value = 0
            gross_value_total = 0
            for child in rec.children_ids:
                if child.state != 'close':
                    total_child_book_value = child.book_value
                    gross_value_total = child.original_value
            self.book_value = rec.value_residual + total_child_book_value
            self.gross_increase_value = gross_value_total
        return res

class AssetSell(models.TransientModel):
    _inherit = 'account.asset.sell'

    def do_action(self):
        res = super(AssetSell, self).do_action()
        for rec in self:
            asset = rec.asset_id
            if self.action == 'sell':
                print('test 1')
                draft_dep_lines = asset.depreciation_move_ids.filtered(lambda d: d.state == 'draft')

                # remove from asset record
                asset.write({
                    'depreciation_move_ids': [(3, dep.id) for dep in draft_dep_lines]
                })
                print('test 2')

                # cancel move records
                #draft_dep_lines.button_cancel()

                # Invoice line
                invoice_line = self.invoice_line_id or self.invoice_id.invoice_line_ids
                invoice_move = invoice_line.move_id

                # Get default sales journal
                sales_journal = self.env['account.journal'].search([('type', '=', 'sale')], limit=1)
                cash_journal = self.env['account.journal'].search([('type', '=', 'cash')], limit=1)

                # Get accumulated depreciation
                posted_dep_lines = asset.depreciation_move_ids.filtered(lambda d: d.state == 'posted')
                dep_vals = posted_dep_lines.mapped('asset_depreciated_value')

                print('test 3')

                # Create draft invoice
                move = self.env['account.move'].create({
                    'journal_id': asset.journal_id.id,
                    'ref': 'Sell %s' % (asset.name,),
                    'asset_id': asset.id,
                    'name': '/',
                    'type': 'entry',
                    # 'asset_remaining_value': 0,
                    # 'amount_total': 0,
                    # 'asset_depreciated_value': max(dep_vals),
                })

                debit_line_1 = {
                    'account_id': sales_journal.default_credit_account_id.id,
                    'name': 'Asset Sale',
                    'debit': invoice_line.price_subtotal,  # AR Selling Price
                }

                if self.gain_or_loss == 'gain':
                    print('gain')
                    dep_vals_sum = sum(dep_vals)
                    gain_value = invoice_line.price_subtotal - (asset.original_value - dep_vals_sum)

                    debit_line_2 = {
                        'account_id': asset.account_depreciation_id.id,
                        'name': 'Accumulated Depreciation',
                        'debit': dep_vals_sum,
                    }

                    # Prepare Credit Line
                    credit_line_1 = {
                        'account_id': asset.account_asset_id.id,
                        'name': asset.name,
                        'credit': asset.original_value,  # AR Selling Price
                    }

                    credit_line_2 = {
                        'account_id': self.gain_account_id.id,
                        'name': '%s Sell Gain' % (asset.name,),
                        'credit': gain_value,
                    }
                    vals = {
                        'line_ids': [
                            (0, 0, debit_line_1),
                            (0, 0, credit_line_1),
                            (0, 0, debit_line_2),
                            # (0, 0, debit_line_3),
                            (0, 0, credit_line_2),
                            # (0, 0, credit_line_3),
                        ]
                    }
                    print(vals)
                    move.write(vals)

                elif self.gain_or_loss == 'loss':
                    print('loss')
                    loss_value = (asset.original_value - max(dep_vals)) - invoice_line.price_subtotal
                    print('loss value %s' % loss_value)
                    # Prepare Debit Lines
                    debit_line_2 = {
                        'account_id': cash_journal.default_credit_account_id.id,
                        'name': invoice_move.name,
                        'debit': invoice_line.price_subtotal,
                    }

                    debit_line_3 = {
                        'account_id': asset.account_depreciation_id.id,
                        'name': 'Accumulated Depreciation',
                        'debit': max(dep_vals),
                    }

                    debit_line_4 = {
                        'account_id': self.loss_account_id.id,
                        'name': '%s Sell Loss' % (asset.name,),
                        'debit': loss_value,
                    }

                    # Prepare Credit Line
                    credit_line_2 = {
                        'account_id': asset.account_asset_id.id,
                        'name': asset.name,
                        'credit': asset.original_value,  # AR Selling Price
                    }
                    vals = {
                        'line_ids': [
                            (0, 0, debit_line_1),
                           # (0, 0, credit_line_1),
                           # (0, 0, debit_line_2),
                            (0, 0, debit_line_3),
                            (0, 0, credit_line_2),
                            (0, 0, debit_line_4),
                        ]
                    }
                    print(vals)
                    move.write(vals)
            asset.value_residual = 0
            parent_asset = asset.parent_id
            if parent_asset:
                parent_asset.book_value = parent_asset.book_value - asset.book_value
        return res
