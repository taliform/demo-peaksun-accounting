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
import datetime

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_DH_AVAILABILITY = [
    ('available', 'Available'),
    ('leave', 'On Leave'),
    ('meeting', 'In Meeting'),
    ('unavailable', 'Unavailable')
]


class HrJob(models.Model):
    _inherit = "hr.job"

    is_dh = fields.Boolean("Driver/Helper", help="Indicate if the job position is for driver and helper.")


class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    is_dh = fields.Boolean(related="job_id.is_dh")


class HrEmployee(models.Model):
    _inherit = "hr.employee"
    DRIVER_HELPER = [
        ('driver', 'Driver'),
        ('helper', 'Helper')
    ]
    is_dh = fields.Boolean(related="job_id.is_dh", store=True, index=True)
    select_dh = fields.Selection(DRIVER_HELPER, string="Select D/H", store=True)
    plant_acc_ids = fields.One2many('tf.hr.plant.accreditation', 'employee_id', "Plants",
                                    domain=[('status', '!=', 'draft')])
    doc_acc_ids = fields.One2many('tf.hr.doc.accreditation', 'employee_id', "Documents",
                                  domain=[('status', '!=', 'draft')])
    license_acc_ids = fields.One2many('tf.hr.license.accreditation', 'employee_id', "Licenses",
                                      domain=[('status', '!=', 'draft')])
    truck_ids = fields.Many2many('fleet.vehicle', string="Trucks")

    def action_get_attachment_tree_view(self):
        res = super(HrEmployee, self).action_get_attachment_tree_view()
        applicants = self.env['hr.applicant'].search([('emp_id', 'in', self.ids)])
        res['domain'] = [
            '|', '|', '|', '|',
            '&', ('res_model', '=', 'hr.employee'), ('res_id', 'in', self.ids),
            '&', ('res_model', '=', 'hr.applicant'), ('res_id', 'in', applicants.ids),
            '&', ('res_model', '=', 'tf.hr.plant.accreditation'), ('res_id', 'in', self.plant_acc_ids.ids),
            '&', ('res_model', '=', 'tf.hr.doc.accreditation'), ('res_id', 'in', self.doc_acc_ids.ids),
            '&', ('res_model', '=', 'tf.hr.license.accreditation'), ('res_id', 'in', self.license_acc_ids.ids)
        ]
        return res

    def _compute_document_ids(self):
        super(HrEmployee, self)._compute_document_ids()
        for employee in self:
            employee.documents_count = len(employee.document_ids) \
                                       + len(employee.plant_acc_ids.mapped('attachment')) \
                                       + len(employee.doc_acc_ids.mapped('attachment')) \
                                       + len(employee.license_acc_ids.mapped('attachment'))


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'
    DRIVER_HELPER = [
        ('driver', 'Driver'),
        ('helper', 'Helper')
    ]
    is_dh = fields.Boolean(related="job_id.is_dh", store=True)
    select_dh = fields.Selection(DRIVER_HELPER, string="Select D/H", store=True)


class HrAccreditation(models.AbstractModel):
    _name = 'tf.hr.accreditation'
    _description = "Accreditation for Drivers/Helpers"

    _STATUS = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('accredited', 'Accredited'),
        ('renewal', 'For Renewal'),
        ('expired', 'Expired')
    ]

    employee_id = fields.Many2one('hr.employee', "Employee", domain="[('is_dh','=',True)]")
    last_name = fields.Char(related="employee_id.last_name")
    first_name = fields.Char(related="employee_id.first_name")
    middle_init = fields.Char(related="employee_id.middle_name", string="Middle Initial", size=2)
    work_location = fields.Char("Work Location", related="employee_id.work_location")
    position_id = fields.Char("Position", related="employee_id.contract_id.position_id.name")
    rank_id = fields.Char("Rank/Level", related="employee_id.rank_id.name")
    ref_no = fields.Char("Reference No.", track_visibility='onchange')
    effective_date = fields.Date("Effective Date", track_visibility='onchange')
    expiration_date = fields.Date("Expiration Date", track_visibility='onchange')
    status = fields.Selection(_STATUS, "Status", default='draft', track_visibility='onchange', copy=False)

    def unlink(self):
        if self.filtered(lambda x: x.status != 'draft'):
            raise ValidationError(_('Only draft records can be deleted.'))
        return super(HrAccreditation, self).unlink()


