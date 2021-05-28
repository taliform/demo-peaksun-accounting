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
from lxml import etree
from dateutil.rrule import *
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.base.models.ir_ui_view import transfer_field_to_modifiers, transfer_modifiers_to_node, \
    transfer_node_to_modifiers


# class HrEmployeeBadge(models.Model):
#     _name = "hr.employee.badge"
#     _description = "Earned badges of employees"
#     _order = 'create_date desc, id desc'
#
#     STATES = [
#         ('draft', "Draft"),
#         ('confirm', "Confirmed"),
#         ('approval', "For Approval"),
#         ('approve', "Approved"),
#         ('cancel', "Cancelled"),
#         ('reject', "For Revision"),
#     ]
#
#     badge_id = fields.Many2one('tf.dh.eval.badge', "Badge")
#     employee_id = fields.Many2one('hr.employee', "Employee")
#     eval_id = fields.Many2one('tf.dh.eval.line', "Source Evaluation")
#     date_granted = fields.Date('Date Granted')


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # dh_badge_ids = fields.One2many('hr.employee.badge', 'employee_id', "Badges Received")
    badge_count = fields.Integer(compute="_compute_badge_count", string="Badges Received")
    evaluation_count = fields.Integer(compute="_compute_evaluation_count", string="Employee Evaluations")

    def _compute_badge_count(self):
        for rec in self:
            rec.badge_count = len(rec.badge_ids)

    def _compute_evaluation_count(self):
        for rec in self:
            evals = self.env['tf.dh.eval.line'].search([
                ('employee_id', '=', rec.id)
            ])
            if evals:
                rec.evaluation_count = len(evals.mapped('eval_id'))
            else:
                rec.evaluation_count = len(evals)

    # def action_open_badges(self):
    #     return {
    #         'name': 'Employee Badges',
    #         'view_mode': 'tree',
    #         'res_model': 'hr.employee.badge',
    #         'view_id': self.env.ref('tf_peec_dh_eval.peec_hr_employee_badges_view_tree').id,
    #         'domain': [('employee_id', '=', self.id)],
    #         'type': 'ir.actions.act_window',
    #         'target': 'current'
    #     }

    def action_open_evaluations(self):
        eval_lines = self.env['tf.dh.eval.line'].search([
            ('employee_id', '=', self.id)
        ])
        evals = eval_lines.mapped('eval_id')

        tree_view_id = self.env.ref('tf_peec_dh_eval.tf_dh_eval_view_tree').id
        form_view_id = self.env.ref('tf_peec_dh_eval.tf_dh_eval_view_form').id

        return {
            'name': 'Driver/Helper Evaluations',
            'view_mode': 'tree,form',
            'res_model': 'tf.dh.eval',
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'domain': [('id', 'in', evals.ids)],
            'type': 'ir.actions.act_window',
            'target': 'current'
        }
