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

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AccountPaymentAssignPDC(models.TransientModel):
    _name = 'account.payment.pdc.assign'
    _description = 'Payment Assign PDC'

    amount = fields.Float('Amount')
    check_date = fields.Date()
    description = fields.Char()
    check_no = fields.Char(string='Check No.')
    partner_id = fields.Many2one('res.partner', string='Partner')
    def assign_pdc(self):
        AccountPayment = self.env['account.payment']
        AccountInvoice = self.env['account.move']
        active_ids = self._context['active_ids']

        for active_id in active_ids:
            payment_id = AccountPayment.browse(active_id)
            pdc_lines = []
            partner_type = False
            check_date = self.check_date
            description = self.description

            #Register Payment Wizard
            if self._context.get('from_inv_wizard', False):

                check_date = self._context['check_date']
                description = self._context['description']
                invoice_ids = self._context['invoice_ids']
                
                pdc_id = self.create_pdc(payment_id, check_date, description)
                
                for invoice_id in invoice_ids:
                    invoice_id = AccountInvoice.browse(invoice_id)
                    if invoice_id.pdc_line_ids.filtered(lambda x: x.pdc_state != 'cancel'):
                        raise ValidationError('This record already has an existing PDC!')
                    vals = {'pdc_id': pdc_id.id,
                            'invoice_id': invoice_id.id,
                            'currency_id': invoice_id.currency_id.id,
                            'allocated_amt': pdc_id.amount}
                    pdc_lines.append(((0,0,vals)))
                pdc_id.pdc_invoice_ids = pdc_lines
            
            #Payment Adjustment (Payment Form)
            elif payment_id.payment_method_type == 'adjustment':
                if not payment_id.payment_inv_line_ids and not payment_id.payment_crdr_inv_line_ids:
                    raise ValidationError(('The payment should have payment allocations.'))
                pdc_id = self.create_pdc(payment_id, check_date, description)
                # Get the allocated amount
                if payment_id.payment_inv_line_ids:
                    for line_id in payment_id.payment_inv_line_ids.filtered(lambda l: l.allocation > 0.0):
                        vals = {'pdc_id': pdc_id.id,
                                'invoice_id': line_id.invoice_id.id,
                                'currency_id': line_id.invoice_id.currency_id.id,
                                'allocated_amt': line_id.allocation}
                        pdc_lines.append(((0,0,vals)))
                if payment_id.payment_crdr_inv_line_ids:
                    for line_id in payment_id.payment_crdr_inv_line_ids.filtered(lambda l: l.allocation > 0.0):
                        vals = {'pdc_id': pdc_id.id,
                                'invoice_id': line_id.invoice_id.id,
                                'currency_id': line_id.invoice_id.currency_id.id,
                                'allocated_amt': line_id.allocation * -1}
                        pdc_lines.append(((0,0,vals)))
                pdc_id.pdc_invoice_ids = pdc_lines
            #Advance Payment (Payment Form)
            else:
                pdc_id = self.create_pdc(payment_id, check_date, description)

            # Update PDC
            sequence_obj = self.env['ir.sequence']
            if payment_id.partner_type == 'customer':
                partner_type = 'customer'
            elif payment_id.partner_type == 'supplier':
                partner_type = 'supplier'
            pdc_id.update({'name': sequence_obj.next_by_code('account.payment.pdc'),
                           'partner_type': partner_type})
            payment_id.pdc_id = pdc_id.id
            payment_id.state = 'pdc'

    def create_pdc(self, payment_id, check_date, description):
        AccountPaymentPDC = self.env['account.payment.pdc']
        pdc_vals = {'payment_id': payment_id.id,
                    'partner_id': payment_id.partner_id.id,
                    'journal_id': payment_id.journal_id.id,
                    'amount': payment_id.amount,
                    'check_no': payment_id.check_no,
                    'check_date': check_date,
                    'description': description,
                    'state': 'confirmed'
                    }
        
        return AccountPaymentPDC.create(pdc_vals)


class AccountPaymentConfirmPDC(models.TransientModel):
    _name = 'account.payment.pdc.confirm'
    _description = 'Payment Confirm PDC'

    payment_date = fields.Date('Payment Date')
    journal_id = fields.Many2one('account.journal', 'Payment Journal')

    def confirm_pdc(self):
        AccountPayment = self.env['account.payment']
        active_ids = self._context['active_ids']

        for active_id in active_ids:
            payment_id = AccountPayment.browse(active_id)
            payment_id.payment_date = self.payment_date
            payment_id.journal_id = self.journal_id

            if payment_id.pdc_id:
                pdc_id = payment_id.pdc_id
                pdc_id.check_date = self.payment_date
                pdc_id.journal_id = self.journal_id

            payment_id.post()
