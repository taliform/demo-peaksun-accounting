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


class ResCompany(models.Model):
    _inherit = 'res.company'
    rdo_code = fields.Char('RDO Code', size=5, track_visibility='onchange')
    vat_registered = fields.Boolean('Vat Registered')
    vat = fields.Char(related='partner_id.vat', string='Tax ID', size=17)
    authorized_rep_id = fields.Many2one('res.partner', 'Authorized Representative')
    vat_tax_ids = fields.Many2many('account.tax', 'vat_tax_rel', 'partner_id', 'tax_id', string='VAT Tax')
    vat_exempt_tax_ids = fields.Many2many('account.tax', 'exempt_tax_rel', 'partner_id', 'tax_id', string='VAT-Exempt Tax')
    zero_rated_tax_ids = fields.Many2many('account.tax', 'zero_tax_rel', 'partner_id', 'tax_id', string='Zero Rated Tax')
    withholding_2306_ids = fields.Many2many('account.tax', 'tax_2306_ids_rel', 'partner_id', 'tax_code_id', string='2306')   
    withholding_2307_ids = fields.Many2many('account.tax', 'tax_2307_ids_rel', 'partner_id', 'tax_code_id', string='2307')
