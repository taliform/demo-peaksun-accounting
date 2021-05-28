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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning
from odoo.addons import decimal_precision as dp
from odoo.addons.base.models.ir_ui_view import transfer_field_to_modifiers, transfer_modifiers_to_node, \
    transfer_node_to_modifiers
from datetime import datetime
from lxml import etree

_LINE_TRANSACTION_TYPES = [
    ('0', 'Purchase of Capital Goods'),
    ('1', 'Purchase of Good Other than Capital Goods'),
    ('2', 'Purchase of Services'),
    ('3', 'Purchases Not Qualified for Input Tax'),
    ('4', 'Others')]


class CashAdvance(models.Model):
    _name = 'cash.advance'
    _description = 'Cash Advance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    CA_STATE = [('draft', 'Draft'),
                ('for_approval', 'For Approval'),
                ('confirm', 'Fund Requested'),
                ('open', 'Open'),
                ('liq_for_approval', 'Liquidation for Approval'),
                ('submit', 'For Validation'),
                ('validated', 'Validated'),
                ('for_payment', 'For Payment'),
                ('close', 'Closed'),
                ('rejected', 'Rejected'),
                ('cancel', 'Cancelled')]

    CA_TYPE = [('ca', 'Cash Advance'),
               ('dr', 'Direct Reimbursement')]

    @api.depends('state')
    def _get_manager_ids(self):
        '''
        @return: Returns list if CA Managers
        '''
        for rec in self:
            manager_ids = self.env['res.users']
            ca_group_id = self.sudo().env['res.groups'].search([
                ('category_id.name', '=', 'Cash Advance'), ('name', '=', 'Manager')])
            if ca_group_id and ca_group_id.users:
                for user_id in ca_group_id.users:
                    manager_ids += user_id
                rec.manager_ids = manager_ids

    def _get_default_account(self):
        '''
        @return: Cash Advance: Returns default debit account of the CA Journal
               Direct Reimbursement: Returns default debit account of the DR Journal
        '''
        ca_type = account_id = False
        if self._context.get('ca_type', False): ca_type = self._context['ca_type']

        if not self.env.user.company_id.dr_journal_id or not self.env.user.company_id.ca_journal_id:
            raise UserError(_('Please configure the journal for Cash Advance.'))

        if ca_type == 'dr':
            account_id = self.env.user.company_id.dr_journal_id.default_debit_account_id.id
        else:
            account_id = self.env.user.company_id.ca_req_journal_id.default_debit_account_id.id
        return account_id

    def _get_default_journal(self):
        '''
        @note: Return default CA Request Journal
        '''
        journal_id = False
        if not self.env.user.company_id.ca_req_journal_id:
            raise UserError(_('Please configure the journal for Cash Advance.'))
        else:
            journal_id = self.env.user.company_id.ca_req_journal_id.id
        return journal_id

    def _get_days_old(self):
        for rec in self:
            if rec.date_start and rec.date_end:
                delta = rec.date_end - rec.date_start
                rec.days_old = delta.days
            elif rec.date_start and not rec.date_end:
                delta = fields.Date.today() - rec.date_start
                rec.days_old = delta.days
            else:
                rec.days_old = 0

            rec.days_old_stored = rec.days_old

    def _check_for_closing(self):
        '''
        @note: Checks if the CA/DR record is for closing.
        '''
        for rec in self:
            rec.is_for_closing = False
            if not rec.for_return and not rec.for_reimbursement and rec.state in ['validated', 'for_payment']:
                rec.is_for_closing = True

    def _check_issued_to(self):
        '''
        @note: Checks if the current user is the <Issued To> indicated in the CA form.
        '''
        for rec in self:
            rec.is_issued_to = False
            if rec.issued_to.id == self._uid:
                rec.is_issued_to = True

    def _get_approvers(self):
        '''
        @note: Get Approvers (Config in Settings)
        '''
        for rec in self:
            rec.approver_ids = self.env['res.users']
            company_id = self.env.user.company_id
            # IF Basic Approval
            if company_id.ca_multiple_approval == 'basic':
                rec.approver_ids += company_id.basic_approver_id
            elif company_id.ca_multiple_approval == 'two':
                if not rec.approved_lvl_1:
                    rec.approver_ids = company_id.basic_approver_id
                else:
                    rec.approver_ids = company_id.second_approver_id

    @api.depends('approver_ids')
    def _check_approver(self):
        '''
        @note: Checks if the current user is an approver.
        '''
        for rec in self:
            rec.is_approver = False
            if self._uid in rec.approver_ids.ids:
                rec.is_approver = True

    def _hide_btn_cancel(self):
        '''
        @note: Hide 'Cancel' button for CA Approver if the Vendor Bill has not been created
        '''
        for rec in self:

            hide_cancel = True
            user_id = self.env.user
            is_ca_user = user_id.has_group('tf_ph_cash_advance.group_cash_advance_user')
            is_ca_accounting = user_id.has_group('tf_ph_cash_advance.group_cash_advance_accountant')

            # Basic Approval
            if not rec.invoice_id and rec.state not in ['for_approval', 'confirm']:
                if is_ca_user or is_ca_accounting:
                    hide_cancel = False
            rec.hide_cancel = hide_cancel


    def _hide_btn_liq(self):
        for rec in self:
            rec.hide_liq_btn = False
            if rec.state == 'cancel' and not rec.cash_transaction_ids:
                rec.hide_liq_btn = True

    def _compute_amount(self):
        '''
        @return: Returns For Return and For Reimbursement Amount
        '''
        for rec in self:
            rec.for_return = False
            rec.for_reimbursement = False
            rec.orig_amount_return = False
            rec.orig_amount_reimburse = False
            if rec.cash_transaction_ids:
                # For Return
                if rec.total_transaction < rec.amount:
                    if rec.amount - rec.total_transaction > 0:
                        rec.orig_amount_return = rec.amount - rec.total_transaction
                    if not rec.total_returned:
                        rec.for_return = rec.amount - rec.total_transaction
                    else:
                        rec.for_return = rec.orig_amount_return - rec.total_returned

                # For Reimbursement
                if rec.total_transaction > rec.amount:
                    if rec.total_transaction - rec.amount > 0:
                        rec.orig_amount_reimburse = rec.total_transaction - rec.amount
                    if not rec.total_reimbursed:
                        rec.for_reimbursement = rec.total_transaction - rec.amount
                    else:
                        rec.for_reimbursement = rec.orig_amount_reimburse - rec.total_reimbursed

    def _compute_total_amount(self):
        '''
        @return: Returns Total Transaction Amount
        '''
        for rec in self:
            rec.total_transaction = False
            rec.total_returned = False
            rec.total_reimbursed = False
            if rec.cash_transaction_ids:
                rec.total_transaction = sum(rec.cash_transaction_ids.mapped('amount'))
            # For Return
            if rec.wo_return_invoice_id:
                invoice_state = rec.wo_return_invoice_id.state
                payment_state = rec.wo_return_invoice_id.invoice_payment_state
                if invoice_state == 'draft':
                    rec.total_returned = rec.wo_return_invoice_id.residual
                elif payment_state == 'paid' and invoice_state == 'posted':
                    rec.total_returned = rec.wo_return_invoice_id.amount_total
                elif payment_state != 'paid' and invoice_state == 'posted':
                    rec.total_returned = abs(rec.wo_return_invoice_id.amount_residual - rec.wo_return_invoice_id.amount_total)

            # For Reimbursement
            if rec.wo_reimburse_invoice_id:
                invoice_state = rec.wo_reimburse_invoice_id.state
                payment_state = rec.wo_reimburse_invoice_id.invoice_payment_state
                if invoice_state == 'draft':
                    rec.total_reimbursed = rec.wo_reimburse_invoice_id.amount_residual
                elif payment_state == 'paid' and invoice_state == 'posted':
                    rec.total_reimbursed = rec.wo_reimburse_invoice_id.amount_total
                elif payment_state != 'paid' and invoice_state == 'posted':
                    rec.total_reimbursed = abs(
                        rec.wo_reimburse_invoice_id.amount_residual - rec.wo_reimburse_invoice_id.amount_total)

    def _get_company_id(self):
        """
        @summary: This will default Company Id on the form by
        getting the attached company_id of the current User. 
        """
        user_id = self.env.uid
        company_id = self.env['res.users'].browse(user_id).company_id.id
        return company_id

    company_id = fields.Many2one('res.company', string='Company', default=_get_company_id, track_visibility='onchange')
    name = fields.Char('Reference', default='Draft Cash Advance', required=True, track_visibility='onchange', copy=False)
    voucher_no = fields.Char('Voucher No.', track_visibility='onchange')
    description = fields.Text(track_visibility='onchange')
    date = fields.Date(default=fields.Date.context_today, track_visibility='onchange')
    ca_type = fields.Selection(CA_TYPE, string='Type')
    state = fields.Selection(CA_STATE, default='draft', string='Status', track_visibility='onchange', copy=False)
    date_start = fields.Date('Date Start', copy=False)
    date_end = fields.Date('Date End', copy=False)
    days_old_stored = fields.Integer('Days', copy=False)
    days_old = fields.Integer('Days Outstanding', compute='_get_days_old',
                              help='Computed as the difference between Cash Request "approval date" and either the "current date" or the Cash Request "closing date."')
    amount = fields.Monetary(track_visibility='onchange')
    total_returned = fields.Monetary('Total Returned', compute='_compute_total_amount')
    total_reimbursed = fields.Monetary('Total Reimbursed', compute='_compute_total_amount')
    for_return = fields.Monetary('For Return', compute='_compute_amount')
    for_reimbursement = fields.Monetary('For Reimbursement', compute='_compute_amount')
    total_transaction = fields.Monetary('Total Transaction', compute='_compute_total_amount')
    orig_amount_return = fields.Monetary('Original Amount to be Returned', compute='_compute_amount')
    orig_amount_reimburse = fields.Monetary('Original Amount to be Reimbursed', compute='_compute_amount')
    new_amount = fields.Monetary('Revised Amount', related='invoice_id.amount_total')
    is_liq_approved = fields.Boolean('Liquidations Approved', copy=False)
    is_liq_invoiced = fields.Boolean('Liquidations (Invoiced)', copy=False)
    is_for_closing = fields.Boolean(compute='_check_for_closing', string='For Closing')
    is_issued_to = fields.Boolean(compute='_check_issued_to')
    hide_cancel = fields.Boolean(compute='_hide_btn_cancel')
    invoice_id = fields.Many2one('account.move', 'Vendor Bill', copy=False)
    invoice_payment_state = fields.Selection(related='invoice_id.invoice_payment_state')
    issued_to = fields.Many2one('res.users', 'Issued To', default=lambda self: self._uid, track_visibility='onchange',
                                copy=False)
    account_id = fields.Many2one('account.account', 'Account', default=_get_default_account,
                                 track_visibility='onchange')
    journal_id = fields.Many2one('account.journal', 'Journal', default=_get_default_journal,
                                 track_visibility='onchange')
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.user.company_id.currency_id,
                                  required=True)
    purchase_tax_id = fields.Many2one('account.tax', 'Purchase Tax', track_visibility='onchange')
    wht_tax_id = fields.Many2one('account.tax', 'Withholding Tax', track_visibility='onchange')
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', track_visibility='onchange')
    wo_return_invoice_id = fields.Many2one('account.move', 'Return Invoice', track_visibility='onchange', copy=False)
    wo_reimburse_invoice_id = fields.Many2one('account.move', 'Reimbursement Invoice', track_visibility='onchange',
                                              copy=False)
    cash_transaction_ids = fields.One2many('cash.advance.transaction', 'cash_advance_id', 'Cash Transaction')
    manager_ids = fields.Many2many('res.users', compute='_get_manager_ids')
    amount_changed = fields.Boolean(copy=False, help='If checked, the amount changed from the invoice amount.')
    hide_liq_btn = fields.Boolean(compute='_hide_btn_liq',
                                  help='If checked, the liquidation smart button should be invisible.')
    note = fields.Text()
    liq_reject_reason = fields.Text('Liquidation Rejection Reason', track_visibility='onchange', copy=False)
    ca_reject_reason = fields.Text('CA Rejection Reason', track_visibility='onchange', copy=False)
    changed_amt_reason = fields.Text('Amount Revision Reason', related='invoice_id.changed_amt_reason')
    is_approver = fields.Boolean(compute='_check_approver')
    approver_ids = fields.Many2many('res.users', compute='_get_approvers')
    approved_lvl_1 = fields.Boolean("Level 1 Approved", copy=False, track_visibility='onchange')

    @api.model
    def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
        res = super(CashAdvance, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                       submenu=submenu)

        user_id = self.env['res.users'].browse(self._uid)
        is_ca_user = user_id.has_group('tf_ph_cash_advance.group_cash_advance_user')
        is_accounting = user_id.has_group('account.group_account_invoice')
        is_ca_accounting = user_id.has_group('tf_ph_cash_advance.group_cash_advance_accountant')

        if view_type == 'form':
            doc2 = etree.XML(res['fields']['cash_transaction_ids']['views']['tree']['arch'])
            o2m_fields = res['fields']['cash_transaction_ids']['views']['tree']['fields']

            # CA Liquidation
            for field in doc2.xpath("//field"):
                # CA Accounting
                # Accounting can only edit the details of the liquidations if For Validation state (except Amount)
                if not is_ca_user:
                    if is_accounting or is_ca_accounting:
                        if field.attrib['name'] == 'or_no':
                            field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                            setup_modifiers(field, o2m_fields[field.attrib['name']])

                        if field.attrib['name'] == 'description':
                            field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                            setup_modifiers(field, o2m_fields[field.attrib['name']])

                        if field.attrib['name'] == 'date':
                            field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                            setup_modifiers(field, o2m_fields[field.attrib['name']])

                        if field.attrib['name'] == 'amount':
                            field.set('readonly', '1')
                            setup_modifiers(field, o2m_fields[field.attrib['name']])

                        if field.attrib['name'] == 'tax_id':
                            field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                            setup_modifiers(field, o2m_fields[field.attrib['name']])

                        if field.attrib['name'] == 'partner_id':
                            field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                            setup_modifiers(field, o2m_fields[field.attrib['name']])

                        if field.attrib['name'] == 'analytic_account_id':
                            field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                            setup_modifiers(field, o2m_fields[field.attrib['name']])

                        if field.attrib['name'] == 'analytic_tag_ids':
                            field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                            setup_modifiers(field, o2m_fields[field.attrib['name']])

                        if field.attrib['name'] == 'expense_category_id':
                            field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                            setup_modifiers(field, o2m_fields[field.attrib['name']])

                        if field.attrib['name'] == 'transaction_type':
                            field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                            setup_modifiers(field, o2m_fields[field.attrib['name']])

            res['fields']['cash_transaction_ids']['views']['tree']['arch'] = etree.tostring(doc2, encoding='unicode')

        return res

    @api.model
    def is_allowed_transition(self, old_state, new_state):
        allowed = [('draft', 'for_approval'),
                   ('draft', 'open'),
                   ('draft', 'rejected'),
                   ('draft', 'cancel'),
                   ('for_approval', 'confirm'),
                   ('for_approval', 'rejected'),
                   ('for_approval', 'draft'),
                   ('for_approval', 'open'),
                   ('for_approval', 'cancel'),
                   ('confirm', 'open'),
                   ('confirm', 'confirm'),  # Amount changed
                   #                    ('confirm', 'for_approval'), #Amount changed for approval
                   ('confirm', 'cancel'),
                   ('open', 'liq_for_approval'),
                   ('open', 'submit'),
                   ('liq_for_approval', 'rejected'),
                   ('liq_for_approval', 'open'),
                   ('liq_for_approval', 'submit'),
                   ('submit', 'open'),
                   ('submit', 'for_payment'),
                   ('submit', 'validated'),
                   ('validated', 'open'),
                   ('validated', 'for_payment'),
                   ('validated', 'close'),
                   ('for_payment', 'close'),
                   ('rejected', 'draft'),
                   ('rejected', 'open'),
                   ('rejected', 'cancel'), ]
        return (old_state, new_state) in allowed

    def button_receive(self):
        for rec in self:
            # Invoice Payment
            invoice_id = rec.invoice_id
            if rec.invoice_payment_state == 'paid' and rec.state == 'confirm':
                if invoice_id.amount_total == rec.amount:
                    rec.write({'journal_id': invoice_id.journal_id.id})
                    rec.change_state('open')

    def change_state(self, new_state):
        for rec in self:
            if rec.is_allowed_transition(rec.state, new_state):
                rec.state = new_state
            else:
                raise ValidationError(_("The state has been already changed. Please refresh the page."))

    def write(self, vals):
        if vals.get('state', False):
            state = vals['state']
            if state == 'open':
                vals['date_start'] = fields.datetime.now()
            elif state == 'close':
                vals['date_end'] = fields.datetime.now()
        return super(CashAdvance, self).write(vals)

    def unlink(self):
        for rec in self:
            if rec.state in ['draft', 'confirm']:
                # Delete invoice if it's in 'Draft' state
                if rec.invoice_id:
                    if rec.invoice_id.state == 'draft':
                        rec.invoice_id.unlink()
                    else:
                        raise UserError(_(
                            'You cannot delete a record that has an open invoice. \nTo proceed, cancel first the '
                            'invoice reference.'))
            else:
                raise UserError(_('You cannot delete record(s) in For Approval, Open, Validation or Close state.'))
        return super(CashAdvance, self).unlink()

    def button_confirm(self):
        '''
        @note: This will send the CA record for approval. Only the CA Manager can approve CA records.
        '''
        current_user = self.env['res.users'].browse(self._uid)
        is_ca_manager = current_user.has_group('tf_ph_cash_advance.group_cash_advance_manager')
        for rec in self:
            # Sequence
            sequence_obj = self.env['ir.sequence']
            rec.update({'name': sequence_obj.next_by_code('cash.advance')})

            if rec.issued_to.id != self.env.uid:
                raise UserError(_(
                    "You are not allowed to send this record for approval. \nPlease inform %s to continue.")
                                % rec.issued_to.name)
            elif is_ca_manager and rec.issued_to == current_user:
                rec.change_state('for_approval')
                rec.approve_button()
            else:
                rec.change_state('for_approval')

            # First Approval
            approver_id = self.env.user.company_id.basic_approver_id
            rec.activity_schedule('tf_ph_cash_advance.mail_act_ca_for_approval',
                                  user_id=approver_id.id,
                                  note=_(
                                      "Approve <a href='#' data-oe-model='%s' data-oe-id='%d'>%s</a> for user "
                                      "<a href='#' data-oe-model='%s' data-oe-id='%s'>%s</a>") % (
                                           rec._name, rec.id, rec.name,
                                           rec.issued_to._name, rec.issued_to.id, rec.issued_to.name))

    def button_dr_confirm(self):
        # Direct Reimbursement
        for rec in self:
            # Sequence
            sequence_obj = self.env['ir.sequence']
            rec.update({'name': sequence_obj.next_by_code('direct.reimbursement')})
            rec.change_state('open')

    def process_approval(self):
        AccountInvoice = self.env['account.move']
        today = fields.Date.context_today(self)

        for rec in self:
            if rec.state in ['draft', 'for_approval']:
                if not rec.invoice_id:
                    partner_id = rec.issued_to.partner_id
                    if not partner_id.property_account_payable_id:
                        raise ValidationError(_('The selected employee must have an Account Payable.'))

                    analytic_id = rec.analytic_account_id and rec.analytic_account_id.id or False
                    # Journals
                    inv_line_vals = {
                        'name': "[" + str(rec.name) + "] " + str(rec.description and rec.description or "N/A"),
                        'account_id': rec.account_id.id,
                        'journal_id': rec.journal_id.id,
                        'analytic_account_id': analytic_id,
                        'price_unit': rec.amount,
                        'quantity': 1,
                    }
                    # Vendor Bills
                    inv_vals = {
                        'partner_id': partner_id.id,
                        'journal_id': rec.journal_id.id,
                        'cash_advance_id': rec.id,
                        'invoice_date': today.strftime('%Y-%m-%d'),
                        'invoice_line_ids': [(0, 0, inv_line_vals)],
                        'date': today.strftime('%Y-%m-%d'),
                        'name': rec.name,
                        'type': 'in_invoice',
                        'is_fund': True,
                    }
                    invoice_id = AccountInvoice.create(inv_vals)

                    rec.write({'invoice_id': invoice_id.id})
                    rec.change_state('confirm')
                else:
                    if rec.amount == rec.invoice_id.amount_total:
                        # Approval for changed amount
                        rec.change_state('open')

            # CA Liquidation For Approval
            elif rec.state == 'liq_for_approval':
                if not rec.cash_transaction_ids:
                    raise ValidationError(_(
                        'There is no CA Liquidation to submit.\nCreate at least one CA Liquidation record to proceed.'))
                else:
                    for cat_id in rec.cash_transaction_ids:
                        cat_id.write({'state': 'submit'})
                    rec.change_state('submit')
                rec.write({'is_liq_approved': True})

    def approve_button(self):
        '''
        @note: This will create a vendor invoice (Fund Request)
        '''

        for rec in self:
            # CA For Approval
            approval_type = rec.company_id.ca_multiple_approval
            if approval_type == 'basic':
                rec.process_approval()
            elif approval_type == 'two':
                if not rec.approved_lvl_1:
                    rec.approved_lvl_1 = True
                    approver_id = self.env.user.company_id.second_approver_id
                    if not approver_id:
                        raise ValidationError("The second level approver hasn't been configured in the "
                                              "Accounting General Settings")
                    rec.activity_schedule('tf_ph_cash_advance.mail_act_ca_for_approval',
                                          user_id=approver_id.id,
                                          note=_(
                                              "Approve <a href='#' data-oe-model='%s' data-oe-id='%d'>%s</a> for user "
                                              "<a href='#' data-oe-model='%s' data-oe-id='%s'>%s</a>") % (
                                                   rec._name, rec.id, rec.name,
                                                   rec.issued_to._name, rec.issued_to.id, rec.issued_to.name))
                else:
                    rec.process_approval()

        return {'type': 'ir.actions.client', 'tag': 'reload'}


    def decline_button(self):
        for rec in self:
            view = self.env.ref('tf_ph_cash_advance.cash_advance_reject_form')
            name = False
            if rec.state in ['draft', 'for_approval']:
                name = 'Reject CA'
            elif rec.state == 'liq_for_approval':
                name = 'Reject Liquidations'
            return {
                'name': _(name),
                'type': 'ir.actions.act_window',
                'res_model': 'cash.advance.reject',
                'view_mode': 'form',
                'view_id': view.id,
                'target': 'new',
                'context': {'default_cash_advance_id': rec.id},
            }

    def button_liq_approval(self):
        '''
        @note: This will transition the state from 'Open' to 'Liquidation For Approval'
        '''
        for rec in self:
            is_ca_manager = self.env['res.users'].browse(self._uid).has_group(
                'tf_ph_cash_advance.group_cash_advance_manager')
            if not rec.cash_transaction_ids:
                raise UserError(_("There are no liquidations to be approved."))
            elif is_ca_manager:
                rec.change_state('submit')
                rec.cash_transaction_ids.write({'state': 'submit'})
            else:
                rec.change_state('liq_for_approval')
                rec.cash_transaction_ids.write({'state': 'for_approval'})

                # Basic Approval
                if self.env.user.company_id.ca_multiple_approval == 'basic':
                    approver_id = self.env.user.company_id.basic_approver_id
                    if rec.ca_type == 'ca':
                        rec.activity_schedule('tf_ph_cash_advance.mail_act_ca_liq_for_approval',
                                              user_id=approver_id.id,
                                              note=_(
                                                  "Approve <a href='#' data-oe-model='%s' data-oe-id='%d'>%s</a> for user <a href='#' data-oe-model='%s' data-oe-id='%s'>%s</a>") % (
                                                       rec._name, rec.id, rec.name,
                                                       rec.issued_to._name, rec.issued_to.id, rec.issued_to.name))
                    elif rec.ca_type == 'dr':
                        rec.activity_schedule('tf_ph_cash_advance.mail_act_dr_liq_for_approval',
                                              user_id=approver_id.id,
                                              note=_(
                                                  "Approve <a href='#' data-oe-model='%s' data-oe-id='%d'>%s</a> for user <a href='#' data-oe-model='%s' data-oe-id='%s'>%s</a>") % (
                                                       rec._name, rec.id, rec.name,
                                                       rec.issued_to._name, rec.issued_to.id, rec.issued_to.name))

    def button_validate(self):
        view = self.env.ref('tf_ph_cash_advance.cash_advance_validate_form')
        return {
            'name': _('Validate Cash Advance'),
            'type': 'ir.actions.act_window',
            'res_model': 'cash.advance.validate',
            'view_mode': 'form',
            'view_id': view.id,
            'target': 'new',
            'context': {'default_cash_advance_id': self.id, 'default_account_date': fields.Date.context_today(self)},
        }

    def action_validate(self, account_date):
        inv_obj = self.env['account.move']
        ap_obj = self.env['account.payment']

        for rec in self:
            # Validation
            if not rec.issued_to.partner_id.property_account_payable_id:
                raise ValidationError(_('%s has no Account Payable.') % rec.issued_to.partner_id.name)

            if rec.state == 'validated':
                raise UserError(_('%s has been validated already.') % rec.name)
            if rec.for_reimbursement > 0 and rec.amount > 0 and rec.wo_reimburse_invoice_id:
                raise UserError(_('%s has been validated already.') % rec.name)

            if rec.for_return > 0 and rec.amount > 0 and rec.wo_return_invoice_id:
                raise UserError(_('%s has been validated already.') % rec.name)

            #Init
            partner_ids = rec.cash_transaction_ids.mapped('partner_id')
            inv_vals = {
                'date': account_date,
                'invoice_date': account_date,
                'currency_id': rec.currency_id.id,
                'invoice_line_ids': [],
                'cash_advance_id': rec.id,
                'ref': "Cash Advance: %s" % rec.name,
            }

            # LIQUIDATION
            if not rec.is_liq_invoiced:
                journal_id = self.env.user.company_id.ca_inv_journal_id.id
                if not journal_id:
                    raise ValidationError("CA Liquidation Invoice Journal hasn't been configured in the Accounting "
                                          "Settings")
                # Create invoice for CA Liquidations (grouped by partner)
                for partner_id in partner_ids:
                    # Validate AP
                    if not partner_id.property_account_payable_id:
                        raise ValidationError('%s has no configured Account Payable.' % partner_id.name)
                    # Filter Liquidations per Partner
                    cat_ids = rec.cash_transaction_ids.filtered(
                        lambda l: l.partner_id == partner_id and l.state == 'submit')
                    liq_vals = inv_vals.copy()
                    # Initialize Invoice Vals
                    liq_vals.update({
                        'journal_id': journal_id,
                        'is_liquidation': True,
                        'partner_id': partner_id,
                        'type': 'in_invoice'
                    })
                    # Create Invoice Lines per Liquidation
                    for cat_id in cat_ids:
                        categ_id = cat_id.expense_category_id
                        name = "[%s]" % categ_id.name
                        if cat_id.or_no:
                            name += " - %s" % cat_id.or_no
                        if cat_id.description:
                            name += " - %s" % cat_id.description

                        liq_vals['invoice_line_ids'].append((0, 0, {
                            'account_id': categ_id.account_id.id,
                            'analytic_account_id': cat_id.analytic_account_id.id,
                            'journal_id': journal_id,
                            'name': name,
                            'cash_advance_transaction_id': cat_id.id,
                            'price_unit': cat_id.amount,
                            'quantity': 1,
                            'transaction_type': cat_id.transaction_type,
                            'tax_ids': [(6, 0, cat_id.tax_id.ids)]
                        }))

                    # Create Invoice
                    inv_id = inv_obj.create(liq_vals)
                    # Post Invoice
                    inv_id.action_post()
                    # Create Payment
                    payment_journal = False
                    if rec.ca_type == 'ca':
                        payment_journal = self.env.user.company_id.ca_journal_id.id
                    # For Direct Reimbursement
                    elif rec.ca_type == 'dr':
                        payment_journal = self.env.user.company_id.dr_journal_id.id

                    ap_vals = {
                        'payment_type': 'outbound',
                        # 'payment_method_type': 'adjustment',
                        'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                        'payment_reference': inv_id.name,
                        'partner_type': 'supplier',
                        'partner_id': self.env['res.partner']._find_accounting_partner(inv_id.partner_id).id,
                        'amount': inv_id.amount_residual,
                        'currency_id': inv_id.currency_id.id,
                        'payment_date': fields.Date.context_today(self),
                        'journal_id': payment_journal,
                        'invoice_ids': [(6, 0, inv_id.ids)],
                    }

                    payment_id = ap_obj.create(ap_vals)
                    payment_id.post()
                # Mark as liquidated
                rec.write({'is_liq_invoiced': True})

            # Validate Liquidations
            rec.cash_transaction_ids.write({'state': 'validated'})

            # For Direct Reimbursement
            if rec.ca_type == 'dr':
                invoice_id = rec.create_vendor_bill('dr', rec.analytic_account_id, account_date)
                invoice_id.action_post()
                rec.write({'wo_reimburse_invoice_id': invoice_id.id})
                rec.change_state('for_payment')

            # For Reimbursement
            # Create Supplier Invoice
            elif rec.for_reimbursement > 0 and rec.amount > 0:
                invoice_id = rec.create_vendor_bill('reimburse', rec.analytic_account_id, account_date)
                invoice_id.action_post()

                rec.write({'wo_reimburse_invoice_id': invoice_id.id})
                rec.change_state('for_payment')

            # For Return
            # Create Customer Invoice
            elif rec.for_return > 0 and rec.amount > 0:
                invoice_id = rec.create_vendor_bill('return', rec.analytic_account_id, account_date)
                invoice_id.action_post()

                rec.write({'wo_return_invoice_id': invoice_id.id})
                rec.change_state('for_payment')

            if not rec.for_reimbursement and not rec.for_return:
                rec.change_state('validated')

    def create_vendor_bill(self, tag, analytic_id, account_date):
        '''
        @note: Creates Vendor Bill upon validation (Liquidation Invoice, Invoice for reimburesement and for return)
        '''
        AccountInvoice = self.env['account.move']
        invoice_tag = False
        is_return = is_reimburse = False
        journal_id = False

        # Create Vendor Bill for reimbursement and for return
        if tag in ['dr', 'return', 'reimburse']:
            analytic_id = self.analytic_account_id and self.analytic_account_id.id or False
            line_account_id = self.env.user.company_id.dr_journal_id.default_debit_account_id
            ref_invoice = self.voucher_no or self.name
            partner_id = self.issued_to.partner_id.id
            is_liquidation = False
            inv_type = 'in_invoice'

            if tag == 'dr':
                amount = sum(self.cash_transaction_ids.mapped('amount'))
                name = 'For reimbursement: ' + str(self.name)
                ref_invoice = 'DR [' + self.name + ']'
                journal_id = self.env.user.company_id.dr_journal_id
                if not journal_id:
                    raise ValidationError("CA DR Journal Journal hasn't been configured in the Accounting Settings")
                else:
                    journal_id = journal_id.id

            elif tag == 'reimburse':
                name = 'For reimbursement: ' + str(self.name)
                ref_invoice = 'REIMB [' + self.name + ']'
                amount = self.for_reimbursement
                line_account_id = self.env.user.company_id.ca_journal_id.default_debit_account_id
                invoice_tag = 'reimburse'
                is_reimburse = True
                journal_id = self.env.user.company_id.ca_reimburse_journal_id
                if not journal_id:
                    raise ValidationError("CA Reimbursements Journal hasn't been configured in the Accounting Settings")
                else:
                    journal_id = journal_id.id

            elif tag == 'return':
                name = 'For return: ' + str(self.name)
                ref_invoice = 'RET [' + self.name + ']'
                amount = self.for_return
                line_account_id = self.env.user.company_id.ca_journal_id.default_debit_account_id
                # Customer Invoice
                inv_type = 'out_invoice'
                invoice_tag = 'return'
                is_return = True
                journal_id = self.env.user.company_id.ca_return_journal_id
                if not journal_id:
                    raise ValidationError("CA Returns Journal hasn't been configured in the Accounting Settings")
                else:
                    journal_id = journal_id.id

        inv_line_vals = {
            'journal_id': journal_id,
            'analytic_account_id': analytic_id,
            'account_id': line_account_id.id,
            'cash_advance_id': self.id,
            'name': name,
            'price_unit': amount,
            'quantity': 1}

        inv_line_vals.update(self.line_val_post_process(line_account_id))

        inv_vals = {
            'date': account_date,
            'invoice_date': account_date,
            'currency_id': self.currency_id.id,
            'journal_id': journal_id,
            'is_liquidation': is_liquidation,
            'is_return': is_return,
            'is_reimburse': is_reimburse,
            'invoice_line_ids': [(0, 0, inv_line_vals)],
            'partner_id': partner_id,
            'cash_advance_id': self.id,
            'ca_invoice_tag': invoice_tag,
            'type': inv_type,
            'ref': ref_invoice}

        inv_vals.update(self.inv_val_post_process())
        invoice_id = AccountInvoice.create(inv_vals)
        return invoice_id

    def line_val_post_process(self):
        # This function is inherited to add additional values to the inv line vals dictionary
        return {}

    def inv_val_post_process(self):
        # This function is inherited to add additional values to the inv vals dictionary
        return {}

    def button_reopen(self):
        for rec in self:
            if rec.issued_to.id != self.env.uid and rec.state != 'submit':
                raise UserError(_(
                    "You are not allowed to confirm this record.\nPlease inform %s to continue.") % rec.issued_to.name)
            else:
                if rec.cash_transaction_ids:
                    for cat_id in rec.cash_transaction_ids:
                        cat_id.write({'state': 'draft'})

                rec.write({'is_liq_approved': False})
                rec.change_state('open')

    def button_cancel(self):
        for rec in self:
            if rec.invoice_id:
                view = self.env.ref('tf_ph_cash_advance.cash_advance_cancel_form')
                return {
                    'name': _('Cancel Cash Advance'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'cash.advance.cancel',
                    'view_mode': 'form',
                    'view_id': view.id,
                    'target': 'new',
                    'context': {'default_cash_advance_id': rec.id},
                }
            else:
                rec.write({'state': 'cancel'})

    def button_revise(self):
        view = self.env.ref('tf_ph_cash_advance.cash_advance_revise_form')
        return {
            'name': _('Receive Revised Cash Advance'),
            'type': 'ir.actions.act_window',
            'res_model': 'cash.advance.revise',
            'view_mode': 'form',
            'view_id': view.id,
            'target': 'new',
            'context': {'default_cash_advance_id': self.id, 'default_amount': self.new_amount},
        }

    def button_close(self):
        '''
        @note: Check if there are pending invoices to be paid.
        '''
        for rec in self:
            if rec.wo_return_invoice_id and rec.wo_return_invoice_id.invoice_payment_state != 'paid':
                raise Warning(_('The invoice for Return should be paid first to close this cash advance record.'))
            elif rec.wo_reimburse_invoice_id and rec.wo_reimburse_invoice_id.invoice_payment_state != 'paid':
                raise Warning(
                    _('The invoice for Reimbursement should be paid first to close this cash advance record.'))
            else:
                rec.write({'state': 'close'})

    def view_cash_advance_transaction_action(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Liquidations'),
            'res_model': 'cash.advance.transaction',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {'default_cash_advance_id': self.id},
            'domain': [('cash_advance_id', '=', self.id)],
        }

    def view_ca_transaction_invoice_action(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Liquidation Invoices'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {'default_cash_advance_id': self.id},
            'domain': [('cash_advance_id', '=', self.id),
                       ('is_liquidation', '=', True),
                       ('type', '=', 'in_invoice')],
        }


class CashAdvanceTransaction(models.Model):
    _name = 'cash.advance.transaction'
    _description = "CA Liquidation"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    CAT_STATE = [('draft', 'Draft'),
                 ('for_approval', 'For Approval'),
                 ('submit', 'For Validation'),
                 ('validated', 'Validated'),
                 ('for_payment', 'For Payment'),
                 ('close', 'Closed'),
                 ('cancel', 'Cancelled')]

    @api.constrains('amount', 'tax_id')
    def _check_amount(self):
        for rec in self:
            if rec.tax_id and rec.partner_id:
                if not rec.partner_id.vat:
                    raise ValidationError(_('The selected Partner should have a TIN.'))

    def _get_company_id(self):
        """
        @summary: This will default Company Id on the form by
        getting the attached company_id of the current User. 
        """
        user_id = self.env.uid
        company_id = self.env['res.users'].browse(user_id).company_id.id
        return company_id

    company_id = fields.Many2one('res.company', string='Company', default=_get_company_id, track_visibility='onchange')
    name = fields.Char('Reference', default='Draft CA Liquidation', required=True, track_visibility='onchange')
    or_no = fields.Char('OR No.', track_visibility='onchange')
    description = fields.Text(track_visibility='onchange')
    date = fields.Date(default=fields.Date.context_today, track_visibility='onchange', copy=False)
    amount = fields.Float('Amount', digits=dp.get_precision('Account'), track_visibility='onchange')
    state = fields.Selection(CAT_STATE, default='draft', string='Status', track_visibility='onchange')
    transaction_type = fields.Selection(_LINE_TRANSACTION_TYPES, string='Transaction Type', track_visibility='onchange')
    ct_cash_advance_state = fields.Selection(related='cash_advance_id.state', string='Cash Advance State', store=True)
    tax_id = fields.Many2one('account.tax', 'Tax', track_visibility='onchange')
    issued_to = fields.Many2one('res.users', 'Issued To', related='cash_advance_id.issued_to', store=True,
                                track_visibility='onchange')
    account_id = fields.Many2one('account.account', related='expense_category_id.account_id', string='Account',
                                 track_visibility='onchange')
    partner_id = fields.Many2one('res.partner', 'Partner', domain=[('is_company', '=', True)],
                                 track_visibility='onchange')
    cash_advance_id = fields.Many2one('cash.advance', 'Cash Advance', track_visibility='onchange', copy=False)
    expense_category_id = fields.Many2one('expense.category', 'Expense Category', track_visibility='onchange')
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', track_visibility='onchange')
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.user.company_id.currency_id,
                                  required=True)
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags', track_visibility='onchange')

    @api.model
    def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
        res = super(CashAdvanceTransaction, self).fields_view_get(view_id=view_id, view_type=view_type,
                                                                  toolbar=toolbar, submenu=submenu)

        doc = etree.XML(res['arch'])
        user_id = self.env['res.users'].browse(self._uid)
        ca_id = self._context.get('default_cash_advance_id', False)
        if ca_id:
            ca_id = self.env['cash.advance'].browse(ca_id)
        is_ca_user = user_id.has_group('tf_ph_cash_advance.group_cash_advance_user')
        is_accounting = user_id.has_group('account.group_account_invoice')
        is_ca_accounting = user_id.has_group('tf_ph_cash_advance.group_cash_advance_accountant')

        if view_type in ['tree', 'form']:
            # CA Accounting
            # Accounting can only edit the details of the liquidations if For Validation state (except Amount)
            if ca_id and user_id != ca_id.issued_to:
                if is_accounting or is_ca_user or is_ca_accounting:
                    for field in doc.xpath("//field[@name='cash_advance_id']"):
                        field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                        setup_modifiers(field, res['fields']['cash_advance_id'])

                    for field in doc.xpath("//field[@name='or_no']"):
                        field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                        setup_modifiers(field, res['fields']['or_no'])

                    for field in doc.xpath("//field[@name='description']"):
                        field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                        setup_modifiers(field, res['fields']['description'])

                    for field in doc.xpath("//field[@name='date']"):
                        field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                        setup_modifiers(field, res['fields']['date'])

                    for field in doc.xpath("//field[@name='amount']"):
                        field.set('readonly', '1')
                        setup_modifiers(field, res['fields']['amount'])

                    for field in doc.xpath("//field[@name='tax_id']"):
                        field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                        setup_modifiers(field, res['fields']['tax_id'])

                    for field in doc.xpath("//field[@name='partner_id']"):
                        field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                        setup_modifiers(field, res['fields']['partner_id'])

                    for field in doc.xpath("//field[@name='analytic_account_id']"):
                        field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                        setup_modifiers(field, res['fields']['analytic_account_id'])

                    for field in doc.xpath("//field[@name='analytic_tag_ids']"):
                        field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                        setup_modifiers(field, res['fields']['analytic_tag_ids'])

                    for field in doc.xpath("//field[@name='expense_category_id']"):
                        field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                        setup_modifiers(field, res['fields']['expense_category_id'])

                    for field in doc.xpath("//field[@name='transaction_type']"):
                        field.set('attrs', "{'readonly': [('state','!=','submit')]}")
                        setup_modifiers(field, res['fields']['transaction_type'])

            res['arch'] = etree.tostring(doc)
        return res

    @api.model
    def create(self, vals):
        res = super(CashAdvanceTransaction, self).create(vals)
        sequence_obj = self.env['ir.sequence']

        # Restrict to add new transactions
        if res.cash_advance_id.is_liq_approved:
            raise UserError(_(
                'You are not allowed to add transactions. The liquidations of the referenced cash advance have been approved.'))

        if res.cash_advance_id.cash_transaction_ids:
            cat_id = res.cash_advance_id.cash_transaction_ids[-1]
            if cat_id.state == 'for_approval':
                raise UserError(
                    _('You are not allowed to add transactions. The existing liquidations are still for approval.'))

        if res.cash_advance_id.issued_to.id != self._uid:
            raise UserError(_(
                'You are not allowed to add transactions. Please inform Please inform %s to continue.') % res.cash_advance_id.issued_to.name)

        if res.cash_advance_id.state in ['validated', 'for_payment', 'close', 'cancel']:
            raise UserError(_('You cannot add transactions.'))

        if res.cash_advance_id.ca_type == 'ca':
            res.update({'name': sequence_obj.next_by_code('cash.advance.transaction')})
        elif res.cash_advance_id.ca_type == 'dr':
            res.update({'name': sequence_obj.next_by_code('direct.reimbursement.transaction')})
        return res

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('You cannot delete a transaction that is not in Draft state.'))

            if rec.cash_advance_id.issued_to.id != self._uid:
                raise UserError(_('You are not allowed to delete this record.'))

        return super(CashAdvanceTransaction, self).unlink()

    @api.onchange('cash_advance_id', 'expense_category_id')
    def onchange_cash_advance(self):
        if self.cash_advance_id:
            if self.cash_advance_id.purchase_tax_id:
                self.tax_id = self.cash_advance_id.purchase_tax_id.id
            if self.cash_advance_id.analytic_account_id:
                self.analytic_account_id = self.cash_advance_id.analytic_account_id.id

        if self.expense_category_id:
            self.account_id = self.expense_category_id.account_id.id
            if self.tax_id:
                self.transaction_type = self.expense_category_id.transaction_type

    @api.onchange('tax_id')
    def onchange_tax_id(self):
        if not self.tax_id:
            self.transaction_type = False
        elif self.tax_id and self.expense_category_id:
            self.transaction_type = self.expense_category_id.transaction_type


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
