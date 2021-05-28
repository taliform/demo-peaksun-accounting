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


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    trial_approved = fields.Boolean(string="Posting with Trial Balanced Approved", default=False, copy=False,
                                    track_visibility='onchange')
    cancel_date = fields.Date(string='Reversal date')
    cancel_trial_requested = fields.Boolean(string="Payment Cancellation with Trial Balance Requested", default=False,
                                            copy=False, track_visibility='onchange')
    cancel_reason = fields.Char("Cancel Reason", copy=False)
    with_trial_balance = fields.Boolean('With Trial Balance', copy=False, compute="get_has_trial_bal", store=True)
    is_billing_user = fields.Boolean(compute='_get_is_billing_user', store=True)
    is_wizard = fields.Boolean(compute='_get_is_wizard')

    @api.depends('payment_date')
    def _get_is_wizard(self):
        for rec in self:
            if self.env.context.get('is_wizard', False):
                rec.is_wizard = True
            else:
                rec.is_wizard = False

    @api.depends('state')
    def _get_is_billing_user(self):
        for rec in self:
            user_id = self.env.user
            is_billing = user_id.has_group('account.group_account_invoice')
            is_advisor = user_id.has_group('account.group_account_manager')
            is_accountant = user_id.has_group('account.group_account_user')
            if user_id.has_group('account.group_account_invoice') and not (is_advisor or is_accountant):
                rec.is_billing_user = True
            else:
                rec.is_billing_user = False

    @api.depends('payment_date')
    def get_has_trial_bal(self):
        date_today = fields.Date.today()
        tb_obj = self.env['tf.ph.trial.balance']
        for rec in self:
            if rec.payment_date != (rec.create_date or date_today):
                tb_id = tb_obj.search([('cut_off_date', '>=', rec.payment_date)])
                rec.with_trial_balance = True if tb_id else False

    def trial_approve(self):
        self.trial_approved = True

    def trial_cancel(self):
        return self.env['account.payment.cancel'].create({
            'date': self.cancel_date,
            'journal_id': self.journal_id.id,
            'cancel_reason': self.cancel_reason
        }).with_context({'active_ids': self.ids}).cancel_payment()


class AccountPaymentCancel(models.TransientModel):
    _inherit = 'account.payment.cancel'

    with_trial_balance = fields.Boolean('With Trial Balance', copy=False, compute="get_has_trial_bal")

    @api.depends('date')
    def get_has_trial_bal(self):
        date_today = fields.Date.today()
        tb_obj = self.env['tf.ph.trial.balance']
        for rec in self:
            if rec.date != date_today:
                tb_id = tb_obj.search([('cut_off_date', '>=', rec.date)])
                rec.with_trial_balance = True if tb_id else False
            else:
                rec.with_trial_balance = False

    def action_request_cancel(self):
        payment_ids = self._context.get('active_ids', False)
        payment_ids = self.env['account.payment'].browse(payment_ids)
        payment_ids.write({
            'cancel_date': self.date,
            'cancel_trial_requested': True,
            'cancel_reason': self.cancel_reason,
        })