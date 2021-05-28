# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2021 Taliform Inc.
#
# Author: Benjamin Cerdena Jr <benjamin@taliform.com>
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

_DH_AVAILABILITY = [
    ('available', 'Available'),
    ('leave', 'On Leave'),
    ('meeting', 'In Meeting'),
    ('unavailable', 'Unavailable')
]


class TfHrJobAssignmentConfig(models.Model):
    _name = "tf.hr.job_assignment.config"
    _inherit = ['mail.thread']
    _description = "Temporary Job Assignment Configuration"

    name = fields.Char("Temporary Job Assignment", required=True, copy=False,
                       help="Indicates the name for the temporary job assignment configuration.")
    effective_date = fields.Date("Effective Date")
    position_id = fields.Many2many('hr.job', required=True, copy=False,
                                   help="Select the position that the temporary job assignment to be applied")
    attendance_status = fields.Selection(_DH_AVAILABILITY, "Attendance Status", required=True, copy=False,
                                         help="Select the drivers & helpers attendance status for job assignment")
    type_id = fields.Many2one('ss.hris.salary_adjustment.type', 'Adjustment Type', required=True, copy=False,
                              domain="[('mode', '=', 'addition')]")
    expiration_time = fields.Float("Expiration Time", required=True, copy=False,
                                   help="Indicate the applicable default expiration time duration for job assignment "
                                        "that has not been log-off by the employee.")
    task_detail_ids = fields.One2many('tf.hr.job_assignment.task.line', 'job_assignment_id', copy=False)
    work_hour_ids = fields.One2many('tf.hr.job_assignment.work_hour.line', 'job_assignment_id', copy=False)


class TfHrJobAssignmentTaskLine(models.Model):
    _name = "tf.hr.job_assignment.task.line"
    _inherit = ['mail.thread']
    _description = "Temporary Job Task Line"
    _rec_name = 'task'

    job_assignment_id = fields.Many2one('tf.hr.job_assignment.config', 'Job Assignment', ondelete="cascade")
    task = fields.Char('Tasks', track_visibility="onchange", required=True,
                       help="User will indicate the job assignment task.")
    description = fields.Char('Description', track_visibility="onchange",
                              help="User will indicate the job assignment description.")
    rate_per_day = fields.Monetary('Rate Per Day', track_visibility="onchange", required=True,
                                   help="User will indicate the job assignment rate per day.")
    currency_id = fields.Many2one('res.currency')


class TfHrJobAssignmentWorkHourLine(models.Model):
    _name = "tf.hr.job_assignment.work_hour.line"
    _inherit = ['mail.thread']
    _description = "Temporary Job Work Hour Range Line"

    _HOURS = [
        ('1_2hours', '1 - 2 Hours'),
        ('2_4hours', '2 - 4 Hours'),
        ('4_6hours', '4 - 6 Hours'),
        ('6_8hours', '6 - 8 Hours')
    ]

    _RATE = [
        ('no_pay', 'No Pay'),
        ('25percent_pay', '1/4 of a Day (25%)'),
        ('50percent_pay', 'Half Day (50%)'),
        ('75percent_pay', '3/4 of a Day (75%)'),
        ('100percent_pay', 'Full Day (100%)')
    ]

    job_assignment_id = fields.Many2one('tf.hr.job_assignment.config', 'Job Assignment', ondelete="cascade")
    range_hours = fields.Selection(_HOURS, 'Range Hours', required=True,
                                   help="User will indicate the range hours.")
    range_duration = fields.Selection(_RATE, 'Range Duration', required=True,
                                      help="User will indicate the job assignment range duration.")
