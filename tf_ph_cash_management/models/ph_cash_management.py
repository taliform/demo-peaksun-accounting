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
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.addons import decimal_precision as dp
from odoo.addons.base.models.ir_ui_view import transfer_field_to_modifiers, transfer_modifiers_to_node, \
    transfer_node_to_modifiers
from datetime import datetime
from lxml import etree

_LINE_TRANSACTION_TYPES = [('0', 'Purchase of Capital Goods'),
                           ('1', 'Purchase of Good Other than Capital Goods'),
                           ('2', 'Purchase of Services'),
                           ('3', 'Purchases Not Qualified for Input Tax'),
                           ('4', 'Others')]


class CashManagement(models.Model):
    _name = 'cash.management'
    _description = 'Cash Management'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    CM_STATE = [('draft', 'Draft'),
                ('open', 'Open'),
                ('for_closing', 'For Closing'),
                ('close', 'Closed')]

    AMOUNT_TYPE = [('establish_amount', 'Establish Cash Management for the first time'),
                   ('enter_previous', 'Enter previous Cash Management balance')]

    def _get_journal_id(self):
        '''
        @note: Returns Purchase Journal
        '''
        AccountJournal = self.env['account.journal']

        company_id = self.env.user.company_id
        journal = AccountJournal.search([('type', '=', 'purchase')], limit=1)
        if journal:
            journal_ids = AccountJournal.search([('type', '=', 'purchase'), ('company_id', '=', company_id.id)])
        else:
            raise ValidationError(_("There is no recorded purchase journal in the system.\n"
                                    "To define, go to Accounting > Configuration > Accounting > Journals."))
        if journal_ids:
            return journal_ids[0].id

    def _get_approvers(self):
        '''
        @note: Get Approvers (Config in Settings)
        '''
        for rec in self:
            rec.approver_ids = self.env['res.users']
            company_id = self.env.user.company_id
            # IF Basic Approval
            if company_id.cm_multiple_approval == 'basic':
                rec.approver_ids += company_id.basic_cm_approver_id
            else:
                rec.approver_ids = self.env['res.users']

    def _get_manager_ids(self):
        '''
        @return: Returns list if CM Managers
        '''
        for rec in self:
            manager_ids = self.env['res.users']
            user_ids = self.env['res.users']
            cm_group_id = self.sudo().env['res.groups'].search(
                [('category_id.name', '=', 'Cash Management'), ('name', '=', 'Custodian')])
            cm_user_group_id = self.sudo().env['res.groups'].search(
                [('category_id.name', '=', 'Cash Management'), ('name', '=', 'User')])

            if cm_group_id and cm_group_id.users:
                for user_id in cm_group_id.users:
                    manager_ids += user_id

            rec.manager_ids = manager_ids

            if cm_user_group_id and cm_user_group_id.users:
                for user_id in cm_user_group_id.users:
                    user_ids += user_id

            rec.user_ids = user_ids

    name = fields.Char(string='Reference', default='Draft Cash Management',
                       required=True, track_visibility='onchange')
    date = fields.Date(default=fields.Date.today,
                       track_visibility='onchange')
    state = fields.Selection(selection=CM_STATE, default='draft', string='Status',
                             track_visibility='onchange')
    cash_management_amount_type = fields.Selection(selection=AMOUNT_TYPE, string='Type',
                                                   help='Determines how the Cash Management amount is given',
                                                   track_visibility='onchange')
    analytic_account_id = fields.Many2one('account.analytic.account',
                                          string='Analytic Account', track_visibility='onchange')
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id,
                                  required=True, track_visibility='onchange')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.user.company_id, track_visibility='onchange')
    account_id = fields.Many2one('account.account', string='Account', track_visibility='onchange')
    journal_id = fields.Many2one('account.journal', string='Journal',
                                 default=_get_journal_id, track_visibility='onchange')
    purchase_tax_id = fields.Many2one('account.tax', string='Purchase Tax',
                                      track_visibility='onchange')
    closing_invoice_id = fields.Many2one('account.move', 'Closing Invoice', track_visibility='onchange',
                                         domain=[('type', '!=', 'entry')])
    cr_user_ids = fields.Many2many('res.users',
                                   help='Users that can access this cash management record from Cash Request.')
    invoice_ids = fields.One2many('account.move', 'cash_management_id', string='CM Invoices',
                                  domain=[('type', '!=', 'entry')])
    cash_request_ids = fields.One2many('cash.request', 'cash_management_id', string='Cash Request')
    journal_entry_ids = fields.One2many('account.move', 'cash_management_id', string='Journal Entries',
                                        domain=[('type', '=', 'entry')])
    replenishment_ids = fields.One2many('cash.replenishment', 'cash_management_id', string='Replenishment')
    requested_fund_ids = fields.One2many('account.move', 'cash_management_id',
                                         string='Fund Request Invoices', compute='_get_requested_funds')
    cash_transaction_ids = fields.One2many('cash.transaction', 'cash_management_id', string='CA Liquidation')
    cash_management_fund_ids = fields.One2many('cash.management.fund', 'cash_management_id',
                                               string='Cash Management Fund')
    balance_start = fields.Float(string='Opening Cash Control', track_visibility='onchange', copy=False)
    current_fund = fields.Float(string='Cash Fund', compute='_get_amount', track_visibility='onchange')
    remaining_fund = fields.Float(string='Cash Balance', compute='_get_amount',
                                  digits=dp.get_precision('Account'), track_visibility='onchange')
    remaining_fund_stored = fields.Float(string='Cash Balance (Stored)', related='remaining_fund', store=True)
    running_transaction = fields.Float(string='Total Cash Transactions', compute='_get_amount')
    unliquidated_amount = fields.Float(string='Unliquidated Amount', compute='_get_amount',
                                       track_visibility='onchange')
    unliquidated_amount_stored = fields.Float(string='Unliquidated Amount (Stored)', related='unliquidated_amount',
                                              store=True)
    total_amount = fields.Float(string='Total Amount', compute='_get_total_amount',
                                track_visibility='onchange')
    total_amount_stored = fields.Float(string='Total Amount (Stored)', related='total_amount', store=True)
    ongoing_replenishment = fields.Float(string='Ongoing Replenishment',
                                         compute='_get_total_amount',
                                         track_visibility='onchange')
    ongoing_replenishment_stored = fields.Float(string='Ongoing Replenishment (Stored)',
                                                related='ongoing_replenishment', store=True)
    total_cash_request = fields.Float(string='Total Cash Request', compute='_get_total_amount')
    total_cash_request_stored = fields.Float(string='Total Cash Request (Stored)', related='total_cash_request',
                                             store=True)
    total_returned = fields.Float(string='Total Returned', compute='_get_total_amount')
    total_reimbursed = fields.Float(string='Total Cash Reimbursed', compute='_get_total_amount')
    total_for_reimbursement = fields.Float(string='Total For Reimbursement',
                                           compute='_get_total_amount')
    total_for_reimbursement_stored = fields.Float(string='Total For Reimbursement (Stored)',
                                                  related='total_for_reimbursement', store=True)
    total_validated_replenishment = fields.Float(string='Total Validated Replenishment',
                                                 compute='_get_total_amount')
    total_received_replenishment = fields.Float(string='Total Received Replenishment',
                                                compute='_get_total_amount')
    unreplenished_cash_transaction_amount = fields.Float(string='Unreplenished Transactions',
                                                         compute='_get_total_amount', track_visibility='onchange')
    unreplenished_cash_transaction_amount_stored = fields.Float(string='Unreplenished Transactions (Stored)',
                                                                related='unreplenished_cash_transaction_amount',
                                                                store=True)
    previous_cash_amount = fields.Float(string='Previous Amount', track_visibility='onchange',
                                        copy=False)
    is_locked = fields.Boolean(string='Is Locked', default=False, copy=False)
    approver_ids = fields.Many2many('res.users', string='Approvers', compute='_get_approvers')
    manager_ids = fields.Many2many('res.users', compute='_get_manager_ids')
    user_ids = fields.Many2many('res.users', compute='_get_manager_ids')
    basic_cm_approver_id = fields.Many2one('res.users', string='Approver', help="Select the CM approver.")
    cm_multiple_approval = fields.Selection(selection=[('basic', 'Basic approval process (one step)')], default='basic',
                                            string="Levels of Approvals *")

    def _get_requested_funds(self):
        '''
        @note: Returns list of Requested funds
        '''
        for rec in self:
            invoice_ids = self.env['account.move'].search(
                [('cash_management_id', '=', rec.id), ('is_fund', '=', True), ('type', '!=', 'entry')])
            if invoice_ids:
                rec.requested_fund_ids = invoice_ids
            else:
                rec.requested_fund_ids = False

    def action_update_custodian(self):
        self.ensure_one()
        return {
            'name': 'Update Custodian',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'tf.cm.update.custodian',
            'view_id': self.env.ref('tf_ph_cash_management.tf_cm_update_custodian_wizard_form').id,
            'context': {'default_cm_id': self.id, 'default_custodian_id': self.create_uid.id},
            'type': 'ir.actions.act_window',
            'target': 'new'
        }

    def _get_amount(self):
        '''
        @note: Returns Current Fund, Remaining Fund, Running Transaction, Unliquidated Amount
        '''
        for rec in self:
            current_fund = running_transaction = unliquidated_amount = 0.0
            # Current Fund
            if rec.cash_management_fund_ids:
                for fund_id in rec.cash_management_fund_ids:
                    if fund_id.state == 'confirm':
                        current_fund += fund_id.amount
            if rec.state == 'draft' and rec.cash_management_amount_type == 'establish_amount':
                current_fund = 0
            if rec.cash_management_amount_type == 'enter_previous':
                current_fund += rec.previous_cash_amount

            rec.current_fund = current_fund

            # Running Transaction
            if rec.cash_transaction_ids:
                for transaction_id in rec.cash_transaction_ids:
                    if transaction_id.state == 'open':
                        running_transaction += transaction_id.amount

            rec.running_transaction = running_transaction

            # Unliquidated Amount
            if rec.cash_request_ids:
                for cr_id in rec.cash_request_ids:
                    if cr_id.state == 'open':
                        if not cr_id.cash_transaction_ids:
                            unliquidated_amount += cr_id.amount - sum(cr_id.return_ids.mapped('amount'))
                        else:
                            unliquidated_amount += cr_id.for_return

            rec.unliquidated_amount = unliquidated_amount

            rec.remaining_fund = (rec.current_fund + rec.total_returned + rec.total_received_replenishment) - (
                    rec.total_cash_request + rec.total_reimbursed)

    @api.depends('cash_request_ids', 'replenishment_ids', 'cash_transaction_ids', 'remaining_fund')
    def _get_total_amount(self):
        '''
        @note: Returns the Ongoing Replenishment, Total Amount, Total Cash Request, Total CR Return, Total Cash Reimbursed, Total For Reimbursement, Total Validated Replenishment, Total Received Replenishment, Unreplenished Transactions
              
        '''
        for rec in self:
            request_amount = total_cr_return = total_cr_reimburse = reimburse_amount = total_val_amount = total_rec_amount = ongoing_replenishment = unreplenished_amount = 0

            # Total Returned and Total Cash Reimbursed
            if rec.cash_request_ids:
                for cr_id in rec.cash_request_ids:
                    if cr_id.state not in ['draft', 'for_approval', 'release', 'cancel']:
                        request_amount += cr_id.amount

                        if cr_id.for_reimbursement > 0:
                            reimburse_amount += cr_id.for_reimbursement

                    total_cr_return += cr_id.total_returned
                    total_cr_reimburse += cr_id.total_reimbursed

            # Total Validated Replenishment and Total Received Replenishment
            if rec.replenishment_ids:
                for repl_id in rec.replenishment_ids:
                    if repl_id.state == 'done':
                        total_val_amount += repl_id.amount
                    if repl_id.state == 'receive':
                        total_rec_amount += repl_id.amount

            # Unreplenished Amount
            if rec.cash_transaction_ids:
                for transaction_id in rec.cash_transaction_ids:
                    if transaction_id.state == 'open':
                        unreplenished_amount += transaction_id.amount

                    # Ongoing Replenishment
                    if transaction_id.cash_replenishment_id and transaction_id.cash_replenishment_id.state != 'done' \
                            and not transaction_id.replenish_receive:
                        ongoing_replenishment += transaction_id.amount

            rec._get_amount()
            rec.total_returned = total_cr_return
            rec.total_cash_request = request_amount
            rec.total_reimbursed = total_cr_reimburse
            rec.total_for_reimbursement = reimburse_amount * -1
            rec.total_received_replenishment = total_rec_amount
            rec.total_validated_replenishment = total_val_amount
            rec.ongoing_replenishment = ongoing_replenishment
            rec.unreplenished_cash_transaction_amount = unreplenished_amount
            rec.unliquidated_amount = rec.unliquidated_amount
            rec.total_amount = rec.remaining_fund

    @api.model
    def create(self, vals):
        res = super(CashManagement, self).create(vals)
        sequence_obj = self.env['ir.sequence']
        res.update({'name': sequence_obj.next_by_code('cash.management')})
        return res

    def unlink(self):
        for rec in self:
            invoice_ids = False
            if rec.journal_entry_ids:
                invoice_ids = rec.invoice_ids.filtered(lambda l: l.state not in ['draft', 'cancel'])
            if rec.state != 'draft' or invoice_ids:
                raise ValidationError(_('You can only delete record(s) in draft state and no approved fund request.'))
        return super(CashManagement, self).unlink()

    def button_open(self):
        for rec in self:
            balance_start = 0
            if rec.cash_management_amount_type == 'enter_previous':
                if rec.previous_cash_amount <= 0:
                    raise ValidationError(_('Please enter a value for the Previous Amount'))
                else:
                    balance_start = rec.previous_cash_amount
            else:
                for fund_id in rec.cash_management_fund_ids:
                    if fund_id.state == 'confirm':
                        balance_start += fund_id.amount

                if balance_start <= 0:
                    raise ValidationError(
                        _('Cash Management should be funded\nPlease select a vendor bill to fund it.'))

            rec.write({'balance_start': balance_start,
                       'state': 'open'})

    def button_reopen(self):
        self.write({'state': 'open'})

    def button_for_closing(self):
        for rec in self:
            if rec.cash_request_ids:
                for cr_id in rec.cash_request_ids:
                    if cr_id.state not in ['close', 'cancel']:
                        raise ValidationError(_('Close the cash requests related to this CM record to proceed.'))

            if rec.unliquidated_amount != 0 or rec.total_for_reimbursement != 0:
                raise ValidationError(_('Unliquidated Amount and Reimbursement Amount should be equal to zero.'))

            if rec.replenishment_ids:
                for repl_id in rec.replenishment_ids:
                    if repl_id.state not in ['receive', 'done']:
                        raise ValidationError(_('Replenishments should be in Received state.'))

            if (rec.remaining_fund + rec.total_validated_replenishment) != rec.current_fund:
                raise ValidationError(
                    _('Remaining Fund plus Total Validated Replenishments should be equal to the Cash Fund.'))
            rec.write({'state': 'for_closing'})

    def view_cash_request_action(self):
        view = self.env.ref('tf_ph_cash_management.cash_request_tree')
        default_id = self.id if self.state == 'open' else False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cash Requests'),
            'res_model': 'cash.request',
            'view_type': 'form',
            'view_mode': 'tree,form,pivot,graph',
            'target': 'current',
            'context': {'default_cash_management_id': default_id, 'search_default_not_closed': 1},
            'domain': [('cash_management_id', '=', self.id)],
            'nodestroy': True,
        }


