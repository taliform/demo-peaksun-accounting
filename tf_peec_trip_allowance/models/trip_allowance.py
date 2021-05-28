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
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError

_STATES = [
    ('draft', 'Draft'),
    ('confirm', 'Confirmed'),
    ('compute', 'Computed'),
    ('validate', 'Validated'),
    ('generate', 'Generated')
]


class TripAllowance(models.Model):
    _name = 'tf.hr.dh.trip.allowance'
    _description = 'Trip Allowance'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Reference', default='Draft Trip Allowance')
    duration_from = fields.Date('From', required=True)
    duration_to = fields.Date('To', required=True)
    is_non_payroll = fields.Boolean('Non-Payroll', default=lambda self: self.env.company.trip_allowance_non_payroll)
    line_ids = fields.One2many('tf.hr.dh.trip.allowance.line', 'ta_id', 'Allowance Lines')
    state = fields.Selection(_STATES, default='draft')
    total_amount = fields.Monetary('Total Amount', compute='_compute_total_amount', store=True)
    total_paid = fields.Monetary('Paid Amount', compute='_compute_total_paid', store=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    notes = fields.Text()
    adjustment_ids = fields.One2many('ss.hris.salary_adjustment', 'ta_id', 'Salary Adjustments')
    adjustment_count = fields.Integer('No. of Salary Adjustments', compute='_compute_adjustments_count')

    def _compute_adjustments_count(self):
        """ Count the number of trip logs """
        for rec in self:
            stat_data = self.env['ss.hris.salary_adjustment'].read_group(
                [('id', 'in', rec.adjustment_ids.ids)], ['ta_id'], ['ta_id'])
            mapped_data = dict([(m['ta_id'][0], m['ta_id_count']) for m in stat_data])
            rec.adjustment_count = mapped_data.get(rec.id, 0)

    @api.depends('line_ids.amount')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('amount'))

    @api.depends('line_ids.adjustment_id', 'line_ids.adjustment_state')
    def _compute_total_paid(self):
        for rec in self:
            paid_adjustments = rec.line_ids.filtered(lambda a: a.adjustment_state == 'done')
            rec.paid_amount = sum(paid_adjustments.mapped('amount'))

    def action_confirm(self):
        sequence_obj = self.env['ir.sequence']
        for rec in self:
            rec.write({
                'name': sequence_obj.sudo().next_by_code('tf.hr.dh.trip.allowance'),
                'state': 'confirm'
            })

    def _action_compute_rates(self):
        # Build Trip Allowance Rates Dictionary
        rates = self.env['tf.hr.dh.trip.allowance.rate'].read_group([], ['job_id', 'rank_id', 'rate'],
                                                                    ['job_id', 'rank_id'], lazy=False)
        mapped_rates = dict([("%s-%s" % (m['job_id'][0], m['rank_id'][0]), m['rate']) for m in rates])

        for rec in self:
            for line in rec.line_ids:
                rate = mapped_rates.get("%s-%s" % (line.job_id.id, line.rank_id.id), 0)
                line.write({
                    'rate': rate,
                    'amount': rate * line.no_of_days,
                })

    def _action_compute(self):
        # Search DH Attendances based on duration
        for rec in self:
            attendance_domain = [
                ('from_date', '>=', rec.duration_from),
                ('to_date', '<=', rec.duration_to),
                ('state', '=', 'available')
            ]

            line_vals = []

            attendance_data = self.env['tf.hr.dh.attendance'].read_group(attendance_domain, ['employee_id'],
                                                                         ['employee_id'])
            for attendance in attendance_data:
                line_vals.append(
                    (0, 0, {
                        'employee_id': attendance['employee_id'][0],
                        'no_of_days': attendance['employee_id_count']
                    })
                )

            return {
                'line_ids': line_vals
            }

    def action_compute(self):
        for rec in self:
            vals = rec._action_compute()
            vals['state'] = 'compute'
            rec.write(vals)
            rec._action_compute_rates()

    def action_recompute(self):
        for rec in self:
            vals = rec._action_compute()
            rec.line_ids.unlink()
            rec.write(vals)
            rec._action_compute_rates()

    def action_validate(self):
        for rec in self:
            rec.write({'state': 'validate'})

    def _action_generate(self):
        for rec in self:
            if not rec.is_non_payroll:
                for attendance in rec.line_ids:
                    adjustment = self.env['ss.hris.salary_adjustment'].create({
                        'employee_id': attendance.employee_id.id,
                        'type_id': self.env.company.trip_allowance_salary_adjustment_type_id.id,
                        'amount': attendance.amount,
                        'reference': rec.name,
                        'ta_id': rec.id,
                    })
                    attendance.write({'adjustment_id': adjustment.id})

    def action_generate(self):
        for rec in self:
            rec._action_generate()
            rec.write({'state': 'generate'})

    def action_regenerate(self):
        for rec in self:
            for adjustment in rec.adjustment_ids:
                if adjustment.state == 'draft':
                    adjustment.unlink()
                elif adjustment.state != 'done':
                    adjustment.write({'ta_id': False})
                    adjustment.action_cancel()
                else:
                    raise ValidationError(_("Cannot regenerate Salary Adjustment that has already been paid."))
            rec._action_generate()

    def action_view_adjustments(self):
        return {
            'name': _('Salary Adjustments'),
            'view_mode': 'tree,form',
            'res_model': 'ss.hris.salary_adjustment',
            'views': [
                (self.env.ref('ss_hris_compben.ss_hris_salary_adjustment_view_tree').id, 'tree'),
                (self.env.ref('ss_hris_compben.ss_hris_salary_adjustment_view_form').id, 'form')
            ],
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.line_ids.mapped('adjustment_id').ids)],
            'context': dict(self._context, create=False),
        }


class TripAllowanceLine(models.Model):
    _name = 'tf.hr.dh.trip.allowance.line'
    _description = 'Trip Allowance Line'

    ta_id = fields.Many2one('tf.hr.dh.trip.allowance', 'Trip Allowance')
    employee_id = fields.Many2one('hr.employee', 'Employee', required=True)
    job_id = fields.Many2one(related='employee_id.job_id')
    rank_id = fields.Many2one(related='employee_id.rank_id')
    no_of_days = fields.Integer('No. of Days')
    rate = fields.Monetary('Rate')
    amount = fields.Monetary('Allowance Amount')
    adjustment_id = fields.Many2one('ss.hris.salary_adjustment', 'Salary Adjustment')
    adjustment_state = fields.Selection(related='adjustment_id.state', string='Adjustment State', store=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)


class TripAllowanceRate(models.Model):
    _name = 'tf.hr.dh.trip.allowance.rate'
    _description = 'Trip Allowance Rate'

    job_id = fields.Many2one('hr.job', 'Job Position')
    rank_id = fields.Many2one('ss.hris.rank', 'Rank')
    rate = fields.Monetary('Allowance Rate (per Day)')
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
