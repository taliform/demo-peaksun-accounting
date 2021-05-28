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
from datetime import date

from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError


class TfHrJobAssignment(models.Model):
    _name = 'tf.hr.job_assignment'
    _inherit = ['mail.thread']
    _description = 'Temporary Job Assignment'

    _STATE = [
        ('draft', 'Draft'),
        ('in_progress', 'In-Progress'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
        ('expired', 'Expired'),
    ]

    name = fields.Char(track_visibility='onchange', default='Draft Job Assignment', copy=False,)
    employee_id = fields.Many2one('hr.employee', string='Employee', copy=False,
                                  domain="[('is_dh', '=', True)]")
    requestor_id = fields.Many2one('hr.employee', string='Requested By', copy=False)
    job_config_id = fields.Many2one('tf.hr.job_assignment.config', 'Temp. Job Assignment')
    currency_id = fields.Many2one('res.currency')
    position_id = fields.Many2one('hr.job')
    date = fields.Date(string="Requested Date", required=True, copy=False,
                       help="Indicate the date of the job assignment request based on the submitted approved "
                            "job assignment form")
    adjustment_date = fields.Date('Adjustment Date', required=True, copy=False,)
    remarks = fields.Text()
    state = fields.Selection(_STATE, string='State', default='draft', copy=False)
    assignment_line_ids = fields.One2many('tf.hr.job_assignment.line', 'job_assignment_id')
    estimated_amount = fields.Monetary(string="Estimated Assignment Amount", compute="_compute_amount", store=True)
    confirmed_amount = fields.Monetary(string="Confirmed Amount", compute="_compute_amount", store=True)
    unprocessed_amount = fields.Monetary(string="Unprocessed Amount", compute="_compute_amount", store=True)
    charged_amount = fields.Monetary(string="Total Charged Amount", compute="_compute_amount", store=True)

    def write(self, vals):

        if self.state == 'draft':
            vals['state'] = 'in_progress'
            vals['name'] = self.env['ir.sequence'].next_by_code('tf.hr.job_assignment')
        if self.state == 'in_progress':
            for assignment in self.assignment_line_ids:
                assignment.write({'state': 'pending'})
        return super(TfHrJobAssignment, self).write(vals)

    @api.depends('assignment_line_ids')
    def _compute_amount(self):
        for rec in self:
            line_ids = self.assignment_line_ids
            estimated_amount = sum(line_ids.mapped('rates'))
            confirmed_amount = sum(line_ids.filtered(lambda s: s.state in ['confirm', 'charge']).mapped('rates'))
            unprocessed_amount = sum(line_ids.filtered(lambda s: s.state == 'confirm').mapped('rates'))
            charged_amount = sum(line_ids.filtered(lambda s: s.state == 'charge').mapped('rates'))

            rec.update({
                'estimated_amount': estimated_amount,
                'confirmed_amount': confirmed_amount,
                'unprocessed_amount': unprocessed_amount,
                'charged_amount': charged_amount
            })

    def action_generate_sa(self):
        sa_obj = self.env['ss.hris.salary_adjustment']
        sequence_obj = self.env['ir.sequence']
        for rec in self:
            employee_id = rec.employee_id
            job_config_id = rec.job_config_id
            assignment_line_ids = self.assignment_line_ids
            for assignment_line in assignment_line_ids:
                adjustments_to_delete = assignment_line.mapped('adjustment_id')
                adjustments_to_delete.filtered(lambda a: a.state not in ['cancel', 'done']).action_cancel()

                if assignment_line.state == 'confirm':
                    vals = {
                        'name': sequence_obj.sudo().next_by_code('ss.hris.salary_adjustment'),
                        'employee_id': employee_id.id,
                        'type_id': job_config_id.type_id.id,
                        'date': rec.adjustment_date,
                        'reference': rec.name,
                        'amount': assignment_line.amount
                    }
                    adjustment_id = sa_obj.create(vals)
                    adjustment_id.action_confirm()
                    assignment_line.adjustment_id = adjustment_id
                    assignment_line.state = 'charge'

    def action_done(self):
        self.sudo().write({'state': 'done'})

    def action_cancel(self):
        for rec in self:
            assignment_line_ids = rec.assignment_line_ids
            for assignment_line in assignment_line_ids:
                assignment_line.action_decline()
                adjustments_to_delete = assignment_line.mapped('adjustment_id')
                adjustments_to_delete.filtered(lambda a: a.state not in ['cancel', 'done']).action_cancel()
        self.sudo().write({'state': 'cancel'})

    def unlink(self):
        # Prevent deletion of job assignment not in draft state
        if self.filtered(lambda rec: rec.state != 'draft'):
            raise ValidationError(_("You may only delete a job assignment in 'Draft' state."))
        res = super(TfHrJobAssignment, self).unlink()
        return res


class TfHrJobAssignmentLine(models.Model):
    _name = 'tf.hr.job_assignment.line'
    _inherit = ['mail.thread']
    _description = 'Temporary Job Assignment Line'

    _STATE = [
        ('pending', 'Pending'),
        ('confirm', 'Confirmed'),
        ('cancel', 'Cancelled'),
        ('charge', 'Charged')
    ]

    _JS_STATE = [
        ('draft', 'Draft'),
        ('in_progress', 'In-Progress'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
        ('expired', 'Expired'),
    ]

    job_assignment_id = fields.Many2one('tf.hr.job_assignment', 'Job Assignment', ondelete="cascade")
    job_config_id = fields.Many2one('tf.hr.job_assignment.config', 'Job Assignment Config',
                                    related="job_assignment_id.job_config_id", store=True)
    currency_id = fields.Many2one('res.currency')
    start_time = fields.Datetime('Start Time', required=True)
    end_time = fields.Datetime('End Time')
    task_id = fields.Many2one('tf.hr.job_assignment.task.line', required=True)
    description = fields.Char(related="task_id.description", store=True)
    rates = fields.Monetary(related="task_id.rate_per_day", store=True)
    total_hours = fields.Float('Total Hours', compute="compute_hours", store=True)
    amount = fields.Monetary(compute="compute_amount")
    is_done = fields.Boolean('Done')
    state = fields.Selection(_STATE)
    job_assignment_state = fields.Selection(related="job_assignment_id.state", copy=False)
    adjustment_id = fields.Many2one('ss.hris.salary_adjustment', string='Salary Adjustment')

    @api.model
    def hours_between(self, from_date, to_date):
        if from_date and to_date:
            return (to_date - from_date).seconds / 60.0 / 60.0
        else:
            return 0

    @api.depends('start_time', 'end_time')
    def compute_hours(self):
        for rec in self:
            start_time = rec.start_time
            end_time = rec.end_time
            hours = 0

            if start_time < end_time:
                hours += self.hours_between(start_time, end_time)
            self.total_hours = hours

    @api.depends('total_hours')
    def compute_amount(self):
        for rec in self:
            job_config_id = rec.job_config_id
            for work_hour_id in job_config_id.work_hour_ids:
                amount = 0
                if rec.total_hours <= 2.0 and rec.total_hours > 0 and work_hour_id.range_hours == '1_2hours':
                    amount += (rec.rates * 0.25)
                    rec.amount = amount
                elif rec.total_hours <= 4.0 and rec.total_hours > 2.0 and work_hour_id.range_hours == '2_4hours':
                    amount += (rec.rates * 0.50)
                    rec.amount = amount
                elif rec.total_hours <= 6.0 and rec.total_hours > 4.0 and work_hour_id.range_hours == '1_2hours':
                    amount += (rec.rates * 0.75)
                    rec.amount = amount
                elif rec.total_hours <= 8.0 and rec.total_hours > 6.0 and work_hour_id.range_hours == '1_2hours':
                    amount += (rec.rates * 1)
                    rec.amount = amount

    def action_decline(self):
        for rec in self:
            rec.write({'state': 'cancel'})

    def unlink(self):
        res = super(TfHrJobAssignmentLine, self).unlink()
        return res