class CashRequest(models.Model):
    _name = 'cash.request'
    _description = 'Cash Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    CR_STATE = [('draft', 'Draft'),
                ('for_approval', 'For Approval'),
                ('release', 'For Request'),
                ('open', 'Open'),
                ('on_hold', 'On Hold'),
                #                 ('liq_for_approval', 'Liquidation for Approval'),
                ('close', 'Closed'),
                ('rejected', 'Rejected'),
                ('cancel', 'Cancelled')]

    def action_on_hold(self):
        self.write({'state': 'on_hold'})

    def action_reopen(self):
        self.write({'state': 'open'})

    @api.model
    def default_get(self, fields):
        res = super(CashRequest, self).default_get(fields)
        cm_ids = self.env['cash.management']
        for cm_id in self.env['cash.management'].search([('state', '=', 'open')]):
            if cm_id.cr_user_ids and self._uid in cm_id.cr_user_ids.ids or self._uid == cm_id.create_uid.id:
                cm_ids += cm_id
        if cm_ids:
            res.update({'cash_management_ids': cm_ids.ids})
        return res

    def _get_approvers(self):
        '''
        @note: Get Approvers (Config in Settings)
        '''
        for rec in self:
            rec.approver_ids = self.env['res.users']
            cm_id = rec.cash_management_id
            # IF Basic Approval
            if cm_id.cm_multiple_approval == 'basic':
                rec.approver_ids += cm_id.basic_cm_approver_id

    @api.depends('approver_ids', 'cash_management_id')
    def _check_user(self):
        '''
        @note: Checks if the current user is an approver.
        '''
        for rec in self:
            rec.is_approver = rec.is_custodian = False
            if self._uid in rec.approver_ids.ids:
                rec.is_approver = True
            if self._uid == rec.cash_management_id.create_uid.id:
                rec.is_custodian = True

    @api.depends('return_ids')
    def _check_returns(self):
        '''
        @note: Checks if the user returned the total amount of the CR
        '''
        for rec in self:
            rec.is_returned = False
            total_returned = sum(rec.return_ids.mapped('amount'))
            if total_returned == rec.amount and not rec.cash_transaction_ids:
                rec.is_returned = True

    def _hide_btn_cancel(self):
        '''
        @note: Hide 'Cancel' button for CR Approver
        '''
        for rec in self:
            # Basic Approval
            rec.hide_cancel = False
            cm_id = rec.cash_management_id
            # IF Basic Approval
            if cm_id.cm_multiple_approval == 'basic':
                approver_id = cm_id.basic_cm_approver_id
                if approver_id.id == self._uid and rec.state == 'for_approval':
                    rec.hide_cancel = True

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id,
                                 track_visibility='onchange')
    name = fields.Char(string='Name', default='Draft Cash Request', required=True, track_visibility='onchange')
    voucher_no = fields.Char(string='Voucher No.', track_visibility='onchange')
    reference = fields.Char(string='Reference', track_visibility='onchange')
    description = fields.Text(track_visibility='onchange')
    date_start = fields.Date(string='Date Start', copy=False)
    date_end = fields.Date(string='Date End', copy=False)
    date = fields.Date(default=fields.Date.today, track_visibility='onchange')
    state = fields.Selection(selection=CR_STATE, default='draft', string='Status', track_visibility='onchange')
    cash_management_state = fields.Selection(string='Cash Management State', related='cash_management_id.state')
    issued_to = fields.Many2one('res.users', string='Issued To', default=lambda self: self._uid,
                                track_visibility='onchange', copy=False)
    purchase_tax_id = fields.Many2one('account.tax', 'Purchase Tax', track_visibility='onchange')
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', track_visibility='onchange')
    cash_replenishment_id = fields.Many2one('cash.replenishment', string='Cash Replenishment')
    cash_management_id = fields.Many2one('cash.management', string='Cash Management', copy=False)
    cash_management_ids = fields.Many2many('cash.management', string='Cash Managements', copy=False)
    return_ids = fields.One2many('return.reimburse', 'cash_request_id', string='Returned',
                                 domain=[('type', '=', 'return')])
    reimburse_ids = fields.One2many('return.reimburse', 'cash_request_id', string='Reimbursed',
                                    domain=[('type', '=', 'reimburse')])
    cash_transaction_ids = fields.One2many('cash.transaction', 'cash_request_id', string='CA Liquidation')
    for_reimbursement = fields.Monetary(string='For Reimbursement', compute='_get_amount', track_visibility='onchange')
    for_reimbursement_stored = fields.Monetary(string='For Reimbursement (Stored)', related='for_reimbursement',
                                               store=True)
    total_transaction = fields.Monetary(string='Total Transaction', compute='_get_amount', track_visibility='onchange')
    total_transaction_stored = fields.Monetary(string='Total Transaction (Stored)', related='total_transaction',
                                               store=True)
    total_reimbursed = fields.Monetary(string='Total Reimbursed', compute='_get_amount')
    total_reimbursed_stored = fields.Monetary(string='Total Reimbursed (Stored)', related='total_reimbursed',
                                              store=True)
    total_returned = fields.Monetary(string='Total Returned', compute='_get_amount')
    total_returned_stored = fields.Monetary(string='Total Returned (Stored)', related='total_returned', store=True)
    for_return = fields.Monetary(string='For Return', compute='_get_amount', track_visibility='onchange')
    for_return_stored = fields.Monetary(string='For Return (Stored)', related='for_return', store=True)
    orig_amount_return = fields.Monetary('Original Amount to be Returned', compute='_get_amount')
    orig_amount_reimburse = fields.Monetary('Original Amount to be Reimbursed', compute='_get_amount')
    amount = fields.Monetary(track_visibility='onchange')
    currency_id = fields.Many2one(related='cash_management_id.currency_id', store=True)
    days_old_stored = fields.Integer(string='Days', copy=False)
    days_old = fields.Integer(string='Days Outstanding', compute='_get_days_old',
                              help='Computed as the difference between Cash Request "approval date" and either the "current date" or the Cash Request "closing date."')
    is_locked = fields.Boolean(related='cash_management_id.is_locked', store=True)
    #     is_liq_approved = fields.Boolean('Liquidations Approved', copy=False)
    is_liq_invoiced = fields.Boolean('Liquidations (Invoiced)', copy=False)
    is_approver = fields.Boolean(compute='_check_user')
    is_custodian = fields.Boolean(compute='_check_user')
    is_returned = fields.Boolean(compute='_check_returns')
    approver_ids = fields.Many2many('res.users', string='Approvers', compute='_get_approvers')
    hide_cancel = fields.Boolean(compute='_hide_btn_cancel')
    liq_reject_reason = fields.Text('Liquidation Rejection Reason', track_visibility='onchange', copy=False)
    cr_reject_reason = fields.Text('CR Rejection Reason', track_visibility='onchange', copy=False)
    note = fields.Text()
    manager_ids = fields.Many2many(related='cash_management_id.manager_ids')
    basic_cm_approver_id = fields.Many2one(related='cash_management_id.basic_cm_approver_id', string='Basic Approver')

    @api.model
    def is_allowed_transition(self, old_state, new_state):
        allowed = [('draft', 'for_approval'),
                   ('draft', 'release'),
                   ('draft', 'rejected'),
                   ('draft', 'cancel'),
                   ('for_approval', 'open'),
                   ('for_approval', 'rejected'),
                   ('for_approval', 'cancel'),
                   ('for_approval', 'draft'),
                   ('for_approval', 'release'),
                   ('release', 'cancel'),
                   ('release', 'open'),
                   ('open', 'close'),
                   #                    ('open', 'liq_for_approval'),
                   #                    ('liq_for_approval', 'open'),
                   #                    ('liq_for_approval', 'rejected'),
                   ('rejected', 'draft'),
                   ('rejected', 'open'),
                   ('rejected', 'cancel'), ]
        return (old_state, new_state) in allowed


    def change_state(self, new_state):
        for rec in self:
            if rec.is_allowed_transition(rec.state, new_state):
                rec.state = new_state
            else:
                raise ValidationError(_("The state has been already changed. Please refresh the page."))

    def view_cm_transaction_action(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Liquidations'),
            'res_model': 'cash.transaction',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {'default_cash_request_id': self.id},
            'domain': [('cash_request_id', '=', self.id)],
        }

    def _get_days_old(self):
        for rec in self:
            if rec.date_start and rec.date_end:
                delta = fields.Datetime.from_string(rec.date_end) - fields.Datetime.from_string(rec.date_start)
                rec.days_old = delta.days
            elif rec.date_start and not rec.date_end:
                delta = fields.Datetime.now() - fields.Datetime.from_string(rec.date_start)
                rec.days_old = delta.days
            else:
                rec.days_old = 0
            rec.days_old_stored = rec.days_old

    def _get_amount(self):
        '''
        @note: Returns Total Transaction, Total Returned, Total Reimbursed, For Return, For Reimbursement
        '''
        for rec in self:
            total_transaction = total_returned = for_return = orig_amount_return = 0
            total_reimbursed = for_reimbursement = orig_amount_reimburse = 0
            replinished_total_transaction = 0
            # Total Transaction
            if rec.cash_transaction_ids:
                for transaction_id in rec.cash_transaction_ids:
                    total_transaction += transaction_id.amount
                    if transaction_id.state in ['replenish', 'validated']:
                        replinished_total_transaction += transaction_id.amount

            # Total Returned
            if rec.return_ids:
                for return_id in rec.return_ids:
                    if return_id.type == 'return':
                        total_returned += return_id.amount

            # If the Custodian already returned an amount (from Form View)
            if not rec.cash_transaction_ids:
                if total_returned:
                    for_return = rec.amount - total_returned
                    orig_amount_return = rec.amount

            # Total Reimbursed
            if rec.reimburse_ids:
                for reim_id in rec.reimburse_ids:
                    if reim_id.type == 'reimburse':
                        total_reimbursed += reim_id.amount

            if rec.cash_transaction_ids:
                # For Return
                return_amount = rec.amount - (total_transaction + total_returned)
                if return_amount > 0 and rec.state not in ['draft', 'release', 'cancel']:
                    for_return = return_amount
                    orig_amount_return = rec.amount - total_transaction

                if rec.total_returned:
                    orig_amount_return = rec.amount - total_transaction

                # For Reimbursement
                reimburse_amount = rec.amount - ((total_transaction + total_returned) - total_reimbursed)

                if reimburse_amount < 0 and rec.state not in ['draft', 'release', 'cancel']:
                    for_reimbursement = abs(reimburse_amount)
                    orig_amount_reimburse = total_transaction - rec.amount

            rec.total_transaction = total_transaction
            rec.total_returned = total_returned
            rec.for_return = for_return
            rec.orig_amount_return = orig_amount_return
            rec.total_reimbursed = total_reimbursed
            rec.for_reimbursement = abs(for_reimbursement)
            rec.orig_amount_reimburse = orig_amount_reimburse

    @api.model
    def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
        '''
        @note: Removes the domain filter on Issued To field if the current user is a Custodian.
        '''
        res = super(CashRequest, self).fields_view_get(view_id=view_id, view_type=view_type,
                                                       toolbar=toolbar, submenu=submenu)

        is_custodian = self.env['res.users'].browse(self._uid).has_group(
            'tf_ph_cash_management.group_cash_management_manager')
        if view_type == 'form' and is_custodian:
            doc = etree.XML(res['arch'])
            element = doc.xpath("//field[@name='issued_to']")[0]
            element.attrib.pop('domain')
            res['arch'] = etree.tostring(doc)
        return res

    @api.model
    def create(self, vals):
        res = super(CashRequest, self).create(vals)
        is_custodian = self.env['res.users'].browse(self._uid).has_group(
            'tf_ph_cash_management.group_cash_management_manager')

        if not is_custodian and self._uid != res.issued_to.id:
            raise ValidationError(_('You are not allowed to request CR for other employees.'))

        if res.cash_management_id:
            remaining_fund = res.cash_management_id.remaining_fund
            if res.amount > remaining_fund:
                raise ValidationError(_('Not enough funds!\nRemaining Fund: %s') % (remaining_fund))

            if res.cash_management_id.state == 'close':
                raise ValidationError((
                                          "You are not allowed to add transactions. The Cash Management reference %s is already closed.") % res.cash_management_id.name)
        return res

    def write(self, vals):
        if ('state' in vals and vals['state'] or False) == 'open':
            vals['date_start'] = fields.datetime.now()
        elif ('state' in vals and vals['state'] or False) == 'close':
            vals['date_end'] = fields.datetime.now()
        return super(CashRequest, self).write(vals)

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_('You can only delete record(s) in draft state.'))
        return super(CashRequest, self).unlink()

    @api.onchange('cash_management_id')
    def onchange_cash_management(self):
        if self.cash_management_id:
            if self.cash_management_id.purchase_tax_id:
                self.purchase_tax_id = self.cash_management_id.purchase_tax_id
            if self.cash_management_id.analytic_account_id:
                self.analytic_account_id = self.cash_management_id.analytic_account_id

    def confirm_button(self):
        '''
        @note: This will send the CM record for approval.
        '''
        current_user = self.env['res.users'].browse(self._uid)
        is_custodian = current_user.has_group('tf_ph_cash_management.group_cash_management_manager')

        for rec in self:
            # Sequence
            sequence_obj = self.env['ir.sequence']
            rec.update({'name': sequence_obj.next_by_code('cash.request')})

            if rec.issued_to.id != self.env.uid:
                raise ValidationError(_(
                    "You are not allowed to send this record for approval. \nPlease inform %s to continue.") % rec.issued_to.name)
            elif is_custodian and rec.approver_ids == current_user:
                rec.change_state('for_approval')
                rec.button_release()
            else:
                rec.change_state('for_approval')
            # Basic Approval
            cm_id = rec.cash_management_id
            if cm_id.cm_multiple_approval == 'basic':
                approver_id = cm_id.basic_cm_approver_id
                if not approver_id:
                    raise ValidationError(_('Approver is not set.\n'
                                            'Please set an approver in Cash Management: %s.' % cm_id.name))

                rec.activity_schedule('tf_ph_cash_management.mail_act_cr_for_approval',
                                      user_id=approver_id.id,
                                      note=_(
                                          "Approve <a href='#' data-oe-model='%s' data-oe-id='%d'>%s</a> for user <a href='#' data-oe-model='%s' data-oe-id='%s'>%s</a>") % (
                                               rec._name, rec.id, rec.name,
                                               rec.issued_to._name, rec.issued_to.id, rec.issued_to.name))

            elif not cm_id.cm_multiple_approval:
                rec.change_state('release')

    def button_release(self):
        for rec in self:
            rec.change_state('open')
        # self.get_cm_amts()

    def approve_button(self):
        for rec in self:
            # For CR Approval
            if rec.state in ['draft', 'for_approval']:
                rec.change_state('release')

        #             # For CR Liquidation Approval
        #             if rec.state == 'liq_for_approval':
        #                 rec.is_liq_approved = True
        #                 for cat_id in rec.cash_transaction_ids: cat_id.write({'state': 'open'})
        #                 rec.change_state('open')

        # self.get_cm_amts()

    def decline_button(self):
        for rec in self:
            view = self.env.ref('tf_ph_cash_management.cash_request_reject_form')
            name = False
            if rec.state in ['draft', 'for_approval']: name = 'Reject CR'
            #             elif rec.state == 'liq_for_approval': name = 'Reject Liquidations'
            return {
                'name': _(name),
                'type': 'ir.actions.act_window',
                'res_model': 'cash.request.reject',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': view.id,
                'target': 'new',
                'context': {'default_cash_request_id': rec.id},
            }

    #     @api.multi
    #     def button_liq_approval(self):
    #         '''
    #         @note: This will transition the state from 'Open' to 'Liquidation For Approval'
    #         '''
    #         for rec in self:
    #             if not rec.cash_transaction_ids: raise UserError(_("There are no liquidations to be approved."))
    #             else:
    #                 for cat_id in rec.cash_transaction_ids: cat_id.write({'state':'for_approval'})
    #                 rec.change_state('liq_for_approval')
    #
    #                 # Basic Approval
    #                 cm_id = rec.cash_management_id
    #                 if cm_id.cm_multiple_approval == 'basic':
    #                     approver_id = cm_id.basic_cm_approver_id
    #                     rec.activity_schedule('ss_ph_cash_advance_enterprise.mail_act_ca_liq_for_approval',
    #                                             user_id=approver_id.id,
    #                                             note=_("Approve <a href='#' data-oe-model='%s' data-oe-id='%d'>%s</a> for user <a href='#' data-oe-model='%s' data-oe-id='%s'>%s</a>") % (
    #                                                 rec._name, rec.id, rec.name,
    #                                                 rec.issued_to._name, rec.issued_to.id, rec.issued_to.name))

    def button_cancel(self):
        for rec in self:
            if rec.state in ['for_approval', 'release']:
                rec.change_state('cancel')

    def button_close(self):
        for rec in self:
            # For Return and Reimbursement
            if rec.for_return > 0:
                raise ValidationError(_('Please return the amount of %s first.') % (rec.for_return))
            if rec.for_reimbursement > 0:
                raise ValidationError(_('Please reimburse the amount of %s first.') % (rec.for_reimbursement))

            if rec.total_returned:
                if rec.amount != (rec.total_transaction + rec.total_returned):
                    raise ValidationError(
                        _('Total Transaction plus Total Returned must be equal to Cash Request Amount'))

            if rec.total_reimbursed:
                if rec.total_transaction != (rec.amount + rec.total_reimbursed):
                    raise ValidationError(
                        _('Total Transaction plus Total Reimbursed must be equal to Cash Request Amount'))

            if not rec.cash_transaction_ids and rec.amount != rec.total_returned:
                raise ValidationError(_("Cash request isn't liquidated or returned yet."))

            # CR Liquidations
            for cat_id in rec.cash_transaction_ids:
                if cat_id.state != 'validated':
                    raise ValidationError(_('All liquidations should be validated.'))

            rec.change_state('close')
            for cat_id in rec.cash_transaction_ids: cat_id.write({'state': 'close'})

    #This function is weird, writing on fields not existing in cash transaction
    def get_cm_amts(self):
        for rec in self:
            rec.write({'cash_bal': rec.cash_management_id.remaining_fund,
                       'ongoing_rep': rec.cash_management_id.ongoing_replenishment,
                       'unrep_transac': rec.cash_management_id.unreplenished_cash_transaction_amount,
                       'unliq_amt': rec.cash_management_id.unliquidated_amount,
                       'reimbursement_amt': rec.cash_management_id.total_for_reimbursement})


