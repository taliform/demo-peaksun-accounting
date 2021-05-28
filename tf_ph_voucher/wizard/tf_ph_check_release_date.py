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
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CheckPaymentDate(models.TransientModel):
    _name = 'check.payment.date'
    _description = 'Check Payment Date Wizard'
    
    payment_date = fields.Date('Payment Release Date')

    def apply(self):
        '''
        @summary: Applies the Check Payment Date value to the current Supplier Payment record.
        '''
        aadata = self
        AccountPayment = self.env['account.payment']
        # Get Supplier Payment record via context.
        payment_id = self._context.get('payment_id')
        payment = AccountPayment.browse(payment_id)
        # Update Supplier Payment record.
        payment.write({'check_release_date': self.payment_date, 'check_released': True})
        if "cash_advance_id" in payment.invoice_ids and payment.invoice_ids.cash_advance_id:
            payment.invoice_ids.cash_advance_id.state = 'open'