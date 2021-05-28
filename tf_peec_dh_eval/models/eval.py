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
import time

from dateutil.rrule import *
from lxml import etree

from odoo import api, fields, models, _
from odoo.addons.base.models.ir_ui_view import transfer_field_to_modifiers, transfer_modifiers_to_node, \
    transfer_node_to_modifiers
from odoo.exceptions import ValidationError


class DhEval(models.Model):
    _name = "tf.dh.eval"
    _description = "Evaluation for Driver/Helper"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    STATES = [
        ('draft', "Draft"),
        ('confirm', "Confirmed"),
        ('approval', "For Approval"),
        ('approve', "Approved"),
        ('cancel', "Cancelled"),
        ('reject', "For Revision"),
    ]

    name = fields.Char("Name", copy=False, track_visibility='onchange', default="Draft Evaluation",
                       help="Indicates the appraisal identifier.")
    description = fields.Char("Description", track_visibility='onchange')
    from_date = fields.Date('From', default=time.strftime('%Y-01-01'), required=True, track_visibility='onchange')
    to_date = fields.Date('To', default=time.strftime('%Y-12-31'), required=True, track_visibility='onchange')
    config_id = fields.Many2one('tf.dh.eval.config', "Rating Configuration", track_visibility='onchange',
                                required=True, domain="[('active', '=', True)]")
    state = fields.Selection(STATES, default='draft', copy=False, track_visibility='onchange',
                             help="Indicates the current status of the evaluation.")
    reject_reason = fields.Char("Reject Reason", copy=False, track_visibility='onchange')
    approver_id = fields.Many2one('res.users', "Approved By", readonly=True, copy=False)
    approve_date = fields.Date("Approval Date")
    contract_ids = fields.Many2many('ss.hris.contract', 'dh_eval_contract_rel', 'eval_id', 'contract_id',
                                    string='Contracts', require=True,
                                    domain="[('position_id.is_dh','=',True),('state', 'in', ['active', 'resignation'])]")
    n_months = fields.Integer("Number of Months", compute="get_n_months", store=True, copy=False,
                              help="Indicates the number of months found in the interval.")
    line_ids = fields.One2many('tf.dh.eval.line', 'eval_id', "Report Lines", copy=False)

    @api.depends('from_date', 'to_date')
    def get_n_months(self):
        for rec in self:
            from_date = rec.from_date
            to_date = rec.to_date

            if from_date and to_date:
                if from_date > to_date:
                    raise ValidationError("End date (%s) should not be before the start start date (%s)" %
                                          (to_date, from_date))

                months = [dt.date() for dt in rrule(MONTHLY, dtstart=from_date, until=to_date)]
                rec.n_months = len(months)
            else:
                rec.n_months = 0

    def action_confirm(self):
        sequence_obj = self.env['ir.sequence']
        for rec in self:
            # Check for contracts
            if not rec.contract_ids:
                raise ValidationError(_('No contracts selected. Unable to Confirm.'))

            rec.write({
                'name': sequence_obj.sudo().next_by_code('tf.dh.eval'),
                'state': 'confirm'
            })

    def action_for_approval(self):
        self.write({
            'state': 'approval'
        })

    def action_approve(self):
        if not self.line_ids:
            raise ValidationError(_("There is no data to approve."))

        self.write({
            'approver_id': self.env.uid,
            'approve_date': fields.Datetime.now(),
            'state': 'approve'
        })
        self.distribute_badges()

    def action_reject_wizard(self):
        self.ensure_one()
        return {
            'name': 'Reject Evaluation',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'tf.dh.eval.reject',
            'view_id': self.env.ref('tf_peec_dh_eval.tf_dh_eval_reject_view_form').id,
            'context': {'default_eval_id': self.id},
            'type': 'ir.actions.act_window',
            'target': 'new'
        }

    def action_reject(self, reject_reason):
        self.write({
            'state': 'reject',
            'reject_reason': reject_reason
        })

    def action_cancel(self):
        self.write({'state': 'cancel'})
        self.mapped('line_ids').unlink()

    def action_generate_report(self):
        trip_report_obj = self.env['logistics.trip.report']
        eval_line_obj = self.env['tf.dh.eval.line']
        infraction_obj = self.env['ss.hris.infraction']
        leave_obj = self.env['ss.hris.leave']

        for rec in self:
            # Delete existing report lines
            if rec.line_ids:
                rec.line_ids.unlink()

            # Init
            from_date = rec.from_date
            to_date = rec.to_date
            config_id = rec.config_id

            # Process per contract
            for contract_id in rec.contract_ids:
                others_score = accident_score = speeding_score = leaves_score = 1
                employee_id = contract_id.employee_id.id
                vals = {
                    'eval_id': rec.id,
                    'employee_id': employee_id
                }

                # Productivity
                trip_ids = trip_report_obj.search([
                    ('delivery_date', '>=', from_date),
                    ('delivery_date', '<=', to_date),
                    ('employee_id', '=', employee_id)
                ])
                if trip_ids:
                    vals['trip_ids'] = [(6, 0, trip_ids.ids)]
                    vals['prod_score'] = config_id.get_prod_score(len(trip_ids))
                    for i in range(1, 13):
                        month_trip_ids = trip_ids.filtered(lambda t: t.delivery_date.month == i)
                        if month_trip_ids:
                            vals['prod_month_%i' % i] = len(month_trip_ids)

                # Corporate - Accidents
                accident_ids = infraction_obj.search([
                    ('infraction_type_id', '=', config_id.accident_infra_id.id),
                    ('action_ids', 'in', [config_id.accident_action_id.id]),
                    ('incident_date', '>=', from_date),
                    ('incident_date', '<=', to_date),
                    ('employee_id', '=', employee_id),
                    ('state', 'in', ['in_progress', 'done'])
                ])
                if accident_ids:
                    accident_score -= config_id.get_accident_score(len(accident_ids))
                    vals['accident_ids'] = [(6, 0, accident_ids.ids)]
                    vals['accident_score'] = accident_score

                    for i in range(1, 13):
                        month_accident_ids = accident_ids.filtered(lambda a: a.incident_date.month == i)
                        if month_accident_ids:
                            vals['accident_month_%i' % i] = len(month_accident_ids)

                # Corporate - Speeding
                speeding_ids = infraction_obj.search([
                    ('infraction_type_id', '=', config_id.speeding_infra_id.id),
                    ('action_ids', 'in', [config_id.speeding_action_id.id]),
                    ('incident_date', '>=', from_date),
                    ('incident_date', '<=', to_date),
                    ('employee_id', '=', employee_id),
                    ('state', 'in', ['in_progress', 'done'])
                ])
                if speeding_ids:
                    speeding_score -= config_id.get_speeding_score(len(speeding_ids))
                    vals['speeding_ids'] = [(6, 0, speeding_ids.ids)]
                    vals['speeding_score'] = speeding_score

                    for i in range(1, 13):
                        month_speeding_ids = speeding_ids.filtered(lambda a: a.incident_date.month == i)
                        if month_speeding_ids:
                            vals['speeding_month_%i' % i] = len(month_speeding_ids)

                # Corporate - Others
                other_ids = infraction_obj.search([
                    ('infraction_type_id', '=', config_id.other_infra_id.id),
                    ('action_ids', 'in', [config_id.other_action_id.id]),
                    ('incident_date', '>=', from_date),
                    ('incident_date', '<=', to_date),
                    ('employee_id', '=', employee_id),
                    ('state', 'in', ['in_progress', 'done'])
                ])
                if other_ids:
                    others_score -= config_id.get_others_score(len(other_ids))
                    vals['other_ids'] = [(6, 0, other_ids.ids)]
                    vals['others_score'] = others_score

                    for i in range(1, 13):
                        month_other_ids = other_ids.filtered(lambda a: a.incident_date.month == i)
                        if month_other_ids:
                            vals['others_month_%i' % i] = len(month_other_ids)

                # Corporate - Leaves
                leave_ids = leave_obj.search([
                    ('type_id', 'in', config_id.leave_type_ids.ids),
                    ('date', '>=', from_date),
                    ('date', '<=', to_date),
                    ('employee_id', '=', employee_id),
                    ('state', 'in', ['approve', 'done']),
                    ('mode', '=', 'consume'),
                ])
                if leave_ids:
                    leaves_score -= config_id.get_leaves_score(len(leave_ids))
                    vals['leave_ids'] = [(6, 0, leave_ids.ids)]
                    vals['leaves_score'] = leaves_score

                    for i in range(1, 13):
                        month_leave_ids = leave_ids.filtered(lambda a: a.date.month == i)
                        if month_leave_ids:
                            vals['leaves_month_%i' % i] = len(month_leave_ids)

                # Corporate - Sum
                vals['corpo_score'] = (accident_score + speeding_score + others_score + leaves_score) / 4

                # Create Report Lines
                eval_line_obj.create(vals)

    def distribute_badges(self):
        for line_id in self.line_ids:
            for badge_id in line_id.badge_ids:
                values = {
                    'user_id': line_id.employee_id.user_id.id,
                    'sender_id': self.env.uid,
                    'badge_id': badge_id.id,
                    'employee_id': line_id.employee_id.id,
                    'comment': self.comment,
                }
                return self.env['gamification.badge.user'].create(values)._send_badge()

    def view_prod(self):
        return {
            'name': "%s - %s Productivity Report" % (self.from_date, self.to_date),
            'view_mode': 'tree',
            'view_id': self.env.ref('tf_peec_dh_eval.tf_dh_eval_prod_report_view_tree').id,
            'res_model': 'tf.dh.eval.line',
            'domain': [('eval_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {'active_id': self.id}
        }

    def view_corpo(self):
        return {
            'name': "%s - %s Corporate Report" % (self.from_date, self.to_date),
            'view_mode': 'tree',
            'view_id': self.env.ref('tf_peec_dh_eval.tf_dh_eval_corpo_report_view_tree').id,
            'res_model': 'tf.dh.eval.line',
            'domain': [('eval_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {'active_id': self.id}
        }

    def view_skills(self):
        return {
            'name': "%s - %s Skills Report" % (self.from_date, self.to_date),
            'view_mode': 'tree',
            'view_id': self.env.ref('tf_peec_dh_eval.tf_dh_eval_skills_report_view_tree').id,
            'res_model': 'tf.dh.eval.line',
            'domain': [('eval_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {'active_id': self.id}
        }

    def view_summary(self):
        return {
            'name': "%s - %s Summary Report" % (self.from_date, self.to_date),
            'view_mode': 'tree',
            'view_id': self.env.ref('tf_peec_dh_eval.tf_dh_eval_summary_report_view_tree').id,
            'res_model': 'tf.dh.eval.line',
            'domain': [('eval_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {'active_id': self.id}
        }

    def unlink(self):
        if self.filtered(lambda x: x.state != 'draft'):
            raise ValidationError(_('Only draft records can be deleted.'))
        return super(DhEval, self).unlink()


class DhEvalLine(models.Model):
    _name = "tf.dh.eval.line"
    _description = "Evaluation Lines for Driver/Helper"

    eval_id = fields.Many2one('tf.dh.eval', "Evaluation Record", ondelete='cascade')
    config_id = fields.Many2one(related='eval_id.config_id')
    employee_id = fields.Many2one('hr.employee', "Employee")
    barcode = fields.Char("ID", related='employee_id.barcode')
    first_name = fields.Char(related='employee_id.first_name')
    middle_name = fields.Char(related='employee_id.middle_name')
    last_name = fields.Char(related='employee_id.last_name')
    work_location = fields.Char(related='employee_id.work_location', store=True)
    job_title = fields.Char(related='employee_id.job_title', store=True)
    rank_id = fields.Many2one(related='employee_id.rank_id', store=True)

    # Productivity
    prod_month_1 = fields.Integer("January (Trips)")
    prod_month_2 = fields.Integer("February (Trips)")
    prod_month_3 = fields.Integer("March (Trips)")
    prod_month_4 = fields.Integer("April (Trips)")
    prod_month_5 = fields.Integer("May (Trips)")
    prod_month_6 = fields.Integer("June (Trips)")
    prod_month_7 = fields.Integer("July (Trips)")
    prod_month_8 = fields.Integer("August (Trips)")
    prod_month_9 = fields.Integer("September (Trips)")
    prod_month_10 = fields.Integer("October (Trips)")
    prod_month_11 = fields.Integer("November (Trips)")
    prod_month_12 = fields.Integer("December (Trips)")
    prod_total = fields.Integer("Total Trips", compute="compute_prod", store=True)
    trip_ids = fields.Many2many('logistics.trip.report', 'dh_eval_line_trip_rel', 'line_id', 'trip_id', "Trips")
    avg_trip = fields.Float("Average Trips", compute="compute_prod", store=True)
    prod_score = fields.Float("Productivity Score")

    # Corporate - Accident
    accident_month_1 = fields.Integer("Jan (Accidents)")
    accident_month_2 = fields.Integer("Feb (Accidents)")
    accident_month_3 = fields.Integer("Mar (Accidents)")
    accident_month_4 = fields.Integer("Apr (Accidents)")
    accident_month_5 = fields.Integer("May (Accidents)")
    accident_month_6 = fields.Integer("Jun (Accidents)")
    accident_month_7 = fields.Integer("Jul (Accidents)")
    accident_month_8 = fields.Integer("Aug (Accidents)")
    accident_month_9 = fields.Integer("Sep (Accidents)")
    accident_month_10 = fields.Integer("Oct (Accidents)")
    accident_month_11 = fields.Integer("Nov (Accidents)")
    accident_month_12 = fields.Integer("Dec (Accidents)")
    accident_total = fields.Integer("Total (Accidents)", compute="compute_accident", store=True)
    acc_sus_days = fields.Integer("Days Suspended (Accidents)")
    accident_ids = fields.Many2many('ss.hris.infraction', 'dh_eval_line_accident_rel', 'line_id', 'infraction_id',
                                    "Accidents")
    avg_accident = fields.Float("Average (Accidents)", compute="compute_accident", store=True)
    accident_score = fields.Float("Safety Score")

    # Corporate - Over Speeding
    speeding_month_1 = fields.Integer("Jan (Speeding)")
    speeding_month_2 = fields.Integer("Feb (Speeding)")
    speeding_month_3 = fields.Integer("Mar (Speeding)")
    speeding_month_4 = fields.Integer("Apr (Speeding)")
    speeding_month_5 = fields.Integer("May (Speeding)")
    speeding_month_6 = fields.Integer("Jun (Speeding)")
    speeding_month_7 = fields.Integer("Jul (Speeding)")
    speeding_month_8 = fields.Integer("Aug (Speeding)")
    speeding_month_9 = fields.Integer("Sep (Speeding)")
    speeding_month_10 = fields.Integer("Oct (Speeding)")
    speeding_month_11 = fields.Integer("Nov (Speeding)")
    speeding_month_12 = fields.Integer("Dec (Speeding)")
    speeding_total = fields.Integer("Total (Speeding)", compute="compute_speeding", store=True)
    spd_sus_days = fields.Integer("Days Suspended (Speeding)")
    speeding_ids = fields.Many2many('ss.hris.infraction', 'dh_eval_line_speeding_rel', 'line_id', 'infraction_id',
                                    "Speeding Records")
    avg_speeding = fields.Float("Average (Speeding)", compute="compute_speeding", store=True)
    speeding_score = fields.Float("Overspeeding Score")

    # Corporate - Other
    others_month_1 = fields.Integer("Jan (Others)")
    others_month_2 = fields.Integer("Feb (Others)")
    others_month_3 = fields.Integer("Mar (Others)")
    others_month_4 = fields.Integer("Apr (Others)")
    others_month_5 = fields.Integer("May (Others)")
    others_month_6 = fields.Integer("Jun (Others)")
    others_month_7 = fields.Integer("Jul (Others)")
    others_month_8 = fields.Integer("Aug (Others)")
    others_month_9 = fields.Integer("Sep (Others)")
    others_month_10 = fields.Integer("Oct (Others)")
    others_month_11 = fields.Integer("Nov (Others)")
    others_month_12 = fields.Integer("Dec (Others)")
    others_total = fields.Integer("Total (Others)", compute="compute_others", store=True)
    other_sus_days = fields.Integer("Days Suspended (Others)")
    other_ids = fields.Many2many('ss.hris.infraction', 'dh_eval_line_others_rel', 'line_id', 'infraction_id',
                                 "Other Infraction Records")
    avg_others = fields.Float("Average (Others)", compute="compute_others", store=True)
    others_score = fields.Float("Others Score")

    # Corporate - Leaves
    leaves_month_1 = fields.Integer("Jan (Leaves)")
    leaves_month_2 = fields.Integer("Feb (Leaves)")
    leaves_month_3 = fields.Integer("Mar (Leaves)")
    leaves_month_4 = fields.Integer("Apr (Leaves)")
    leaves_month_5 = fields.Integer("May (Leaves)")
    leaves_month_6 = fields.Integer("Jun (Leaves)")
    leaves_month_7 = fields.Integer("Jul (Leaves)")
    leaves_month_8 = fields.Integer("Aug (Leaves)")
    leaves_month_9 = fields.Integer("Sep (Leaves)")
    leaves_month_10 = fields.Integer("Oct (Leaves)")
    leaves_month_11 = fields.Integer("Nov (Leaves)")
    leaves_month_12 = fields.Integer("Dec (Leaves)")
    leaves_total = fields.Integer("Total (Leaves)", compute="compute_leaves", store=True)
    leave_ids = fields.Many2many('ss.hris.leave', 'dh_eval_line_leaves_rel', 'line_id', 'leave_id', "Leave Records")
    leaves_score = fields.Float("Leaves Score")

    # Corporate - Sum
    corpo_score = fields.Float("Corporate Score")

    # Skills
    skills_score = fields.Float("Skills")

    # Summary
    total_score = fields.Float("Total Rating", compute="get_summary", store=True)
    rating = fields.Char("Rating", compute="get_summary", store=True)
    badge_ids = fields.Many2many('gamification.badge', string='Badges', compute="get_summary", store=True)

    @api.constrains('accident_score', 'speeding_score', 'others_score', 'leaves_score',
                    'corpo_score', 'skills_score', 'prod_score')
    def _check_scores(self):
        for rec in self:
            if rec.prod_score < 0 \
                    or rec.accident_score < 0 \
                    or rec.speeding_score < 0 \
                    or rec.others_score < 0 \
                    or rec.leaves_score < 0 \
                    or rec.corpo_score < 0 \
                    or rec.skills_score < 0:
                raise ValidationError(_("Scores cannot be negative."))

    @api.depends('prod_score', 'corpo_score', 'skills_score')
    def get_summary(self):
        for rec in self:
            total_score, rating, badge_ids = rec.config_id.get_summary_score(rec.prod_score, rec.corpo_score,
                                                                             rec.skills_score)
            rec.total_score = total_score
            rec.rating = rating
            rec.badge_ids = badge_ids

    @api.depends('trip_ids')
    def compute_prod(self):
        for rec in self:
            n_months = rec.eval_id.n_months
            trip_ids = rec.trip_ids
            prod_total = len(trip_ids)
            rec.prod_total = prod_total
            rec.avg_trip = prod_total / n_months

    @api.depends('accident_ids')
    def compute_accident(self):
        for rec in self:
            n_months = rec.eval_id.n_months
            accident_ids = rec.accident_ids
            accident_total = len(accident_ids)
            rec.acc_sus_days = accident_total * rec.config_id.accident_action_id.days
            rec.accident_total = accident_total
            rec.avg_accident = accident_total / n_months

    @api.depends('speeding_ids')
    def compute_speeding(self):
        for rec in self:
            n_months = rec.eval_id.n_months
            speeding_ids = rec.speeding_ids
            speeding_total = len(speeding_ids)
            rec.spd_sus_days = speeding_total * rec.config_id.speeding_action_id.days
            rec.speeding_total = speeding_total
            rec.avg_speeding = speeding_total / n_months

    @api.depends('other_ids')
    def compute_others(self):
        for rec in self:
            n_months = rec.eval_id.n_months
            other_ids = rec.other_ids
            others_total = len(other_ids)
            rec.other_sus_days = others_total * rec.config_id.other_action_id.days
            rec.others_total = others_total
            rec.avg_others = others_total / n_months

    @api.depends('leave_ids')
    def compute_leaves(self):
        for rec in self:
            rec.leaves_total = len(rec.leave_ids)

    def action_view_trips(self):
        view = self.env.ref('tf_peec_dh_eval.logistics_trip_report_view_tree_readonly')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Trip Summary',
            'res_model': 'logistics.trip.report',
            'domain': [('id', 'in', self.trip_ids.ids)],
            'view_id': view.id,
            'view_mode': 'tree',
            'target': 'current',
        }

    def action_view_accident(self):
        view = self.env.ref('ss_hris_infraction.ss_hris_infraction_tree_approval')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Infraction Summary',
            'res_model': 'ss.hris.infraction',
            'domain': [('id', 'in', self.accident_ids.ids)],
            'views': [(view.id, 'tree'), (False, 'form')],
            'view_mode': 'tree,form',
            'target': 'current',
        }

    def action_view_speeding(self):
        view = self.env.ref('ss_hris_infraction.ss_hris_infraction_tree_approval')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Infraction Summary',
            'res_model': 'ss.hris.infraction',
            'domain': [('id', 'in', self.speeding_ids.ids)],
            'views': [(view.id, 'tree'), (False, 'form')],
            'view_mode': 'tree,form',
            'target': 'current',
        }

    def action_view_others(self):
        view = self.env.ref('ss_hris_infraction.ss_hris_infraction_tree_approval')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Infraction Summary',
            'res_model': 'ss.hris.infraction',
            'domain': [('id', 'in', self.other_ids.ids)],
            'views': [(view.id, 'tree'), (False, 'form')],
            'view_mode': 'tree,form',
            'target': 'current',
        }

    def action_view_leaves(self):
        view = self.env.ref('ss_hris_leave.ss_hris_leave_view_tree')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Leaves Summary',
            'res_model': 'ss.hris.leave',
            'domain': [('id', 'in', self.leave_ids.ids)],
            'views': [(view.id, 'tree'), (False, 'form')],
            'view_mode': 'tree',
            'target': 'current',
        }

    @api.model
    def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
        res = super(DhEvalLine, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                      submenu=submenu)

        doc = etree.XML(res['arch'])
        prod_view_id = self.env.ref('tf_peec_dh_eval.tf_dh_eval_prod_report_view_tree').id
        corpo_view_id = self.env.ref('tf_peec_dh_eval.tf_dh_eval_corpo_report_view_tree').id
        active_id = self.env.context.get('active_id', False)
        if active_id:
            eval_id = self.env['tf.dh.eval'].browse(active_id)
            months = [dt.month for dt in rrule(MONTHLY, dtstart=eval_id.from_date, until=eval_id.to_date)]
            # Productivity Report
            if view_id == prod_view_id:
                for i in range(1, 13):
                    if i in months:
                        for field in doc.xpath("//field[@name='prod_month_%s']" % i):
                            field.set('invisible', '0')
                            setup_modifiers(field, res['fields']['prod_month_%s' % i])
            # Corporate Report
            elif view_id == corpo_view_id:
                for i in range(1, 13):
                    if i in months:
                        # Accidents
                        for field in doc.xpath("//field[@name='accident_month_%s']" % i):
                            field.set('invisible', '0')
                            setup_modifiers(field, res['fields']['accident_month_%s' % i])
                        # Over-speeding
                        for field in doc.xpath("//field[@name='speeding_month_%s']" % i):
                            field.set('invisible', '0')
                            setup_modifiers(field, res['fields']['speeding_month_%s' % i])
                        # Others
                        for field in doc.xpath("//field[@name='others_month_%s']" % i):
                            field.set('invisible', '0')
                            setup_modifiers(field, res['fields']['others_month_%s' % i])
                        # Leaves
                        for field in doc.xpath("//field[@name='leaves_month_%s']" % i):
                            field.set('invisible', '0')
                            setup_modifiers(field, res['fields']['leaves_month_%s' % i])

        res['arch'] = etree.tostring(doc)
        return res


# Add back missing functions from Odoo 12
def setup_modifiers(node, field=None, context=None, in_tree_view=False):
    """ Processes node attributes and field descriptors to generate
    the ``modifiers`` node attribute and set it on the provided node.
    Alters its first argument in-place.
    :param node: ``field`` node from an OpenERP view
    :type node: lxml.etree._Element
    :param dict field: field descriptor corresponding to the provided node
    :param dict context: execution context used to evaluate node attributes
    :param bool in_tree_view: triggers the ``column_invisible`` code
                              path (separate from ``invisible``): in
                              tree view there are two levels of
                              invisibility, cell content (a column is
                              present but the cell itself is not
                              displayed) with ``invisible`` and column
                              invisibility (the whole column is
                              hidden) with ``column_invisible``.
    :returns: nothing
    """
    modifiers = {}
    if field is not None:
        transfer_field_to_modifiers(field, modifiers)
    transfer_node_to_modifiers(
        node, modifiers, context=context, in_tree_view=in_tree_view)
    transfer_modifiers_to_node(modifiers, node)