class HrPlantAccreditation(models.Model):
    _inherit = ['mail.thread', 'tf.hr.accreditation']
    _name = 'tf.hr.plant.accreditation'
    _description = "Plant Accreditation for Drivers/Helpers"
    _rec_name = 'plant_id'

    _STATUS = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('accredited', 'Accredited'),
        ('renewal', 'For Renewal'),
        ('expired', 'Expired')
    ]

    plant_id = fields.Many2one('res.partner', "Plant",
                               domain=['|', ('is_cement_plant', '=', True), ('is_batching_plant', '=', True)],
                               required=True,
                               help="Indicates the plant for accreditation.")
    requirement_status = fields.Selection(_STATUS, compute="_compute_req_status", track_visibility='onchange')
    cert_auth = fields.Char("Certification Authority")
    attachment = fields.Many2many('ir.attachment', string='Attachment',
                                  domain="[('res_model', '=', 'tf.hr.plant.accreditation'), ('res_id', '=', id)]")

    @api.depends('status')
    def _compute_req_status(self):
        plants_req_obj = self.env['tf.hr.logistic.plant.requirements']
        for rec in self:
            employee_id = rec.employee_id
            plant_req_id = plants_req_obj.search([('employee_id', '=', employee_id.id)])
            if plant_req_id.status == 'active':
                rec.update({
                    'requirement_status': 'active'
                })
            elif plant_req_id.status == 'renewal':
                rec.update({
                    'requirement_status': 'renewal'
                })
            elif plant_req_id.status == 'expired':
                rec.update({
                    'requirement_status': 'expired'
                })
            else:
                rec.update({
                    'requirement_status': 'draft'
                })

    def action_active(self):
        for rec in self:
            rec.write({'status': 'active'})

    def action_renewal(self):
        for rec in self:
            rec.write({'status': 'renewal'})

    def action_expired(self):
        for rec in self:
            rec.write({'status': 'expired'})

    def action_force_activation(self):
        for rec in self:
            rec.write({'status': 'active'})

    def action_force_expiration(self):
        for rec in self:
            rec.write({'status': 'expired'})

    def action_accredited(self):
        for rec in self:
            rec.write({'status': 'accredited'})

    @api.model
    def scheduler_status(self):
        plants_req_obj = self.env['tf.hr.logistic.plant.requirements']
        employee_id = self.employee_id

        # Get Plant Requirement
        plant_req_id = plants_req_obj.search([('employee_id', '=', employee_id.id)])

        # Get current date
        current_date = datetime.date.today()

        # Search for plants requirement for expiration today
        self.search([('status', 'in', ['active', 'accredited']),
                     ('expiration_date', '<=', current_date - relativedelta(days=1)),
                     ]).action_force_expiration()

        # Search for expiring plants requirement
        one_month_before = current_date + relativedelta(months=1)
        self.search([('status', 'in', ['active', 'accredited']),
                     ('expiration_date', '<=', one_month_before),
                     ('expiration_date', '>=', current_date)]).action_renewal()

        # Search for plant accreditation to be effective after expiring and expired
        self.search([('status', 'in', ['renewal', 'expired']),
                     ('expiration_date', '>', current_date)]).action_active()

        # Search for plant accreditation to be effective today
        self.search([('status', '=', 'draft'), ('effective_date', '<=', current_date)]).action_force_activation()

        if plant_req_id.status == 'active':
            plant_req_id.action_accredited()

        elif plant_req_id.status != 'active':
            plant_req_id.action_renewal()


