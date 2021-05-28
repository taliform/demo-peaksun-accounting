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
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    cement_sales = fields.Boolean(string='Cement Sales', default=False)
    topsheet_id = fields.Many2one('account.topsheet', 'Topsheet')

    def action_generate_topsheet(self):
        if any(move.type != 'out_invoice' for move in self):
            raise ValidationError(_("This action isn't available for this document."))
        self._generate_topsheet_validation()
        AccountTopsheet = self.env['account.topsheet']
        sequence_obj = self.env['ir.sequence']
        topsheet_vals = {
            'name': sequence_obj.next_by_code('account.topsheet'),
            'state': 'draft',
            'customer_id': self[0].partner_id.id,
            'invoice_ids':  self.ids
        }
        topsheet_id = AccountTopsheet.create(topsheet_vals)
        for rec in self:
            rec.write({
                'topsheet_id': topsheet_id
            })

    def _generate_topsheet_validation(self):
        multiple_partners = self.mapped('partner_id')
        error_string = ''
        if len(multiple_partners) > 1:
            error_string += 'The selected records should have the same partner.\n'
        valid_ref = self.filtered(lambda rec: rec.invoice_origin != False).mapped('invoice_origin')
        if len(valid_ref) > 1:
            error_string += 'The selected records should have the same reference.\n'
        topsheet_valid_invoices = self.search([
            ('cement_sales', '=', True),
            ('topsheet_id', '=', False),
            ('invoice_payment_state', '!=', 'paid'),
            ('type', 'not in', ('in_invoice', 'in_refund', 'in_receipt'))
        ])
        for rec in self:
            if rec.id not in topsheet_valid_invoices.ids:
                error_string += f'{rec.name} not valid for topsheet generation. \n'
        if not topsheet_valid_invoices:
            error_string += 'The selected records should have unpaid cement sales without an existing topsheet reference.'

        if error_string:
            raise ValidationError(error_string)


