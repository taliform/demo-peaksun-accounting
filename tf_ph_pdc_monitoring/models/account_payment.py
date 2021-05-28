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

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError, Warning


class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    state = fields.Selection([('draft', 'Draft'), 
                              ('pdc', 'PDC'),
                              ('posted', 'Posted'), 
                              ('sent', 'Sent'), 
                              ('reconciled', 'Reconciled'),
                              ('cancelled', 'Cancelled')], readonly=True, default='draft', copy=False, string="Status")
    pdc_id = fields.Many2one('account.payment.pdc', 'Post Dated Check')

    def assign_pdc(self):
        for rec in self:
            description = rec.communication
            #Register Payment Wizard
            #Should not return wizard
            if self._context.get('from_inv_wizard', False):
                PDCAssign = self.env['account.payment.pdc.assign']
                invoice_ids = self._context['active_ids']
                if not rec.communication:
                    description = False
                    
                    for invoice_id in invoice_ids:
                        if not description: 
                            description = invoice_id.name
                        else: 
                            description = description + ', ' + invoice_id.name
                            
                context = {'amount': rec.amount,
                           'check_date': rec.payment_date,
                           'description': description,
                           'active_ids': [rec.id],
                           'from_inv_wizard': True,
                           'invoice_ids': invoice_ids,
                            }
                
                PDCAssign.with_context(context).assign_pdc()
            
            else:
                view = self.env.ref('tf_ph_pdc_monitoring.account_payment_pdc_assign_form')
                if rec.payment_method_type == 'adjustment':
                    description = False
                    for line in rec.payment_inv_line_ids.filtered(lambda l: l.allocation > 0.0):
                        if not description: 
                            description = line.invoice_id.name
                        else: 
                            description = description + ', ' + line.invoice_id.name
                
                return {
                        'name': _('Assign PDC'),
                        'type': 'ir.actions.act_window',
                        'res_model': 'account.payment.pdc.assign',
                        'view_mode': 'form',
                        'view_id': view.id,
                        'target': 'new',
                        'context': {'default_payment_id': rec.id,
                                    'default_partner_id': rec.payee_id.id,
                                    'default_check_no': rec.check_no,
                                    'default_amount': rec.amount,
                                    'default_check_date': rec.payment_date,
                                    'default_description': description,
                                    },
                        }

    def post_pdc(self):
        for rec in self:
            view = self.env.ref('tf_ph_pdc_monitoring.account_payment_pdc_confirm_form')
            return {
                    'name': _('Confirm PDC'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.payment.pdc.confirm',
                    'view_mode': 'form',
                    'view_id': view.id,
                    'target': 'new',
                    'context': {'default_payment_id': rec.id,
                                'default_journal_id': rec.journal_id.id,
                                'default_payment_date': rec.payment_date,
                                },
                    }

    def cancel_pdc(self):
        for rec in self:
            #Cancel PDC record
            rec.pdc_id.state = 'cancel'
            # Reset the allocated amount int the PDC Invoice Lines
            for line_id in rec.pdc_id.pdc_invoice_ids:
                line_id.allocated_amt = 0.0
                line_id.invoice_id = False
            rec.state = 'cancelled'

    def post(self):
        res = super(AccountPayment, self).post()
        for rec in self.filtered(lambda payment: payment.pdc_id):
            rec.pdc_id.state = 'paid'

        return res

    def unlink(self):
        for rec in self:
            if rec.state == 'pdc':
                raise Warning(_('You are not allowed to delete payment records that are in PDC status.'))
            return super(AccountPayment, self).unlink()

class AccountPaymentInvoiceLine(models.Model):
    _inherit = 'account.payment.invoice.line'

    is_pdc = fields.Boolean(string='PDC', compute="_compute_is_pdc")

    def _compute_is_pdc(self):
        for rec in self:
            rec.is_pdc = False
            if rec.payment_id.state == 'pdc':
                rec.is_pdc = True