class HrPlantsRequirements(models.Model):
    _inherit = ['mail.thread', 'tf.hr.accreditation']
    _name = 'tf.hr.logistic.plant.requirements'
    _description = "Plants Requirements"
    _rec_name = 'plant_acc_id'

    plant_acc_id = fields.Many2one('tf.hr.plant.accreditation', "Plant")
    requirement_type_id = fields.Many2one('res.partner', "Requirement Type", domain=[('is_cement_plant', '=', True)])
    # Particular, Consolidate records on each requirement type
    training_ids = fields.Many2many(related="requirement_type_id.training_ids")
    document_ids = fields.Many2many(related="requirement_type_id.document_ids")
    license_ids = fields.Many2many(related="requirement_type_id.license_ids")

    def action_active(self):
        for rec in self:
            rec.write({'status': 'active'})

    def action_renewal(self):
        for rec in self:
            rec.write({'status': 'renewal'})

    def action_expired(self):
        for rec in self:
            rec.write({'status': 'expired'})

    def action_force_activation(self):
        for rec in self:
            rec.write({'status': 'active'})

    def action_force_expiration(self):
        for rec in self:
            rec.write({'state': 'expired'})

    @api.model
    def scheduler_status(self):
        # Get current date
        current_date = datetime.date.today()

        # Search for plants requirement for expiration today
        self.search([('status', 'in', ['active', 'accredited']),
                     ('expiration_date', '<=', current_date - relativedelta(days=1)),
                     ]).action_force_expiration()

        # Search for expiring plants requirement
        one_month_before = current_date + relativedelta(months=1)
        self.search([('status', 'in', ['active', 'accredited']),
                     ('expiration_date', '<=', one_month_before),
                     ('expiration_date', '>=', current_date)]).action_renewal()

        # Search for plant accreditation to be effective after expiring and expired
        self.search([('status', 'in', ['renewal', 'expired']),
                     ('expiration_date', '>', current_date)]).action_active()

        # Search for plant accreditation to be effective today
        self.search([('status', '=', 'draft'), ('effective_date', '<=', current_date)]).action_force_activation()


class HrPlantDocs(models.Model):
    _inherit = ['mail.thread', 'tf.hr.accreditation']
    _name = 'tf.hr.doc.accreditation'
    _description = "Document Accreditation for Drivers/Helpers"
    _rec_name = 'type_id'

    type_id = fields.Many2one('tf.hr.logistic_doc.type', "Document Type")
    cert_auth = fields.Char("Certification Authority")
    attachment = fields.Many2many('ir.attachment', string='Attachment',
                                  domain="[('res_model', '=', 'tf.hr.plant.accreditation'), ('res_id', '=', id)]")

    @api.onchange('type_id')
    def _onchange_type_id(self):
        for rec in self:
            if rec.type_id.certification_authority:
                rec.cert_auth = rec.type_id.certification_authority

    def action_active(self):
        for rec in self:
            rec.write({'status': 'active'})

    def action_renewal(self):
        for rec in self:
            rec.write({'status': 'renewal'})

    def action_expired(self):
        for rec in self:
            rec.write({'status': 'expired'})

    def action_force_activation(self):
        for rec in self:
            rec.write({'status': 'active'})

    def action_force_expiration(self):
        for rec in self:
            rec.write({'state': 'expired'})

    @api.model
    def scheduler_status(self):
        # Get current date
        current_date = datetime.date.today()

        # Search for plants requirement for expiration today
        self.search([('status', 'in', ['active', 'accredited']),
                     ('expiration_date', '<=', current_date - relativedelta(days=1)),
                     ]).action_force_expiration()

        # Search for expiring plants requirement
        one_month_before = current_date + relativedelta(months=1)
        self.search([('status', 'in', ['active', 'accredited']),
                     ('expiration_date', '<=', one_month_before),
                     ('expiration_date', '>=', current_date)]).action_renewal()

        # Search for plant accreditation to be effective after expiring and expired
        self.search([('status', 'in', ['renewal', 'expired']),
                     ('expiration_date', '>', current_date)]).action_active()

        # Search for plant accreditation to be effective today
        self.search([('status', '=', 'draft'), ('effective_date', '<=', current_date)]).action_force_activation()


