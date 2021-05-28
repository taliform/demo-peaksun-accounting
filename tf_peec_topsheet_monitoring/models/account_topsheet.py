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


class AccountTopsheet(models.Model):
    _inherit = 'account.topsheet'

    @api.returns('self')
    def _default_stage(self):
        return self.env['account.topsheet.stages'].search([], limit=1)

    stage_id = fields.Many2one('account.topsheet.stages', string='Topsheet Stage', default=_default_stage,
                               group_expand='_read_group_stage_ids', track_visibility="onchange")
    move_remarks = fields.Char(track_visibility="onchange", string='Stage Move Remarks')

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        return self.env['account.topsheet.stages'].search([], order=order)

    def action_next_stage(self):
        TopsheetStage = self.env['account.topsheet.stages']
        stage_sequences = self._get_stage_sequences()
        for rec in self:
            if rec.stage_id.id:
                curr_stage_seq = rec.stage_id.sequence
                next_stage_seq = curr_stage_seq + 1
                if next_stage_seq in stage_sequences:
                    next_stage_id = TopsheetStage.search([('sequence', '=', next_stage_seq)]).id
                    if TopsheetStage.browse([next_stage_id]).require_date:
                        return {
                            'name': 'Topsheet Monitoring Move Stage',
                            'view_type': 'form',
                            'view_mode': 'form',
                            'res_model': 'topsheet.monitoring.move.stage',
                            'view_id': self.env.ref(
                                'tf_peec_topsheet_monitoring.topsheet_monitoring_move_stage_view_form').id,
                            'context': {'default_topsheet_id': rec.id,
                                        'default_to_stage': next_stage_id},
                            'type': 'ir.actions.act_window',
                            'target': 'new'
                        }
                    else:
                        rec.write({
                            'stage_id': next_stage_id
                        })
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'reload',
                        }

    def action_prev_stage(self):
        TopsheetStage = self.env['account.topsheet.stages']
        stage_sequences = self._get_stage_sequences()
        for rec in self:
            if rec.stage_id.id:
                curr_stage_seq = rec.stage_id.sequence
                prev_stage_seq = curr_stage_seq - 1
                if prev_stage_seq in stage_sequences:
                    prev_stage_id = TopsheetStage.search([('sequence', '=', prev_stage_seq)]).id
                    if TopsheetStage.browse([prev_stage_id]).require_date:
                        return {
                            'name': 'Topsheet Monitoring Move Stage',
                            'view_type': 'form',
                            'view_mode': 'form',
                            'res_model': 'topsheet.monitoring.move.stage',
                            'view_id': self.env.ref(
                                'tf_peec_topsheet_monitoring.topsheet_monitoring_move_stage_view_form').id,
                            'context': {'default_topsheet_id': rec.id,
                                        'default_to_stage': prev_stage_id},
                            'type': 'ir.actions.act_window',
                            'target': 'new'
                        }
                    else:
                        rec.write({
                            'stage_id': prev_stage_id
                        })
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'reload',
                        }

    def _get_stage_sequences(self):
        return self.env['account.topsheet.stages'].search([]).mapped('sequence')
