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


class TfHrRiceSubsidyConfig(models.Model):
    _name = "tf.hr.rice.subsidy.config"
    _inherit = ['mail.thread']
    _description = "Rice Subsidy Configuration"

    name = fields.Char("Name", required=True, copy=False, help="Indicates the name for the rice subsidy configuration.")
    is_dh = fields.Boolean("Driver/Helper", default=True,
                           help=" Indicate that only employees tagged as driver and helper in "
                                "their Employee 201 will be considered.")
    tenure_count = fields.Float("Min. Tenure Year", required=True,
                                help="Indicates the minimum number of tenure years to be qualified for "
                                     "rice subsidy.")
    attendance_count = fields.Integer("Attendance Count", required=True,
                                      help="Indicates the minimum number of attendance present per month to be "
                                           "qualified for rice subsidy.")
    meeting_count = fields.Integer("Meeting Count", required=True,
                                   help="Indicates the minimum number of meetings to be present per month to be "
                                        "qualified for rice subsidy.")
    infraction_count = fields.Integer("Infraction Count", required=True,
                                      help="Indicates the maximum number of infractions that the employee will "
                                           "commit in the month to be qualified for rice subsidy.")
    trips_count = fields.Integer("Trips Count", required=True,
                                 help="Indicates the number of trips that the employee will commit in the month to be "
                                      "qualified for rice subsidy.")

    @api.constrains('name')
    def _check_name_unique(self):
        """
        @noted: This function checks for lowercase and uppercase alpha characters.
        """
        if self.name:
            name = self.name.lower()
            existing_name = self.search([('name', '!=', False)]).filtered(lambda x: x.name.lower() == name)
            if len(existing_name) > 1:
                raise ValidationError((_("Rice Subsidy Configuration - %s already exists.")) % existing_name[0].name)

    @api.constrains('tenure_count', 'trips_count', 'infraction_count', 'attendance_count', 'meeting_count')
    def _check_counts(self):
        for rec in self:
            if rec.tenure_count < 0 or rec.trips_count < 0 or rec.infraction_id < 0 or rec.attendance_count < 0 or rec.meeting_count < 0:
                raise ValidationError(_('Tenure / No. of Trips / Infractions / '
                                        'Attendance / Meetings must not be negative.'))
