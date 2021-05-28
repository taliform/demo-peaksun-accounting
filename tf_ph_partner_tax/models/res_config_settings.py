# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    vat_tax_ids = fields.Many2many(related='company_id.vat_tax_ids', readonly=False, string='VAT Tax')
    vat_exempt_tax_ids = fields.Many2many(related='company_id.vat_exempt_tax_ids', readonly=False, string='VAT-Exempt Tax')
    zero_rated_tax_ids = fields.Many2many(related='company_id.zero_rated_tax_ids', readonly=False, string='Zero Rated Tax')
    withholding_2306_ids = fields.Many2many(related='company_id.withholding_2306_ids', readonly=False, string='2306')   
    withholding_2307_ids = fields.Many2many(related='company_id.withholding_2307_ids', readonly=False, string='2307')