class HrLicenseDocs(models.Model):
    _inherit = ['mail.thread', 'tf.hr.accreditation']
    _name = 'tf.hr.license.accreditation'
    _description = "License Accreditation for Drivers/Helpers"
    _rec_name = 'type_id'

    type_id = fields.Many2one('tf.hr.logistic_license.type', "License Type")
    cert_auth = fields.Char("Certification Authority")
    attachment = fields.Many2many('ir.attachment', string='Attachment',
                                  domain="[('res_model', '=', 'tf.hr.license.accreditation'), ('res_id', '=', id)]")

    @api.onchange('type_id')
    def _onchange_type_id(self):
        for rec in self:
            if rec.type_id.certification_authority:
                rec.cert_auth = rec.type_id.certification_authority

    def action_active(self):
        for rec in self:
            rec.write({'status': 'active'})

    def action_renewal(self):
        for rec in self:
            rec.write({'status': 'renewal'})

    def action_expired(self):
        for rec in self:
            rec.write({'status': 'expired'})

    def action_force_activation(self):
        for rec in self:
            rec.write({'status': 'active'})

    def action_force_expiration(self):
        for rec in self:
            rec.write({'state': 'expired'})

    @api.model
    def scheduler_status(self):
        # Get current date
        current_date = datetime.date.today()

        # Search for plants requirement for expiration today
        self.search([('status', 'in', ['active', 'accredited']),
                     ('expiration_date', '<=', current_date - relativedelta(days=1)),
                     ]).action_force_expiration()

        # Search for expiring plants requirement
        one_month_before = current_date + relativedelta(months=1)
        self.search([('status', 'in', ['active', 'accredited']),
                     ('expiration_date', '<=', one_month_before),
                     ('expiration_date', '>=', current_date)]).action_renewal()

        # Search for plant accreditation to be effective after expiring and expired
        self.search([('status', 'in', ['renewal', 'expired']),
                     ('expiration_date', '>', current_date)]).action_active()

        # Search for plant accreditation to be effective today
        self.search([('status', '=', 'draft'), ('effective_date', '<=', current_date)]).action_force_activation()


class HrTrainingDocs(models.Model):
    _inherit = ['mail.thread', 'tf.hr.accreditation']
    _name = 'tf.hr.training.accreditation'
    _description = "Training Accreditation for Drivers/Helpers"
    _rec_name = 'training_list_id'

    training_list_id = fields.Many2one('ss.hris.training.checklist', domain="[('employee_id', '=', employee_id)]")
    training_id = fields.Many2one('ss.hris.training.config', 'Training',
                                  related="training_list_id.item_ids.requirement_id")
    session_id = fields.Many2one('ss.hris.training', related="training_list_id.item_ids.training_id")
    course_id = fields.Many2one('ss.hris.training.course', related="training_list_id.item_ids.course_id")
    deadline = fields.Date(related="training_list_id.deadline_date")
    date_completed = fields.Datetime(related="training_list_id.date_completed", track_visibility='onchange')
    expiration_date = fields.Date("Expiration Date", compute="get_expiration_date", store=True,
                                  track_visibility='onchange')
    expiration_duration = fields.Integer(track_visibility='onchange')
    item_ids = fields.One2many(related='training_list_id.item_ids')

    @api.depends('training_list_id', 'date_completed', 'expiration_duration')
    def get_expiration_date(self):
        for rec in self:
            if not rec.date_completed:
                rec.update({
                    'expiration_date': ''
                })
            else:
                date_completed = rec.date_completed
                date_expiry = date_completed + relativedelta(days=int(rec.expiration_duration))
                date_expiry = date_expiry.strftime('%Y-%m-%d')
                rec.update({
                    'expiration_date': date_expiry
                })

    def action_active(self):
        for rec in self:
            rec.write({'status': 'active'})

    def action_renewal(self):
        for rec in self:
            rec.write({'status': 'renewal'})

    def action_expired(self):
        for rec in self:
            rec.write({'status': 'expired'})

    def action_force_activation(self):
        for rec in self:
            rec.write({'status': 'active'})

    def action_force_expiration(self):
        for rec in self:
            rec.write({'state': 'expired'})

    @api.model
    def scheduler_status(self):
        # Get current date
        current_date = datetime.date.today()

        # Search for plants requirement for expiration today
        self.search([('status', 'in', ['active', 'accredited']),
                     ('expiration_date', '<=', current_date - relativedelta(days=1)),
                     ]).action_force_expiration()

        # Search for expiring plants requirement
        one_month_before = current_date + relativedelta(months=1)
        self.search([('status', 'in', ['active', 'accredited']),
                     ('expiration_date', '<=', one_month_before),
                     ('expiration_date', '>=', current_date)]).action_renewal()

        # Search for plant accreditation to be effective after expiring and expired
        self.search([('status', 'in', ['renewal', 'expired']),
                     ('expiration_date', '>', current_date)]).action_active()

        # Search for plant accreditation to be effective today
        self.search([('status', '=', 'draft'), ('effective_date', '<=', current_date)]).action_force_activation()


