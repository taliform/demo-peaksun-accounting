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


class TfHrJobAssignmentSAWizard(models.TransientModel):
    _name = 'tf.hr.job_assignment.sa.wizard'

    employee_id = fields.Many2one('hr.employee', 'Employee')
    currency_id = fields.Many2one('res.currency')
    job_config_id = fields.Many2one('tf.hr.job_assignment.config', 'Job Assignment')
    type_id = fields.Many2one('ss.hris.salary_adjustment.type', related="job_config_id.type_id")
    adjustment_date = fields.Date('Adjustment Date')
    total_hours = fields.Float('Total Hours', compute="compute_hours")
    amount = fields.Monetary()
    reference = fields.Char('Source Document')
    assignment_line_ids = fields.One2many('tf.hr.job_assignment.line', 'job_assignment_id')

    @api.model
    def hours_between(self, from_date, to_date):
        if from_date and to_date:
            return (to_date - from_date).seconds / 60.0 / 60.0
        else:
            return 0

    @api.depends('assignment_line_ids.start_time', 'assignment_line_ids.end_time')
    def compute_hours(self):
        for assignment in self.assignment_line_ids:
            start_time = assignment.start_time
            end_time = assignment.end_time
            hours = 0

            if start_time < end_time:
                hours += self.hours_between(start_time, end_time)
            self.total_hours = hours

    def compute_amount(self):
        job_config_id = self.job_config_id
        work_hour_ids = job_config_id.work_hour_ids
        for assignment in self.assignment_line_ids:
            amount = 0
            if work_hour_ids.range_hours == '1_2hours' and self.total_hours <= 2 and self.total_hours > 0:
                amount += assignment.amount * 0.25
                self.amount = amount

    def action_confirm(self):
        for rec in self:
            approve_id = self.env[self._context.get('active_model')].browse(self._context.get('active_id'))
            vals = {
                'end_time': rec.end_time,
                'is_done': rec.is_done
            }
            approve_id.write(vals)

        # return {'type': 'ir.actions.client', 'tag': 'reload'}
