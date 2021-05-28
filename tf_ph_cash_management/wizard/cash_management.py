# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2019 Synersys Consulting Inc.
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
from odoo.exceptions import ValidationError
from odoo import models, fields, api, _


class CashManagementWizard(models.TransientModel):
    _name = 'cash.management.wizard'
    _description = 'Cash Management Wizard'
   
    journal_id = fields.Many2one('account.journal', string='Journal', domain=[('type', 'in', ['bank', 'cash'])])
    cash_management_id = fields.Many2one('cash.management', string='Cash Management')

    def close_cash_management(self):
        CashManagement = self.env['cash.management']
        AccountInvoice = self.env['account.move']
        AccountInvoiceLine = self.env['account.move.line']
        today = fields.Date.today()
        
        if self._context.get('default_cash_management_id', False):
            cm_id = CashManagement.browse(self._context['default_cash_management_id'])
            
            if cm_id.unliquidated_amount != 0 or cm_id.total_for_reimbursement != 0:
                raise ValidationError(_('Unliquidated Amount and Reimbursement Amount should be equal to zero.'))
            
            if cm_id.replenishment_ids:
                for repl_id in cm_id.replenishment_ids:
                    if repl_id.state not in ['validate', 'receive', 'done']:
                        raise ValidationError(_('Replenishments should be either Validated, Received or in Done state.'))
                
            if (cm_id.remaining_fund + cm_id.total_validated_replenishment) != cm_id.current_fund:
                raise ValidationError(_('Remaining Fund plus Total Validated Replenishments should be equal to the Cash Fund.'))
        
            if cm_id.remaining_fund != cm_id.current_fund:
                raise ValidationError(_('Cash Balance should be equal to the Cash Fund.'))
                
        for rec in self:
            if rec.cash_management_id:
                if not rec.journal_id.default_debit_account_id:
                    raise ValidationError(_('The selected Journal does not have a default debit account'))
                
                cm_id = rec.cash_management_id
                analytic_account_id = False
                company_id = self.env.user.company_id
                if not company_id:
                    raise ValidationError(_('There is no default company for the current user!'))
                
                if cm_id.analytic_account_id: 
                    analytic_account_id = cm_id.analytic_account_id.id

                inv_line_vals = {
                                 'account_id': cm_id.account_id.id,
                                 'journal_id': rec.journal_id.id,
                                 'analytic_account_id': analytic_account_id,
                                 'name': 'Closing of ' + cm_id.name,
                                 'price_unit': cm_id.remaining_fund,
                                 'quantity': 1
                }
                #Customer Invoice
                inv_vals = {
#                             'account_id': ct_id.partner_id.property_account_payable_id.id,
                            'currency_id': cm_id.currency_id.id,
                            'journal_id': rec.journal_id.id,
                            'cash_management_id': cm_id.id,
                            'ref': cm_id.name,
                            'partner_id': cm_id.create_uid.partner_id.id,
                            'invoice_line_ids': [(0, 0, inv_line_vals)],
                            'invoice_date': today.strftime('%Y-%m-%d'),
                            'for_closing': True,
                            'type': 'out_invoice'}
                invoice_id = AccountInvoice.create(inv_vals)
                invoice_id.action_post()
                cm_id.write({
                    'closing_invoice_id': invoice_id.id,
                    'remaining_fund': 0,
                    'state': 'close'
                })


class ReplenishFund(models.TransientModel):
    _name = 'replenish.fund'
    _description = 'Replenish Fund'

    def generate_replenishment(self):
        CashReplenishment = self.env['cash.replenishment']
        CashTransaction = self.env['cash.transaction']

        ct_ids = self._context.get('active_ids', False)
        if ct_ids:
            repl_id = False
            cm_ids = []
            for ct_id in ct_ids:
                ct_id = CashTransaction.browse(ct_id)
                if ct_id.state != 'open':
                    raise ValidationError(_('One of the selected transaction is already replenished.'))
                else:
                    cm_id = ct_id.cash_management_id
                    if cm_ids and cm_id not in cm_ids:
                        raise ValidationError(_('The selected transactions should have the same CM reference.'))
                    else:
                        if not repl_id:
                            journal_id = CashReplenishment._get_journal_entry_config_account()
                            repl_id = CashReplenishment.create({'cash_management_id':cm_id.id,
                                                                'journal_id':journal_id})
                        cm_ids.append(cm_id)
                        ct_id.write({'state': 'replenish',
                                     'cash_replenishment_id': repl_id.id})
        return {'type': 'ir.actions.act_window_close'}


class CashRequestReject(models.TransientModel):
    _name = 'cash.request.reject'
    _description = 'Cancel CR'

    notes = fields.Text('Reason')

    def reject_cr(self):
        CashRequest = self.env['cash.request']
        active_ids = self._context['active_ids']

        for active_id in active_ids:
            cr_id = CashRequest.browse(active_id)
            # CA Rejected
            if cr_id.state in ['draft', 'for_approval']:
                cr_id.cr_reject_reason = self.notes
                cr_id.change_state('rejected')
                cr_id.change_state('cancel')


class TfCmUpdateCustodian(models.TransientModel):
    _name = 'tf.cm.update.custodian'
    _description = 'Cash Management Update Custodian Wizard'

    cm_id = fields.Many2one('cash.management', "Cash Management")
    custodian_id = fields.Many2one('res.users', string="New Custodian", domain=lambda self: [
        ('groups_id', 'in', self.env.ref('tf_ph_cash_management.group_cash_management_manager').id)],
                                   help="Update the CM custodian with the following user", required="1")

    def action_confirm(self):
        self._cr.execute("""UPDATE cash_management SET create_uid = %s WHERE id = %s""", (self.custodian_id.id, self.cm_id.id,))
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
