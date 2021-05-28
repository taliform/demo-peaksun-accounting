# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################
from odoo import models, fields
from odoo.tools.translate import _


class TfVendorServiceVatGenerate(models.TransientModel):
    _name = 'tf.vendor.service.vat.generate'
    _description = 'Generate Service Vat'

    payment_id = fields.Many2one('account.payment', "Payment")
    or_no = fields.Char("O.R. Number")
    or_date = fields.Date("O.R. Date")

    def action_confirm(self):
        payment_id = self.payment_id
        wh_aml_ids = payment_id.move_line_ids.filtered_domain([('type', '=', 'entry'), ('payment_id', '=', False)])
        payment_aml_ids = payment_id.move_line_ids
        other_amounts = sum(wh_aml_ids.mapped('balance'))
        payment_id.create_reclass_entry(payment_id.reconciled_invoice_ids, other_amounts)
        if payment_id.vat_move_ids:
            payment_id.vendor_valid_for_reclass = False
            payment_id.write({
                'or_no': self.or_no,
                'or_date': self.or_date
            })
