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
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DhEvalConfig(models.Model):
    _name = "tf.dh.eval.config"
    _description = "Evaluation Config for Driver/Helper"
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    _sql_constraints = [('name_unique', 'unique(name)', 'Evaluation configuration name already exists.')]

    name = fields.Char("Name", required=True, copy=False, track_visibility='onchange',
                       help="Indicates the appraisal configuration identifier.")
    active = fields.Boolean(default=True, track_visibility='onchange',
                            help="By unchecking the active field, you may hide this evaluation "
                                 "matrix without deleting it.")
    percent_prod = fields.Float("Productivity", track_visibility='onchange',
                                help="Indicate the the percentage share of productivity in the overall performance "
                                     "evaluation.")
    percent_corp = fields.Float("Corporate", track_visibility='onchange',
                                help="Indicate the the percentage share of corporate activities in the overall "
                                     "performance evaluation.")
    percent_skills = fields.Float("Skills", track_visibility='onchange',
                                  help="Indicate the the percentage share of productivity in the overall performance "
                                       "evaluation.")
    total_rating = fields.Float("Total", readonly="1", store=True, copy=False, compute="_compute_total_rating",
                                help="Indicates the total percentage score of productivity, corporate and skills.")
    productivity_ids = fields.One2many('tf.dh.eval.prod.config', 'config_id', "Productivity Matrix",
                                       track_visibility='onchange',
                                       help="Indicates the productivity evaluation based on the range of average "
                                            "number of trips per month and its corresponding score.")
    accident_ids = fields.One2many('tf.dh.eval.corpo.config', 'accident_id', "Accidents Matrix",
                                   track_visibility='onchange',)
    speeding_ids = fields.One2many('tf.dh.eval.corpo.config', 'speeding_id', "Over-speeding Matrix",
                                   track_visibility='onchange',)
    infraction_ids = fields.One2many('tf.dh.eval.corpo.config', 'infraction_id', "Other Infractions Matrix",
                                     track_visibility='onchange')
    grade_ids = fields.One2many('tf.dh.eval.grade.config', 'config_id', "Appraisal Grade",
                                track_visibility='onchange',)
    max_prod = fields.Integer(compute="get_prod_seq", store=True, copy=False)
    max_accident = fields.Integer(compute="get_accident_seq", store=True, copy=False)
    max_speeding = fields.Integer(compute="get_speeding_seq", store=True, copy=False)
    max_infraction = fields.Integer(compute="get_infraction_seq", store=True, copy=False)
    max_rating = fields.Float(compute="get_rating_seq", store=True, copy=False)
    accident_infra_id = fields.Many2one('ss.hris.infraction.type', "Infraction Type", required=True,
                                        track_visibility='onchange',
                                        help="Select the applicable infraction type record that are related to "
                                             "accidents")
    speeding_infra_id = fields.Many2one('ss.hris.infraction.type', "Infraction Type", required=True,
                                        track_visibility='onchange',
                                        help="Select the applicable infraction type record that is related to "
                                             "overspeeding.")
    other_infra_id = fields.Many2one('ss.hris.infraction.type', "Infraction Type", required=True,
                                     track_visibility='onchange',
                                     help="Select the applicable infraction type record that is related to other "
                                          "infractions.")
    accident_action_id = fields.Many2one('ss.hris.infraction.action', "Disciplinary Action", required=True,
                                         track_visibility='onchange',
                                         help="Select the applicable disciplinary action that is related to suspension."
                                              " Evaluation of overspeeding is based on the days that the employee was"
                                              " suspended.")
    speeding_action_id = fields.Many2one('ss.hris.infraction.action', "Disciplinary Action", required=True,
                                         track_visibility='onchange',
                                         help="Select the applicable disciplinary action that is related to suspension"
                                              ". Evaluation of overspeeding is based on the days that the employee was "
                                              "suspended.")
    other_action_id = fields.Many2one('ss.hris.infraction.action', "Disciplinary Action", required=True,
                                      track_visibility='onchange',
                                      help="Select the applicable disciplinary action that is related to suspension. "
                                           "Evaluation of other infractions is based on the days that the employee "
                                           "was suspended.")
    leave_type_ids = fields.Many2many('ss.hris.leave.type', 'dh_eval_leave_config_rel', 'config_id', 'leave_id',
                                      track_visibility='onchange',
                                      string='Leave Type(s)', require=True)
    leave_multiplier = fields.Float("Multiplier (Per Leave Day)",
                                    track_visibility='onchange',
                                    help="Indicate the multiplier per leave day for scoring of the point deduction for "
                                         "the leaves.")

    @api.constrains('percent_prod', 'percent_corp', 'percent_skills')
    def _check_scores(self):
        for rec in self:
            if rec.percent_prod < 0 \
                    or rec.percent_corp < 0 \
                    or rec.percent_skills < 0:
                raise ValidationError(_("Multipliers cannot be negative."))

    @api.depends('productivity_ids')
    def get_prod_seq(self):
        for rec in self:
            max_n = 0
            if rec.productivity_ids:
                max_n = max(rec.productivity_ids.mapped("to_range"))
            rec.max_prod = max_n + 1

    @api.depends('accident_ids')
    def get_accident_seq(self):
        for rec in self:
            max_n = 0
            if rec.accident_ids:
                max_n = max(rec.accident_ids.mapped("to_range"))
            rec.max_accident = max_n + 1

    @api.depends('speeding_ids')
    def get_speeding_seq(self):
        for rec in self:
            max_n = 0
            if rec.speeding_ids:
                max_n = max(rec.speeding_ids.mapped("to_range"))
            rec.max_speeding = max_n + 1

    @api.depends('infraction_ids')
    def get_infraction_seq(self):
        for rec in self:
            max_n = 0
            if rec.infraction_ids:
                max_n = max(rec.infraction_ids.mapped("to_range"))
            rec.max_infraction = max_n + 1

    @api.depends('grade_ids')
    def get_rating_seq(self):
        for rec in self:
            max_n = 0
            if rec.grade_ids:
                max_n = max(rec.grade_ids.mapped("to_range"))
            rec.max_rating = max_n + 0.01

    @api.depends('percent_prod', 'percent_corp', 'percent_skills')
    def _compute_total_rating(self):
        for rec in self:
            rec.total_rating = rec.percent_prod + rec.percent_skills + rec.percent_corp

    def get_prod_score(self, n_trips):
        line_id = self.productivity_ids.filtered(lambda p: p.from_range <= n_trips <= p.to_range)
        if line_id:
            return line_id[0].score
        else:
            return 0

    def get_accident_score(self, n_accidents):
        line_id = self.accident_ids.filtered(lambda a: a.from_range <= n_accidents <= a.to_range)
        if line_id:
            return line_id[0].score
        else:
            return 0

    def get_speeding_score(self, n_speeding):
        line_id = self.speeding_ids.filtered(lambda a: a.from_range <= n_speeding <= a.to_range)
        if line_id:
            return line_id[0].score
        else:
            return 0

    def get_others_score(self, n_others):
        line_id = self.infraction_ids.filtered(lambda a: a.from_range <= n_others <= a.to_range)
        if line_id:
            return line_id[0].score
        else:
            return 0

    def get_leaves_score(self, n_leaves):
        return n_leaves * self.leave_multiplier

    def get_summary_score(self, prod_score, corpo_score, skills_score):
        prod_score = prod_score * self.percent_prod
        corpo_score = corpo_score * self.percent_corp
        skills_score = skills_score * self.percent_skills
        total_score = prod_score + corpo_score + skills_score
        rating = "Not Defined"
        badge_ids = []
        line_id = self.grade_ids.filtered(lambda g: g.from_range <= total_score <= g.to_range)
        if line_id:
            rating = line_id[0].rating
            badge_ids = line_id[0].badge_ids

        return total_score, rating, badge_ids

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {}, name=_("%s (Copy)") % self.name)
        return super(DhEvalConfig, self).copy(default=default)