class CashTransaction(models.Model):
    _name = 'cash.transaction'
    _description = 'CR Liquidation'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    CT_STATE = [('open', 'Open'),
                ('replenish', 'Replenished'),
                ('validated', 'Validated'),
                ('close', 'Closed'),
                ('cancel', 'Cancelled')]

    def _check_user_account(self):
        '''
        @note:  Allow CM Accountant to edit the following columns in the Replenishment Transaction line 
        (Expense Category, Tax, Partner, Analytic Account) which will change its corresponding CR Liquidation records
        '''
        for rec in self:
            rec.transac_readonly = False
            user_id = self.env['res.users'].browse(self._uid)
            is_cr_accounting = user_id.has_group('tf_ph_cash_management.group_cash_management_accountant')
            if rec.cash_replenishment_id.state == 'draft' and not is_cr_accounting: rec.transac_readonly = True
            if rec.cash_replenishment_id.state != 'draft': rec.transac_readonly = True

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0.0:
                raise ValidationError(_('Amount should be greater than zero!'))

    def _check_current_user(self):
        for rec in self:
            rec.is_amount_readonly = False
            user_id = self.env['res.users'].browse(self._uid)
            if user_id != rec.issued_to:
                rec.is_amount_readonly = True

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id,
                                 track_visibility='onchange')
    name = fields.Char(string='Reference', default='Draft CR Liquidation', required=True, track_visibility='onchange')
    or_no = fields.Char(string='OR No.', track_visibility='onchange')
    date = fields.Date(default=fields.Date.today, track_visibility='onchange')
    description = fields.Text(track_visibility='onchange')
    amount = fields.Float(string='Amount', digits=dp.get_precision('Account'), track_visibility='onchange')
    tax_id = fields.Many2one('account.tax', 'Tax', track_visibility='onchange')
    wht_tax_id = fields.Many2one('account.tax', 'Withholding Tax', track_visibility='onchange')
    partner_id = fields.Many2one('res.partner', string='Partner', track_visibility='onchange')
    account_id = fields.Many2one('account.account', related='expense_category_id.account_id', string='Account',
                                 track_visibility='onchange')
    cash_request_id = fields.Many2one('cash.request', string='Cash Requisition', track_visibility='onchange',
                                      copy=False)
    expense_category_id = fields.Many2one('expense.category', string='Expense Category', track_visibility='onchange')
    issued_to = fields.Many2one(related='cash_request_id.issued_to', store=True, track_visibility='onchange')
    cash_management_id = fields.Many2one(related='cash_request_id.cash_management_id', store=True)
    cash_replenishment_id = fields.Many2one('cash.replenishment', string='Cash Replenishment', copy=False)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account',
                                          track_visibility='onchange')
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')
    replenish_receive = fields.Boolean(string='Replenishment Received?', copy=False)
    ct_cash_management_state = fields.Selection(related='cash_management_id.state', string='Cash Management State')
    state = fields.Selection(selection=CT_STATE, string='Status', default='open', track_visibility='onchange')
    cr_state = fields.Selection(related='cash_request_id.state', string='Cash Request State')
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.user.company_id.currency_id,
                                  required=True)
    transaction_type = fields.Selection(_LINE_TRANSACTION_TYPES, string='Transaction Type', track_visibility='onchange')
    is_amount_readonly = fields.Boolean(compute='_check_current_user')
    transac_readonly = fields.Boolean(compute='_check_user_account')
    approver_ids = fields.Many2many(related='cash_request_id.approver_ids')

    @api.model
    def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
        res = super(CashTransaction, self).fields_view_get(view_id=view_id, view_type=view_type,
                                                           toolbar=toolbar, submenu=submenu)

        doc = etree.XML(res['arch'])
        user_id = self.env.user
        cr_id = self._context.get('default_cash_request_id', False)
        if cr_id:
            cr_id = self.env['cash.request'].browse(cr_id)
        is_cr_manager = user_id.has_group('tf_ph_cash_management.group_cash_management_manager')
        is_accounting = user_id.has_group('account.group_account_invoice')
        is_cr_accounting = user_id.has_group('tf_ph_cash_management.group_cash_management_accountant')

        if view_type in ['tree', 'form']:
            # CR Accounting
            # Accounting/Custodian can only edit the details of the liquidations if Open state (except Amount)
            if cr_id and user_id != cr_id.issued_to:
                if is_accounting or is_cr_accounting or is_cr_manager:
                    for field in doc.xpath("//field[@name='cash_request_id']"):
                        field.set('attrs', "{'readonly': [('state','!=','open')]}")
                        setup_modifiers(field, res['fields']['cash_request_id'])

                    for field in doc.xpath("//field[@name='or_no']"):
                        field.set('attrs', "{'readonly': [('state','!=','open')]}")
                        setup_modifiers(field, res['fields']['or_no'])

                    for field in doc.xpath("//field[@name='description']"):
                        field.set('attrs', "{'readonly': [('state','!=','open')]}")
                        setup_modifiers(field, res['fields']['description'])

                    for field in doc.xpath("//field[@name='date']"):
                        field.set('attrs', "{'readonly': [('state','!=','open')]}")
                        setup_modifiers(field, res['fields']['date'])

                    for field in doc.xpath("//field[@name='amount']"):
                        field.set('readonly', '1')
                        setup_modifiers(field, res['fields']['amount'])

                    for field in doc.xpath("//field[@name='tax_id']"):
                        field.set('attrs', "{'readonly': [('state','!=','open')]}")
                        setup_modifiers(field, res['fields']['tax_id'])

                    for field in doc.xpath("//field[@name='partner_id']"):
                        field.set('attrs', "{'readonly': [('state','!=','open')]}")
                        setup_modifiers(field, res['fields']['partner_id'])

                    for field in doc.xpath("//field[@name='analytic_account_id']"):
                        field.set('attrs', "{'readonly': [('state','!=','open')]}")
                        setup_modifiers(field, res['fields']['analytic_account_id'])

                    for field in doc.xpath("//field[@name='analytic_tag_ids']"):
                        field.set('attrs', "{'readonly': [('state','!=','open')]}")
                        setup_modifiers(field, res['fields']['analytic_tag_ids'])

                    for field in doc.xpath("//field[@name='expense_category_id']"):
                        field.set('attrs', "{'readonly': [('state','!=','open')]}")
                        setup_modifiers(field, res['fields']['expense_category_id'])

                    for field in doc.xpath("//field[@name='transaction_type']"):
                        field.set('attrs', "{'readonly': [('state','!=','open')]}")
                        setup_modifiers(field, res['fields']['transaction_type'])

                res['arch'] = etree.tostring(doc)
        return res

    @api.model
    def create(self, vals):
        res = super(CashTransaction, self).create(vals)
        if res.tax_id and res.partner_id:
            partner_id = res.partner_id
            if not partner_id.vat:
                raise ValidationError(_('Selected Partner should have a TIN'))

        if res.cash_request_id:
            is_custodian = self.env.user.has_group(
                'tf_ph_cash_management.group_cash_management_manager')
            issued_to_id = res.cash_request_id.issued_to
            # res.cash_request_id.write({'unliq_amt': res.cash_management_id.unliquidated_amount,
            #                            'reimbursement_amt': res.cash_management_id.total_for_reimbursement})

            if not is_custodian and self._uid != issued_to_id.id:
                raise ValidationError(_("You are not allowed to add transactions."
                                        "Please inform the user indicated in the field <issued to> of related Cash Request to continue."))

        if res.cash_request_id.state == 'close':
            raise ValidationError(_("You are not allowed to add transactions."
                                    "The Cash Request reference %s is already closed.") % res.cash_request_id.name)

        if res.cash_management_id and res.cash_management_id.state == 'close':
            raise ValidationError(_("You are not allowed to add transactions."
                                    "The Cash Management reference %s is already closed.") % res.cash_management_id.name)

        sequence_obj = self.env['ir.sequence']
        res.update({'name': sequence_obj.next_by_code('cash.transaction')})
        return res

    def write(self, vals):
        is_custodian = self.env['res.users'].browse(self._uid).has_group(
            'tf_ph_cash_management.group_cash_management_manager')
        is_accountant = self.env['res.users'].browse(self._uid).has_group(
            'tf_ph_cash_management.group_cash_management_accountant')
        if self._uid != self.issued_to.id and 'state' not in vals and 'replenish_receive' not in vals and not is_custodian:
            # Allow CM Accountant to edit transactions (Replenishment record)
            if not is_accountant and self.cash_replenishment_id.state != 'draft':
                raise ValidationError(_("You are not allowed to edit transactions."
                                        "Please inform the user indicated in the field <issued to> of related Cash Request to continue."))
        res = super(CashTransaction, self).write(vals)
        return res

    def unlink(self):
        for rec in self:
            if rec.state != 'open':
                raise ValidationError(_('You may only delete liquidations in open state.'))

            if rec.cash_request_id.issued_to.id != self._uid and \
                    not self.env.user.has_group('tf_ph_cash_management.group_cash_management_manager'):
                raise ValidationError(_('You are not allowed to delete this record.'))
        return super(CashTransaction, self).unlink()

    @api.onchange('cash_request_id', 'expense_category_id')
    def onchange_cash_request(self):
        if self.cash_request_id:
            if self.cash_request_id.purchase_tax_id:
                self.tax_id = self.cash_request_id.purchase_tax_id.id
            if self.cash_request_id.analytic_account_id:
                self.analytic_account_id = self.cash_request_id.analytic_account_id.id

        if self.expense_category_id:
            if self.tax_id:
                self.transaction_type = self.expense_category_id.transaction_type

    @api.onchange('tax_id')
    def onchange_tax_id(self):
        if not self.tax_id:
            self.transaction_type = False
        elif self.tax_id and self.expense_category_id:
            self.transaction_type = self.expense_category_id.transaction_type


