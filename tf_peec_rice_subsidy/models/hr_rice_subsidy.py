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


class TfHrRiceSubsidyReport(models.Model):
    _name = "tf.hr.rice.subsidy.report"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Rice Subsidy Report'

    _STATE = [
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ]

    name = fields.Char(track_visibility='onchange', required=True, copy=False,
                       help="Indicate the name of the to be generated rice subsidy report.")
    date_from = fields.Date(copy=False)
    date_to = fields.Date(copy=False)
    qualification_id = fields.Many2one('tf.hr.rice.subsidy.config', 'Qualification Template')
    is_dh = fields.Boolean("Driver/Helper", compute="_compute_qualification")
    tenure_count = fields.Float("Min. Tenure Year", compute="_compute_qualification")
    attendance_count = fields.Integer("Attendance Count", compute="_compute_qualification")
    meeting_count = fields.Integer("Meeting Count", compute="_compute_qualification")
    infraction_count = fields.Integer("Infraction Count", compute="_compute_qualification")
    trips_count = fields.Integer("Trips Count", compute="_compute_qualification")
    rice_subsidy_line_ids = fields.One2many('tf.hr.rice.subsidy.report.line', 'rice_subsidy_id', 'Details', copy=False)
    state = fields.Selection(_STATE, default='draft', track_visibility='onchange', copy=False)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from > rec.date_to:
                raise ValidationError(_("Interval's Date From cannot be later than Date To."))

    def action_confirm(self):
        for rec in self:
            rec.write({
                'state': 'confirm'
            })

    def action_generate(self):
        employee_obj = self.env['hr.employee']
        infraction_obj = self.env['ss.hris.infraction']
        trip_obj = self.env['logistics.trip.report']
        attendance_meeting_obj = self.env['tf.hr.dh.attendance']
        for rec in self:
            rec.rice_subsidy_line_ids.unlink()

            # Get DH Employee
            employee_ids = employee_obj.search([('active', '=', True),
                                                ('is_dh', '=', True)])
            line_vals = []

            for employee in employee_ids:
                # Get Tenure Year based on Employee Date Hired
                today = date.today()
                tenure_count = today.year - employee.date_hired.year - (
                        (today.month, today.day) < (employee.date_hired.month, employee.date_hired.day))

                trip_data_ids = trip_obj.search([('employee_id', '=', employee.id),
                                                 ('delivery_date', '>=', rec.date_from),
                                                 ('delivery_date', '<=', rec.date_to)])

                # Get infraction of DH Employee
                infraction_ids = infraction_obj.search([('employee_id', '=', employee.id),
                                                        ('state', 'in', ['in_progress', 'done']),
                                                        ('incident_date', '>=', rec.date_from),
                                                        ('incident_date', '<=', rec.date_to)])

                # Get attendance of DH Employee
                attendance_ids = attendance_meeting_obj.search([('employee_id', '=', employee.id),
                                                                ('state', '=', 'available'),
                                                                ('from_date', '>=', rec.date_from),
                                                                ('to_date', '<=', rec.date_to)])

                meeting_ids = attendance_meeting_obj.search([('employee_id', '=', employee.id),
                                                             ('state', '=', 'meeting'),
                                                             ('from_date', '>=', rec.date_from),
                                                             ('to_date', '<=', rec.date_to)])

                # Get all trip data & infraction of DH Employee
                trips_count = len(trip_data_ids.mapped('id'))
                infraction_count = len(infraction_ids.mapped('id'))
                attendance_count = len(attendance_ids.mapped('id'))
                meeting_count = len(meeting_ids.mapped('id'))

                vals = {
                    'employee_id': employee.id,
                    'tenure_count': tenure_count,
                    'trips_count': trips_count,
                    'infraction_count': infraction_count,
                    'attendance_count': attendance_count,
                    'meeting_count': meeting_count
                }

                line_vals.append((0, 0, vals))
            rec.write({
                'rice_subsidy_line_ids': line_vals
            })

    def action_done(self):
        overlaps = self.search([
            ('id', '!=', self.id),
            ('state', 'not in', ['draft', 'cancel']),
            ('date_from', '<=', self.date_from),
            ('date_to', '>=', self.date_to)
        ])
        if overlaps:
            raise ValidationError("You cannot use same duration of the previously validated report.\n\n"
                                  "Ref: %s" % (', '.join(overlaps.mapped('name'),)))
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    @api.depends('qualification_id')
    def _compute_qualification(self):
        for rec in self:
            # Get Qualification Configuration
            # and show it to the form for reference.
            qualification_id = rec.qualification_id
            rec.update({
                'is_dh': qualification_id.is_dh,
                'tenure_count': qualification_id.tenure_count,
                'attendance_count': qualification_id.attendance_count,
                'meeting_count': qualification_id.meeting_count,
                'infraction_count': qualification_id.infraction_count,
                'trips_count': qualification_id.trips_count
            })

    def unlink(self):
        # Prevent deletion of rice subsidy report not in draft state
        if self.filtered(lambda rec: rec.state != 'draft'):
            raise ValidationError(_("You may only delete a rice subsidy report in 'Draft' state."))
        res = super(TfHrRiceSubsidyReport, self).unlink()
        return res

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {}, name=_("%s (Copy)") % self.name)
        return super(TfHrRiceSubsidyReport, self).copy(default=default)


