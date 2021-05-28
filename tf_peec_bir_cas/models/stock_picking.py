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


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    delivery_receipt = fields.Binary(string='Delivery Receipt')
    hash_code = fields.Char('Hash Code (MD5)')
    business_style = fields.Char(string='Business Style', help="Indicates the company's business style", required=True,
                                 default=lambda self: self.env.company.business_style)
    permit_to_use_no = fields.Char(string="Permit to use No.",
                                   help="Indicates the permit to use CAS number provided by BIR.",
                                   default=lambda self: self.env.company.permit_to_use_no)
    date_issued = fields.Date(string="Date Issued", help="Indicates the date the permit is issued for the CAS.",
                              default=lambda self: self.env.company.date_issued)
    date_valid = fields.Date(string="Valid Until", help="Indicates the expiration date of the CAS permit.",
                             default=lambda self: self.env.company.date_valid)
    range_series_dr = fields.Char(string="Range of Series - Delivery Receipt",
                                  help="Indicates the permit's range of series.",
                                  default=lambda self: self.env.company.range_series_dr)
    range_series_bs = fields.Char(string="Range of Series - Billing Statement",
                                  help="Indicates the permit's range of series.",
                                  default=lambda self: self.env.company.range_series_bs)
    range_series_si = fields.Char(string="Range of Series - Sales Invoice",
                                  help="Indicates the permit's range of series.",
                                  default=lambda self: self.env.company.range_series_si)
    footnote = fields.Text(string="Footnote", help="Indicates the footnote for the official document printout.",
                           default=lambda self: self.env.company.footnote)