class CashReplenishment(models.Model):
    _name = 'cash.replenishment'
    _description = 'Cash Replenishment'
    _inherit = ['mail.thread']
    _order = 'id desc'

    CP_STATE = [('draft', 'Draft'),
                ('locked', 'Locked'),
                ('validate', 'Validated'),
                ('release', 'In-Process'),
                ('receive', 'Received'),
                ('done', 'Done')]

    def _get_journal_entry_config_account(self):
        '''
        @note: Returns Clearing Journal (Accounting Configuration)
        '''
        company = self.env.user.company_id
        journal_id = company.cm_journal_id

        if journal_id:
            journal_id = self.env['account.journal'].browse(journal_id.id)
            if not journal_id.default_debit_account_id or not journal_id.default_credit_account_id:
                raise ValidationError(_('Default Credit/Debit Account for Clearing Journal not set.\n'
                                        'Please configure default credit/debit account entry for clearing journal to continue.'))
        if not journal_id:
            raise ValidationError(_('Journal Entry for Clearing is not set.\n'
                                    'To configure, go to Accounting > Configuration > Settings > Cash Management > Clearing Journal.'))
        return journal_id.id

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id,
                                 track_visibility='onchange')
    name = fields.Char(string='Reference', default='Draft Cash Replenishment',
                       required=True, track_visibility='onchange')
    date = fields.Date(default=fields.Date.today, track_visibility='onchange')
    invoice_id = fields.Many2one('account.move', string='Replenishment Invoice', domain=[('type', '!=', 'entry')])
    journal_id = fields.Many2one('account.journal', string='Payment Method',
                                 default=_get_journal_entry_config_account,
                                 track_visibility='onchange')
    custodian_id = fields.Many2one(related='cash_management_id.create_uid',
                                   string='Custodian', store=True,
                                   track_visibility='onchange')
    cash_management_id = fields.Many2one('cash.management', string='Cash Management')
    amount = fields.Monetary(compute='_get_total_amount', track_visibility='onchange')
    total_expense_category = fields.Float(compute='_get_total_amount')
    state = fields.Selection(selection=CP_STATE, string='Status', default='draft',
                             track_visibility='onchange')
    invoice_state = fields.Selection(related='invoice_id.invoice_payment_state', string='Invoice State')
    cash_management_state = fields.Selection(related='cash_management_id.state',
                                             string='Cash Management State')
    cash_transaction_ids = fields.One2many('cash.transaction', 'cash_replenishment_id',
                                           string='CR Liquidation')
    replenishment_line_ids = fields.One2many('account.move', 'cash_replenishment_id', domain=[('type', '!=', 'entry')],
                                             string='Replenishment Line')
    expense_category_line_ids = fields.One2many('replenish.expense.category', 'replenish_id',
                                                string='Expense Category Line')
    unliquidated_cash_request_ids = fields.One2many('cash.request', 'cash_replenishment_id',
                                                    string='Unliquidated Cash Requisitions',
                                                    compute='_get_list_ids')
    reimbursement_cash_request_ids = fields.One2many('cash.request', 'cash_replenishment_id',
                                                     string='For Reimbursement', compute='_get_list_ids')
    unreplenished_cash_transaction_ids = fields.One2many('cash.transaction', 'cash_replenishment_id',
                                                         string='Unreplenished Transactions',
                                                         compute='_get_list_ids')
    cash_count_ids = fields.One2many('cash.count', 'cash_replenishment_id', string='Cash Count')
    overall_cash_count = fields.Float(compute='_get_overall_cash_count', store=True)
    cash_fund = fields.Float(related='cash_management_id.current_fund', string='Cash Fund', store=True)
    ongoing_rep = fields.Float(compute='_get_replenish_amt', string='Ongoing Replenishment')
    unrep_transac = fields.Float(compute='_get_replenish_amt', string='Unreplenished Transactions Amount')
    unliq_amt = fields.Float(compute='_get_replenish_amt', string='Unliquidated Amount')
    reimbursement_amt = fields.Float(compute='_get_replenish_amt', string='Reimbursement Amount')
    cash_balance = fields.Float(compute='_get_replenish_amt', string='Cash Balance')
    tot_cash_count = fields.Float(compute='_get_replenish_amt', string='Cash Count Total')
    overage_shortage = fields.Float(compute='_get_replenish_amt', string='Overage/Shortage')
    is_locked = fields.Boolean(string='Is Locked', default=False, copy=False)
    currency_id = fields.Many2one(related='cash_management_id.currency_id', store=True)
    cr_liq_inv_count = fields.Integer("CR Liquidation Invoices", compute="_get_cr_liq_inv_count")

    def action_unlock(self):
        self.write({'is_locked': False})

    def _get_cr_liq_inv_count(self):
        for rec in self:
            rec.cr_liq_inv_count = len(rec.replenishment_line_ids)

    def _get_total_amount(self):
        '''
        @note: Returns Total Replenishment Amount, Total Expense Category
        '''
        for rec in self:
            amount = 0
            total_expense_category = 0
            for repl_id in rec.replenishment_line_ids:
                amount += repl_id.amount_untaxed
            
            for exp_categ_id in rec.expense_category_line_ids:
                total_expense_category += exp_categ_id.amount

            rec.amount = amount
            rec.total_expense_category = total_expense_category

    def _get_list_ids(self):
        '''
        @note: Returns List of Unreplenished Transactions, Unreplenished Cash Requests, For Reimbursements
        '''
        CashTransaction = self.env['cash.transaction']
        CashRequest = self.env['cash.request']

        for rec in self:
            # Unreplenished Transactions
            rec.unreplenished_cash_transaction_ids = CashTransaction.search([
                ('cash_management_id', '=', rec.cash_management_id.id),
                ('state', '=', 'open')])

            # Unreplenished Cash Requests and For Reimbursement
            unliquidated_cr_ids = self.env['cash.request']
            reimbursement_cr_ids = self.env['cash.request']
            cr_ids = CashRequest.search([('cash_management_id', '=', rec.cash_management_id.id)])
            if cr_ids:
                for cr_id in cr_ids:
                    if cr_id.state not in ['draft', 'release', 'cancel']:
                        if cr_id.for_return > 0: unliquidated_cr_ids += cr_id
                        if cr_id.for_reimbursement > 0: reimbursement_cr_ids += cr_id
                rec.unliquidated_cash_request_ids = unliquidated_cr_ids
                rec.reimbursement_cash_request_ids = reimbursement_cr_ids

    @api.depends('cash_count_ids')
    def _get_overall_cash_count(self):
        '''
        @note: Returns Overall Cash Count amount
        '''
        for rec in self:
            if len(rec.cash_count_ids) > 0:
                rec.overall_cash_count = 0
                for count in rec.cash_count_ids:
                    rec.overall_cash_count += count.total

    def _get_replenish_amt(self):
        ongoing_rep = self.cash_management_id.ongoing_replenishment
        unrep_transac = self.cash_management_id.unreplenished_cash_transaction_amount
        unliq_amt = self.cash_management_id.unliquidated_amount
        reimbursement_amt = self.cash_management_id.total_for_reimbursement

        self.ongoing_rep = ongoing_rep
        self.unrep_transac = unrep_transac
        self.unliq_amt = unliq_amt
        self.reimbursement_amt = reimbursement_amt
        self.cash_balance = self.cash_management_id.current_fund - (
                ongoing_rep + unrep_transac + unliq_amt + reimbursement_amt)
        self.tot_cash_count = self.overall_cash_count
        self.overage_shortage = self.cash_balance - self.tot_cash_count

    @api.model
    def create(self, vals):
        res = super(CashReplenishment, self).create(vals)
        if res.cash_transaction_ids:
            cm_ids = []
            for cat_id in res.cash_transaction_ids:
                cm_id = cat_id.cash_request_id.cash_management_id
                if not cm_ids:
                    cm_ids.append(cm_id)
                else:
                    if cm_id not in cm_ids:
                        raise ValidationError(_('The selected liquidations have different CM reference.'))

        sequence_obj = self.env['ir.sequence']
        res.update({'name': sequence_obj.next_by_code('cash.replenishment')})
        return res

    def unlink(self):
        for rec in self:
            if rec.state == 'draft':
                rec.cash_transaction_ids.write({'state': 'open'})

                for line in rec.replenishment_line_ids:
                    for inv_line_id in line.invoice_line_ids:
                        if inv_line_id.cash_transaction_id: inv_line_id.cash_transaction_id.write({'state': 'open'})
            else:
                raise ValidationError(_('You can only delete a replenishment record in Draft state.'))
        return super(CashReplenishment, self).unlink()

    def get_journal_entry_config_crdr(self):
        '''
        @note: Return Credit and Debit Account of the Clearing Journal
        '''
        for rec in self:
            default_credit_account_id = default_debit_account_id = False
            if not rec.journal_id:
                raise ValidationError(_('Journal Entry for Clearing is not set.\n'
                                        'Please configure a valid journal entry for clearing to continue.'))
            elif not rec.journal_id.default_debit_account_id or not rec.journal_id.default_credit_account_id:
                raise ValidationError(_('Default credit/debit account for Clearing Journal not set.\n'
                                        'Please configure default credit/debit account entry for clearing journal to continue.'))
            else:
                default_credit_account_id = rec.journal_id.default_credit_account_id
                default_debit_account_id = rec.journal_id.default_debit_account_id

        return {'default_credit_account_id': default_credit_account_id.id,
                'default_debit_account_id': default_debit_account_id.id}

    def button_locked(self):
        for rec in self:
            rec.write({'state': 'locked', 'is_locked': True})
            rec.cash_management_id.write({'is_locked': True})

    def confirm_replenishment(self):
        view = self.env.ref('tf_ph_cash_management.replenishment_cash_count_view')

        return {
            'type': 'ir.actions.act_window',
            'name': 'Replenishment Confirmation',
            'res_model': 'replenishment.cash.count',
            'view_id': view.id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_cash_rep_id': self.id,
                        'default_cash_balance': self.cash_management_id.remaining_fund,
                        'default_cash_count_total': self.overall_cash_count},
            'domain': [],
            'nodestroy': True,
        }

    def replenishment_validate(self):
        aml_obj = self.env['account.move.line']
        ap_obj = self.env['account.payment']
        am_obj = self.env['account.move']

        company_id = self.env.user.company_id
        for rec in self:
            # Create CR Liquidation Invoices
            ct_ids = rec.cash_transaction_ids
            if ct_ids:
                rec.create_ct_invoices(ct_ids)

            if rec.replenishment_line_ids:
                for invoice_id in rec.replenishment_line_ids:
                    # Validate invoice
                    invoice_id.action_post()

                    # Add the CM Reference in the generated Journal Entry
                    invoice_id.write({'narration': 'Generation of Vendor Bill %s for expenses.' % invoice_id.name})

                    # Create Payment
                    ap_vals = {
                        'payment_type': 'outbound',
                        'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                        'payment_reference': invoice_id.name,
                        'partner_type': 'supplier',
                        'partner_id': self.env['res.partner']._find_accounting_partner(invoice_id.partner_id).id,
                        'amount': invoice_id.amount_residual,
                        'currency_id': invoice_id.currency_id.id,
                        'payment_date': fields.Date.context_today(self),
                        'journal_id': self.env.user.company_id.cm_journal_id.id,
                        'invoice_ids': [(6, 0, invoice_id.ids)],
                    }
                    payment_id = ap_obj.create(ap_vals)
                    payment_id.post()
                    #invoice_id.assign_outstanding_credit(payment_id.move_line_ids.id)
                    if invoice_id.invoice_payment_state == 'paid' and invoice_id.payment_move_line_ids:
                        invoice_id.payment_move_line_ids.write({
                            # 'cash_management_id': rec.cash_management_id.id,
                            'ref': 'Expenses Payment: ' + rec.name,
                            'internal_note': 'Payment of Vendor Bill: ' +
                                         invoice_id.name + ' at replenishment validation.'
                        })

            # Validate Requisition and Liquidations
            rec.write({'state': 'validate'})
            for cat_id in rec.cash_transaction_ids:
                cat_id.write({'state': 'validated'})

            # Journal Entries
            if rec.cash_management_id.state == 'for_closing':
                journal_id = self._get_journal_entry_config_account()
                account_id = self.get_journal_entry_config_crdr()
                analytic_account_id = False
                if rec.cash_management_id.analytic_account_id:
                    analytic_account_id = rec.cash_management_id.analytic_account_id.id

                if not company_id:
                    raise ValidationError(_('There is no default company for the current user!'))

                if not account_id['default_debit_account_id']:
                    raise ValidationError(_('The CM Journal does not have a default debit account'))

                account_move_vals = {'journal_id': journal_id.id,
                                     'ref': rec.cash_management_id.name}
                account_move_id = am_obj.create(account_move_vals)
                account_move_line_vals1 = {'name': 'To close ' + str(rec.cash_management_id.name),
                                           'account_id': account_id['default_debit_account_id'],
                                           'debit': rec.amount,
                                           'move_id': account_move_id.id,
                                           'analytic_account_id': analytic_account_id,
                                           'partner_id': False,
                                           'company_id': company_id.id,
                                           }
                aml_obj.create(account_move_line_vals1)
                account_move_line_vals2 = {'name': 'To close ' + str(rec.cash_management_id.name),
                                           'account_id': rec.cash_management_id.account_id.id,
                                           'credit': rec.amount,
                                           'move_id': account_move_id.id,
                                           'analytic_account_id': analytic_account_id,
                                           'partner_id': False,
                                           'company_id': company_id.id,
                                           }
                aml_obj.create(account_move_line_vals2)
                rec.write({'state': 'done'})

    def action_view_cr_liq_ids(self):
        return {
            'name': 'CR Liquidation Invoices',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'domain': [('id', 'in', self.replenishment_line_ids.ids)],
            'views': [(self.env.ref('tf_ph_cash_management.tf_account_move_tree_readonly').id, 'tree'),
                      (False, 'form')],
            'type': 'ir.actions.act_window',
            'target': 'current'
        }


    def create_ct_invoices(self, ct_ids):
        '''
        @note: Created CR Liquidation invoices
        '''
        # Init
        rexp_categ_obj = self.env['replenish.expense.category']
        inv_obj = self.env['account.move']
        today = fields.Date.context_today(self)
        cr_liq_journal_id = self.env.user.company_id.cr_liq_journal_id.id
        cm_id = self.cash_management_id

        # Create Invoices
        partner_ids = ct_ids.mapped('partner_id')
        for partner_id in partner_ids:
            inv_vals = {
                'currency_id': cm_id.currency_id.id,
                'journal_id': cr_liq_journal_id,
                'cash_management_id': cm_id.id,
                'cash_replenishment_id': self.id,
                'ref': "Expenses: %s" % cm_id.name,
                'partner_id': partner_id.id,
                'invoice_date': today,
                'is_replenishment': True,
                'type': 'in_invoice',
                'invoice_line_ids': []
            }
            for ct_id in ct_ids.filtered(lambda c: c.partner_id == partner_id):
                categ_id = ct_id.expense_category_id
                name = "[%s]%s" % (cm_id.name, categ_id.name)
                if ct_id.or_no:
                    name += " - %s" % ct_id.or_no
                if ct_id.description:
                    name += " - %s" % ct_id.description

                inv_vals.update({'base_transaction_type': ct_id.transaction_type})

                inv_vals['invoice_line_ids'].append((0, 0, {
                    'account_id': categ_id.account_id.id,
                    'analytic_account_id': ct_id.analytic_account_id.id,
                    'journal_id': cr_liq_journal_id or cm_id.journal_id.id,
                    'name': name,
                    'cash_transaction_id': ct_id.id,
                    'price_unit': ct_id.amount,
                    'quantity': 1,
                    'transaction_type': ct_id.transaction_type,
                    'tax_ids': [(6, 0, ct_id.tax_id.ids + ct_id.wht_tax_id.ids)]
                }))

                # Create Replenishment Category
                ext_repl_expense_category = rexp_categ_obj.search(
                    [('expense_category_id', '=', categ_id.id)])
                if not ext_repl_expense_category:
                    repl_exp_vals = {'expense_category_id': categ_id.id,
                                     'replenish_id': self.id}
                    rexp_categ_obj.create(repl_exp_vals)

            inv_obj.create(inv_vals)

    def replenishment_release(self):
        AccountInvoice = self.env['account.move']
        today = fields.Date.today()
        inv_lines = []

        for rec in self:
            repl_line_id = rec.replenishment_line_ids[0]
            repl_id = repl_line_id.cash_replenishment_id
            partner_id = repl_id.custodian_id.partner_id
            cm_id = repl_line_id.cash_management_id
            # Create Supplier Invoice Lines
            account_id = self.get_journal_entry_config_crdr()
            inv_lines.append((0, 0, {'name': str(cm_id.name) + ' - ' + str(rec.name),
                                     'account_id': account_id['default_debit_account_id'],
                                     'cash_transaction_id': False,
                                     'analytic_account_id': False,
                                     'tax_ids': False,
                                     'price_unit': rec.amount,
                                     'quantity': 1}))

            # Create Supplier Invoice 
            invoice_id = AccountInvoice.create({#'account_id': partner_id.property_account_payable_id.id,
                                                'ref': str(cm_id.name) + ' - ' + str(repl_id.name),
                                                'currency_id': repl_line_id.currency_id.id,
                                                'cash_management_id': cm_id.id,
                                                'journal_id': cm_id.journal_id.id,
                                                'partner_id': partner_id.id,
                                                'invoice_date': today.strftime('%Y-%m-%d'),
                                                'is_replenishment': True,
                                                'is_repl_released': True,
                                                'type': 'in_invoice',
                                                'invoice_line_ids': inv_lines,
                                                'ref': 'Fund replenishment: ' + rec.name,
                                                'narration': 'Vendor Bill ' + cm_id.name + ' for replenishing fund.'
                                                })
            # Validate invoice
            invoice_id.action_post()
            rec.write({'state': 'release', 'invoice_id': invoice_id.id})

    def replenishment_receive(self):
        for rec in self:
            for invoice_id in rec.replenishment_line_ids:
                invoice_id.write({'received': True})
                for line in invoice_id.invoice_line_ids:
                    ct_id = line.cash_transaction_id
                    ct_id.write({'replenish_receive': True})

            rec.write({'state': 'receive'})

    def action_view_cm_report(self):
        view_id = self.env['ir.ui.view'].search([('name', '=', 'view.replenish.report.form')])

        return {
            'name': _("Replenishment Report"),
            'view_mode': 'form',
            'view_id': view_id[0].id,
            'res_model': 'replenishment.report',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': {'default_cash_reple_id': self.id,
                        'default_cash_fund': self.cash_fund,
                        'default_ongoing_rep': self.ongoing_rep,
                        'default_unrep_transac': self.unrep_transac,
                        'default_unliq_amt': self.unliq_amt,
                        'default_reimbursement_amt': self.reimbursement_amt,
                        'default_cash_balance': self.cash_balance,
                        'default_tot_cash_count': self.tot_cash_count,
                        'default_overage_shortage': self.overage_shortage}
        }