class TfHrRiceSubsidyReportLine(models.Model):
    _name = "tf.hr.rice.subsidy.report.line"
    _inherit = ['mail.thread']
    _description = 'Rice Subsidy Report Line'

    _STATE = [
        ('not_qualified', 'Not Qualified'),
        ('qualified', 'Qualified')
    ]

    rice_subsidy_id = fields.Many2one('tf.hr.rice.subsidy.report', 'Rice Subsidy', ondelete="cascade")
    employee_id = fields.Many2one('hr.employee', 'Employee', domain="[('is_dh', '=', True)]")
    rank_id = fields.Many2one(related='employee_id.rank_id', store=True)
    position_id = fields.Char(related='employee_id.job_title', store=True)
    tenure_count = fields.Float("Tenure")
    trips_count = fields.Integer("No. of Trips")
    infraction_count = fields.Integer("Infractions")
    attendance_count = fields.Integer("Attendances")
    meeting_count = fields.Integer("Meetings")
    rice_subsidy_state = fields.Selection(_STATE, "Rice Subsidy", compute='_compute_state', store=True)

    @api.constrains('tenure_count', 'trips_count', 'infraction_count', 'attendance_count', 'meeting_count')
    def _check_counts(self):
        for rec in self:
            if rec.tenure_count < 0 \
                    or rec.trips_count < 0 \
                    or rec.infraction_count < 0 \
                    or rec.attendance_count < 0 \
                    or rec.meeting_count < 0:
                raise ValidationError(_('Tenure / No. of Trips / Infractions / '
                                        'Attendance / Meetings must not be negative.'))

    def unlink(self):
        res = super(TfHrRiceSubsidyReportLine, self).unlink()
        return res

    def check_qualification(self, tenure, attendance, meeting, infraction, trip):
        for rec in self:
            subsidy = rec.rice_subsidy_id
            if tenure >= subsidy.tenure_count \
                    and attendance >= subsidy.attendance_count \
                    and meeting >= subsidy.meeting_count \
                    and infraction <= subsidy.infraction_count \
                    and trip >= subsidy.trips_count:
                return 'qualified'
            else:
                return 'not_qualified'

    @api.depends('rice_subsidy_id.qualification_id', 'tenure_count', 'attendance_count', 'meeting_count', 'infraction_count', 'trips_count')
    def _compute_state(self):
        for rec in self:
            rec.rice_subsidy_state = rec.check_qualification(
                rec.tenure_count, rec.attendance_count, rec.meeting_count, rec.infraction_count, rec.trips_count
            )