class DHAttendance(models.Model):
    _name = 'tf.hr.dh.attendance'
    _description = 'Driver/Helper Attendance'

    employee_id = fields.Many2one('hr.employee', 'Employee', required=True, index=True)
    employee_domain_ids = fields.Many2many('hr.employee', 'attendance_employee_domain_rel',
                                           compute='_compute_domain')
    job_id = fields.Many2one(related='employee_id.job_id', store=True)
    display_name = fields.Char(related='employee_id.display_name', string='Employee Name', store=True)
    from_date = fields.Date('From', required=True, copy=False)
    to_date = fields.Date('To', required=True, copy=False)
    state = fields.Selection(_DH_AVAILABILITY,
                             default='available', required=True)

    @api.depends('employee_id')
    def _compute_domain(self):
        HrEmployee = self.env['hr.employee']
        for rec in self:
            rec.employee_domain_ids = HrEmployee.search([('is_dh', '=', True)])

    @api.model
    def _get_attendance_state(self, employee, date):
        # Convenience function to retrieve the state of attendance of employee on given date
        attendance = self.search([
            ('employee_id', '=', employee.id),
            ('from_date', '<=', date),
            ('to_date', '>=', date)
        ])
        if attendance:
            return attendance.state
        else:
            return 'unavailable'

    @api.model_create_multi
    def create(self, vals_list):
        # If created attendance falls on current day, automatically set the D/H Availability for the day
        for vals in vals_list:
            employee = vals.get('employee_id')
            from_date = vals.get('from_date')
            to_date = vals.get('to_date')

            if not from_date or not to_date:
                raise ValidationError(_('From/To Date is required.'))

            if to_date < vals.get('from_date'):
                raise ValidationError(_('To Date cannot be earlier than From Date.'))

            attendances = self.search([
                ('employee_id', '=', employee),
                '|', '|', '|',
                '&', ('from_date', '<=', from_date), ('to_date', '>=', from_date),
                '&', ('from_date', '<=', to_date), ('to_date', '>=', to_date),
                '&', ('from_date', '<=', from_date), ('to_date', '>=', to_date),
                '&', ('from_date', '>=', from_date), ('to_date', '<=', to_date),
            ])
            if attendances:
                raise ValidationError(_('Driver/Helper attendance overlaps with an existing attendance entry.'))

        result = super(DHAttendance, self).create(vals_list)

        for attendance in result:
            employee = attendance.employee_id
            today = fields.Date.context_today(self)
            if attendance.from_date <= today <= attendance.to_date:
                employee.sudo().write({'dh_availability': attendance.state})

        return result

    def unlink(self):
        for attendance in self:
            today = fields.Date.context_today(self)
            if attendance.state == 'available' and attendance.from_date <= today <= attendance.to_date:
                attendance.employee_id.sudo().write({'dh_availability': 'unavailable'})
        return super(DHAttendance, self).unlink()

    @api.model
    def set_dh_availability(self, employees=None):
        # Update the DH Availability status of each DH based on current date
        # Ideally must run every 12AM
        if not employees:
            employees = self.env['hr.employee'].search([('is_dh', '=', True)])

        for employee in employees:
            attendance_state = self._get_attendance_state(employee, fields.Date.context_today(self))
            if employee.dh_availability != attendance_state:
                # Only update if necessary to reduce no. of database writes
                employee.sudo().write({'dh_availability': attendance_state})

    def write(self, vals):
        res = super(DHAttendance, self).write(vals)
        if 'from_date' in vals or 'to_date' in vals:
            # change in dates detected, so update corresponding employee
            self.set_dh_availability(self.mapped('employee_id'))
        return res
