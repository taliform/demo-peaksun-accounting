# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Joshua <joshua@taliform.com>
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
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    business_style = fields.Char(string='Business Style', help="Indicates the company's business style", required=True)
    _sql_constraints = [
        ('business_style_uniq', 'unique (business_style)', 'Business Style must be unique'),
    ]
    permit_to_use_no = fields.Char(string="Permit to use No.", help="Indicates the permit to use CAS number provided by BIR.")
    date_issued = fields.Date(string="Date Issued", help="Indicates the date the permit is issued for the CAS.")
    date_valid = fields.Date(string="Valid Until", help="Indicates the expiration date of the CAS permit.")
    range_series = fields.Char(string="Range of Series", help="Indicates the permit's range of series.")
    footnote = fields.Char(string="Footnote", help="Indicates the footnote for the official document printout.")