class CashCount(models.Model):
    _name = 'cash.count'
    _description = 'Cash Count'

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id,
                                 track_visibility='onchange')
    cash_replenishment_id = fields.Many2one('cash.replenishment', string='Cash Replenishment')
    denomination = fields.Float(string='Denomination')
    qty = fields.Float(string='Quantity')
    total = fields.Float(compute='_get_amount_total', store=True)

    @api.depends('denomination', 'qty')
    def _get_amount_total(self):
        for rec in self:
            rec.total = rec.denomination * rec.qty


class CashManagementFund(models.Model):
    _name = 'cash.management.fund'
    _description = 'Cash Management Fund'

    CMF_STATE = [('draft', 'Draft'),
                 ('confirm', 'Confirmed')]

    CMF_TYPE = [('fund', 'Fund'),
                ('replenish', 'Replenish')]

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id,
                                 track_visibility='onchange')
    cash_management_id = fields.Many2one('cash.management', string='Cash Management')
    custodian_id = fields.Many2one('res.users', string='Custodian')
    invoice_id = fields.Many2one('account.move', string='Vendor Bill', copy=False)
    date = fields.Date(default=fields.Date.today)
    amount = fields.Float(compute='_get_amount_total', store=True)
    type = fields.Selection(selection=CMF_TYPE, default='fund', required=True, readonly=True)
    state = fields.Selection(selection=CMF_STATE, default='draft', string='Status')

    @api.depends('invoice_id')
    def _get_amount_total(self):
        for rec in self:
            if rec.invoice_id:
                rec.amount = rec.invoice_id.amount_total

    def confirm_fund(self):
        for rec in self:
            if rec.amount == 0:
                raise ValidationError(_('Amount should be greater than zero.'))
            duplicate_check = self.search(
                [('invoice_id', '=', rec.invoice_id.id), ('cash_management_id', '=', rec.cash_management_id.id)])
            if len(duplicate_check) > 1:
                raise ValidationError(_('You cannot use this invoice for this Cash Management more than once.'))
            invoice_id = rec.invoice_id
            invoice_id.write({'received': True,
                              'cash_management_id': rec.cash_management_id.id,
                              'ref': 'Funding of ' + rec.cash_management_id.name,
                              'narration': 'Vendor Bill for funding of ' + rec.cash_management_id.name})

            if invoice_id.state == 'paid' and invoice_id.payment_move_line_ids:
                move_ids = []
                for move_line in invoice_id.payment_move_line_ids:
                    if move_line.move_id not in move_ids: move_ids.append(move_line.move_id)
                if move_ids:
                    for move_id in move_ids:
                        move_id.write({'cash_management_id': rec.cash_management_id.id,
                                       'narration': 'Payment of Vendor Bill ' + rec.invoice_id.name + ' for funding of ' + rec.cash_management_id.name})

            rec.write({'state': 'confirm'})

    def unlink(self):
        for rec in self:
            if rec.invoice_id.invoice_payment_state == 'paid':
                raise ValidationError(_('You cannot delete paid cash management fund.'))
        return super(CashManagementFund, self).unlink()