class DhEvalProdConfig(models.Model):
    _name = "tf.dh.eval.prod.config"
    _description = "Productivity Evaluation Config for Driver/Helper"

    config_id = fields.Many2one('tf.dh.eval.config', "Configuration", ondelete='cascade')
    from_range = fields.Integer("From", required=True)
    to_range = fields.Integer("To", required=True)
    score = fields.Float("Score", required=True)

    @api.constrains('from_range', 'to_range')
    def _check_range(self):
        for rec in self:
            from_range = rec.from_range
            to_range = rec.to_range

            if from_range < 0 or to_range < 0:
                raise ValidationError(_('Productivity From and To cannot be negative.'))

            if from_range >= to_range:
                raise ValidationError(
                    "Productivity Matrix: To range value (%s) should be greater than the From value (%s)" %
                    (to_range, from_range))


class DhEvalCorpoConfig(models.Model):
    _name = "tf.dh.eval.corpo.config"
    _description = "Corporate activities evaluation configuration for Driver/Helper"

    accident_id = fields.Many2one('tf.dh.eval.config', "Configuration", ondelete='cascade')
    speeding_id = fields.Many2one('tf.dh.eval.config', "Configuration", ondelete='cascade')
    infraction_id = fields.Many2one('tf.dh.eval.config', "Configuration", ondelete='cascade')
    from_range = fields.Integer("From", required=True)
    to_range = fields.Integer("To", required=True)
    score = fields.Float("Score (Deduction)", required=True)

    @api.constrains('from_range', 'to_range')
    def _check_range(self):
        for rec in self:
            from_range = rec.from_range
            to_range = rec.to_range

            if from_range < 0 or to_range < 0:
                raise ValidationError(_('Corporate From and To cannot be negative.'))

            if from_range >= to_range:
                range_name = ""
                if rec.accident_id:
                    range_name = "Accident Matrix"
                elif rec.speeding_id:
                    range_name = "Over-speeding Matrix"
                elif rec.infraction_id:
                    range_name = "Other Infractions Matrix"

                raise ValidationError(
                    "%s: To range value (%s) should be greater than the From value (%s)" %
                    (range_name, to_range, from_range))


# class DhEvalBadge(models.Model):
#     _name = "tf.dh.eval.badge"
#     _description = "Driver/Helper Badges for Gamification"
#
#     _sql_constraints = [('name_unique', 'unique(name)', 'Badge name already exists.')]
#
#     name = fields.Char("Badge Name", required=True, copy=False)


class DhEvalGradeConfig(models.Model):
    _name = "tf.dh.eval.grade.config"
    _description = "Appraisal grade configuration for Driver/Helper"

    config_id = fields.Many2one('tf.dh.eval.config', "Configuration", ondelete='cascade')
    from_range = fields.Float("From", required=True)
    to_range = fields.Float("To", required=True)
    rating = fields.Char("Rating", required=True)
    badge_ids = fields.Many2many('gamification.badge', string='Badges')

    @api.constrains('from_range', 'to_range')
    def _check_range(self):
        for rec in self:
            from_range = rec.from_range
            to_range = rec.to_range

            if from_range < 0 or to_range < 0:
                raise ValidationError(_('Appraisal Grading From and To cannot be negative.'))

            if from_range >= to_range:
                raise ValidationError(
                    "Appraisal Grading Matrix: To range value (%s) should be greater than the From value (%s)" %
                    (to_range, from_range))
