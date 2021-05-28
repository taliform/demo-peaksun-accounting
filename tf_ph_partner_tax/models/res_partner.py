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
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import re

_TRANSACTION_TYPES = [('0', 'Purchase of Capital Goods'),
                      ('1', 'Purchase of Good Other than Capital Goods'),
                      ('2', 'Purchase of Services'),
                      ('3', 'Purchases Not Qualified for Input Tax'),
                      ('4', 'Others')]


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    sale_tax_ids = fields.Many2many('account.tax', 'sale_tax_rel', 'sale_tax_ids', 'partner_id', string='Sale Taxes',
                                    domain=[('type_tax_use', 'in', ['sale', 'none'])])
    purchase_tax_ids = fields.Many2many('account.tax', 'purchase_tax_rel', 'purchase_tax_ids', 'partner_id',
                                        string='Purchase Taxes', domain=[('type_tax_use', 'in', ['purchase', 'none'])])
    business_id = fields.Many2one('business.type', string='Business Type')
    vat = fields.Char(string='TIN', help="Tax Identification Number. Check the box if this contact is subjected to "
                                         "taxes. Used by the some of the legal statements.", size=17)
    trade_name = fields.Char('Trade Name')
    transaction_type = fields.Selection(_TRANSACTION_TYPES, 'Transaction Type')
    first_name = fields.Char('First Name', size=30)
    last_name = fields.Char('Last Name', size=30)
    middle_name = fields.Char('Middle Name', size=30)
    rdo_code = fields.Char(string='RDO Code', size=5)

    @api.onchange('first_name', 'middle_name', 'last_name')
    def onchange_first_last_name(self):
        if self.first_name and self.last_name:
            fullname = f'{self.first_name} {self.middle_name} {self.last_name}' if self.middle_name else f'{self.first_name} {self.last_name}'
            self.name = fullname

    @api.onchange('rdo_code')
    def onchange_rdo_code(self):
        for rec in self:
            if rec.rdo_code and rec.vat:
                rec.vat = f'{rec.vat[:11]}-{rec.rdo_code}'

    @api.onchange('vat')
    def onchange_vat(self):
        for rec in self:
            tin = rec.vat.replace('-', '')
            if not tin.isdigit():
                rec.vat = re.sub('[^0-9/-]+', '', tin)
            if rec.vat and len(rec.vat) == 17:
                rec.rdo_code = rec.vat[-5:]

    @api.constrains('vat')
    def _check_vat_len(self):
        for rec in self:
            if rec.vat and len(rec.vat) < 9:
                raise ValidationError('TIN cannot be less than 9 digits.')