class RequestFund(models.Model):
    _name = 'request.fund'
    _description = 'Request Fund'

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id,
                                 track_visibility='onchange')
    cash_management_id = fields.Many2one('cash.management', string='Cash Management')
    custodian_id = fields.Many2one('res.users', string='Custodian')
    invoice_id = fields.Many2one('account.move', 'Invoice')
    description = fields.Text()
    amount = fields.Float()

    @api.constrains('amount')
    def check_amount(self):
        if self.amount <= 0:
            raise ValidationError(_('The amount should greater than zero.'))

    def send_fund_request(self):
        AccountInvoiceLine = self.env['account.move.line']
        AccountInvoice = self.env['account.move']
        today = datetime.now().date()

        for rec in self:
            # Check for existing fund request
            if rec.cash_management_id.invoice_ids:
                ext_invoice_ids = rec.cash_management_id.invoice_ids.filtered(lambda l: l.state != 'cancel')
                if ext_invoice_ids and rec.cash_management_id.state == 'draft':
                    raise ValidationError(_('You cannot request for fund more than once for beginning balance.'
                                            'Open cash box first before requesting for additional fund.'))

            if not rec.cash_management_id.create_uid.partner_id.property_account_payable_id:
                raise ValidationError(_('Your selected custodian must have an Account Payable'))

            analytic_account_id = False
            if rec.cash_management_id.analytic_account_id:
                analytic_account_id = rec.cash_management_id.analytic_account_id.id
            # Create Supplier Invoice
            inv_ref = "%s_%s" % (rec.cash_management_id.name, len(rec.cash_management_id.requested_fund_ids))
            supplier_inv_vals = {'partner_id': rec.cash_management_id.create_uid.partner_id.id,
                                 # 'account_id': rec.cash_management_id.create_uid.partner_id.property_account_payable_id.id,
                                 'journal_id': rec.cash_management_id._get_journal_id(),
                                 'fund_id': rec.id,
                                 'cash_management_id': rec.cash_management_id.id,
                                 'invoice_date': today.strftime('%Y-%m-%d'),
                                 'ref': inv_ref,
                                 'type': 'in_invoice',
                                 'is_fund': True,
                                 'invoice_line_ids': [(0, 0, {
                                     'account_id': rec.cash_management_id.account_id.id,
                                     'analytic_account_id': analytic_account_id,
                                     'price_unit': rec.amount,
                                     'name': str("[" + rec.cash_management_id.name + "] " + rec.description),
                                     'quantity': 1
                                 })]}
            invoice_id = AccountInvoice.create(supplier_inv_vals)

            rec.invoice_id = invoice_id.id


