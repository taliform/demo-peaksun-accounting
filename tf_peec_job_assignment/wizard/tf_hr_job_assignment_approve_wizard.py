# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2021 Taliform Inc.
#
# Author: Benjamin Cerdena Jr. <benjamin@taliform.com>
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

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TfHrJobAssignmentApproveWizard(models.TransientModel):
    _name = 'tf.hr.job_assignment.approve.wizard'

    start_time = fields.Datetime('Start Time')
    end_time = fields.Datetime('End Time')
    task_id = fields.Many2one('tf.hr.job_assignment.task.line', 'Task')
    is_done = fields.Boolean('Done')

    def action_confirm(self):
        for rec in self:
            approve_id = self.env[self._context.get('active_model')].browse(self._context.get('active_id'))
            vals = {
                'start_time': rec.start_time,
                'end_time': rec.end_time,
                'task_id': rec.task_id.id,
                'is_done': rec.is_done,
                'state': 'confirm'
            }
            approve_id.write(vals)

        # return {'type': 'ir.actions.client', 'tag': 'reload'}
