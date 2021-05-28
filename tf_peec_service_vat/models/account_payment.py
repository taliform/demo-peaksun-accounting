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
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    official_receipt_no = fields.Char('Official Receipt No', copy=False, readonly=False,
                                      states={'reconciled': [('readonly', True)], 'cancelled': [('readonly', True)]},
                                      help="Indicate the payment receipt reference.")
    official_receipt_date = fields.Date('Official Receipt Date', default=fields.Date.context_today, copy=False,
                                        states={'reconciled': [('readonly', True)], 'cancelled': [('readonly', True)]},
                                        help="Indicate the date of the payment receipt reference. ")
    service_vat = fields.Many2one('account.move', string='Service VAT', help="Automatically indicate a link to journal entry for the service VAT reclassification entry. ")
    generate_vat = fields.Boolean(default=False)

    def action_update(self):
        for rec in self:
            rec._or_validation()
            rec.payment_inv_line_ids.invoice_id.invoice_line_ids.write({
                'ref': f'{rec.official_receipt_no}/{rec.official_receipt_date}'
            })

    def action_generate_vat(self):
        wh_aml_ids = self.payment_inv_line_ids.invoice_id.invoice_line_ids.filtered(lambda x: x.type == 'entry' and not x.payment_id)
        other_amounts = sum(wh_aml_ids.mapped('balance'))
        for rec in self:
            rec._or_validation()
            rec.generate_vat = True
            self.create_reclass_entry(rec.invoice_ids, other_amounts)

    def write(self, vals):
        res = super(AccountPayment, self).write(vals)
        return res

    def _or_validation(self):
        for rec in self:
            if not rec.official_receipt_no or not rec.official_receipt_date:
                raise ValidationError('Official Receipt No. and Date should not be empty')

    def post(self):

        for rec in self:
            if rec.state == 'draft':
                for invoice in rec.payment_inv_line_ids:
                    service_invoice = invoice.invoice_id.invoice_line_ids.mapped('tax_ids').filtered(lambda t: t.is_service)
                    if service_invoice:
                        rec.service_vat = invoice.invoice_id
        return super(AccountPayment, self).post()

    def create_reclass_entry(self, invoice_ids, other_amounts):
        for rec in self:
            if rec.service_vat and not rec.generate_vat:
                print('bill has service vat')
            else:
                rec.generate_vat = False
                return super(AccountPayment, self).create_reclass_entry(invoice_ids, other_amounts)