class ReturnReimburse(models.Model):
    _name = 'return.reimburse'
    _description = 'Return Reimburse'

    RR_TYPE = [('return', 'Return'),
               ('reimburse', 'Reimburse')]

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id,
                                 track_visibility='onchange')
    cash_request_id = fields.Many2one('cash.request', string='Cash Request')
    reference = fields.Char(string='Probationary/Acknowledgment Receipt no.')
    amount = fields.Float()
    date = fields.Date(default=fields.Date.today)
    type = fields.Selection(selection=RR_TYPE, required=True)

    @api.model
    def create(self, vals):
        res = super(ReturnReimburse, self).create(vals)
        CashRequest = self.env['cash.request']
        cr_id = False
        if res.cash_request_id:
            cr_id = res.cash_request_id
        else:
            if self._context.get('default_cash_request_id', False):
                cr_id = CashRequest.browse(self._context['default_cash_request_id'])

        # Cannot perform Return/Reimbursement if in Locked state
        if cr_id.cash_management_id.is_locked:
            raise ValidationError(
                _('You are not allowed to perform For Return/For Reimbursment if the CM reference is locked.'))

        if res.amount <= 0:
            raise ValidationError(_('Amount should be greater than zero'))

        # List View
        if self._context.get('default_amount', False):
            if res.amount > self._context['default_amount']:
                if self._context['default_type'] == 'return':
                    raise ValidationError(_('Amount should not be greater than the amount for return.'))

        # Form View
        if cr_id and self._context.get('return_form', False) and self._context['default_type'] == 'return':
            total_returned = sum(cr_id.return_ids.mapped('amount'))
            if total_returned > cr_id.amount:
                raise ValidationError(_('Amount should not be greater than the amount for return.'))

        if self._context.get('default_type', False) and cr_id:
            if self._context['default_type'] == 'reimburse':
                if res.amount > cr_id.cash_management_id.remaining_fund:
                    raise ValidationError(_('You do not have enough funds.'))

        if cr_id:
            cr_id.write({'reference': res.reference})
        return res

    def write(self, vals):
        for rec in self:
            if rec.cash_request_id:
                rec.cash_request_id.write({'reference': False})
        return super(ReturnReimburse, self).write(vals)

    def unlink(self):
        for rec in self:
            if rec.cash_request_id:
                rec.cash_request_id.write({'reference': False})
        return super(ReturnReimburse, self).unlink()

    def return_reimburse(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cash Request'),
            'res_model': 'cash.request',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {'default_cash_management_id': self.cash_request_id.cash_management_id.id},
            'domain': [('cash_management_id', '=', self.cash_request_id.cash_management_id.id)],
            'nodestroy': True,
        }

# Add back missing functions from Odoo 12
def setup_modifiers(node, field=None, context=None, in_tree_view=False):
    """ Processes node attributes and field descriptors to generate
    the ``modifiers`` node attribute and set it on the provided node.
    Alters its first argument in-place.
    :param node: ``field`` node from an OpenERP view
    :type node: lxml.etree._Element
    :param dict field: field descriptor corresponding to the provided node
    :param dict context: execution context used to evaluate node attributes
    :param bool in_tree_view: triggers the ``column_invisible`` code
                              path (separate from ``invisible``): in
                              tree view there are two levels of
                              invisibility, cell content (a column is
                              present but the cell itself is not
                              displayed) with ``invisible`` and column
                              invisibility (the whole column is
                              hidden) with ``column_invisible``.
    :returns: nothing
    """
    modifiers = {}
    if field is not None:
        transfer_field_to_modifiers(field, modifiers)
    transfer_node_to_modifiers(
        node, modifiers, context=context, in_tree_view=in_tree_view)
    transfer_modifiers_to_node(modifiers, node)
