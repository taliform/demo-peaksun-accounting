# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Allen Guarnes <allen@taliform.com>
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
import json

from lxml import etree

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_CREDIT_TERM_MEASURES = [
    ('days', 'Days'),
    ('months', 'Months'),
    ('years', 'Years')
]

_STATES = [
    ('draft', 'Draft'),
    ('confirmed', 'Confirmed'),
    ('investigation', 'Investigation'),
    ('approval', 'Approval'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('cancelled', 'Cancelled')
]


class CreditApplication(models.Model):
    _name = 'credit.application'
    _description = 'Credit Application'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Name', default='Draft Credit Application', copy=False, track_visibility='onchange')
    partner_id = fields.Many2one('res.partner', 'Registered Name')
    trade_name = fields.Char(related='partner_id.trade_name')
    vat = fields.Char(related='partner_id.vat')
    year_business_started = fields.Char(related='partner_id.year_business_started')
    telephone = fields.Char(related='partner_id.phone', string='Telephone')
    fax = fields.Char(related='partner_id.fax')
    email = fields.Char(related='partner_id.email')
    nature_id = fields.Many2one(related='partner_id.nature_id')
    volume = fields.Float('# of Bags / Mo.')
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.user.company_id.currency_id)
    requested_credit_line = fields.Monetary('Requested Credit Line', track_visibility='onchange')
    requested_credit_term = fields.Integer('Requested Credit Term', track_visibility='onchange')
    requested_credit_term_measure = fields.Selection(_CREDIT_TERM_MEASURES,
                                                     'Requested Credit Term Measure', default='days',
                                                     track_visibility='onchange')
    approved_credit_line = fields.Monetary('Approved Credit Line', copy=False, track_visibility='onchange')
    approved_credit_term = fields.Integer('Approved Credit Term', copy=False, track_visibility='onchange')
    approved_credit_term_measure = fields.Selection(_CREDIT_TERM_MEASURES,
                                                    'Approved Credit Term Measure', default='days', copy=False,
                                                    track_visibility='onchange')
    application_date = fields.Date('Date of Application', default=fields.Date.context_today)
    user_id = fields.Many2one('res.partner', 'Account Officer')
    approver_ids = fields.One2many('credit.application.approver', 'credit_application_id', 'Approvers')
    officer_ids = fields.Many2many('res.partner', 'credit_application_officers', string='Company Officers')
    signatory_ids = fields.Many2many('res.partner', 'credit_application_signatories', string='Check Signatories')
    project_ids = fields.Many2many('res.partner.project', string='Major Projects')
    loan_ids = fields.One2many('credit.application.loan', 'credit_application_id', 'Outstanding Loans')
    trade_reference_ids = fields.One2many('credit.application.reference.trade',
                                          'credit_application_id', 'Trade References')
    bank_reference_ids = fields.One2many('credit.application.reference.bank',
                                         'credit_application_id', 'Bank References')
    approver_ids = fields.One2many('credit.application.approver', 'credit_application_id', 'Approvers')
    state = fields.Selection(_STATES, 'State', default='draft', track_visibility='onchange', copy=False)

    collection_day = fields.Selection(related='partner_id.collection_day')
    collection_time = fields.Float(related='partner_id.collection_time')
    collection_address = fields.Text(related='partner_id.collection_address')
    mode_of_payment = fields.Selection(related='partner_id.mode_of_payment')

    latest_gis_for_corporations = fields.Boolean('Latest GIS for Corporations')
    updated_financial_statements = fields.Boolean('Updated Financial Statements (3 Years)')
    bir_form_2303 = fields.Boolean('BIR Form 2303')
    authorization_letter_for_bank_references = fields.Boolean('Authorization Letter for Bank References')

    authorized_person_id = fields.Many2one('res.partner', 'Authorized Person', track_visibility='onchange')
    authorized_designation = fields.Char('Designation', track_visibility='onchange')
    authorized_signature = fields.Binary('Authorized Signature', track_visibility='onchange')

    def write(self, vals):
        if vals.get('approved_credit_line', False) \
                or vals.get('approved_credit_term', False) \
                or vals.get('approved_credit_term_measure', False):
            if not self.env.user.has_group('tf_peec_credit_application.group_credit_application_approver'):
                raise ValidationError(_('You are not allowed to modify the Approved Credit Line and Terms.'))
        return super(CreditApplication, self).write(vals)

    @api.model
    def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
        '''
        @note: Removes the domain filter on Issued To field if the current user is a Custodian.
        '''
        res = super(CreditApplication, self).fields_view_get(view_id=view_id, view_type=view_type,
                                                             toolbar=toolbar, submenu=submenu)
        is_approver = self.env.user.has_group('tf_peec_credit_application.group_credit_application_approver')
        if view_type == 'form' and not is_approver:
            doc = etree.XML(res['arch'])
            approved_credit_line = doc.xpath("//field[@name='approved_credit_line']")[0]
            approved_credit_line.set('readonly', '1')
            modifiers = json.loads(approved_credit_line.get("modifiers"))
            modifiers['readonly'] = True
            approved_credit_line.set("modifiers", json.dumps(modifiers))

            approved_credit_term = doc.xpath("//field[@name='approved_credit_term']")[0]
            approved_credit_term.set('readonly', '1')
            modifiers = json.loads(approved_credit_term.get("modifiers"))
            modifiers['readonly'] = True
            approved_credit_term.set("modifiers", json.dumps(modifiers))

            approved_credit_term_measure = doc.xpath("//field[@name='approved_credit_term_measure']")[0]
            approved_credit_term_measure.set('readonly', '1')
            modifiers = json.loads(approved_credit_term_measure.get("modifiers"))
            modifiers['readonly'] = True
            approved_credit_term_measure.set("modifiers", json.dumps(modifiers))

            res['arch'] = etree.tostring(doc)
        return res

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for credit_application in self:
            if credit_application.partner_id:
                officers = credit_application.partner_id.child_ids.filtered(lambda c: c.is_company_officer)
                signatories = credit_application.partner_id.child_ids.filtered(lambda c: c.is_check_signatory)
                projects = credit_application.partner_id.project_ids
                credit_application.officer_ids = [(6, 0, officers.ids)]
                credit_application.signatory_ids = [(6, 0, signatories.ids)]
                credit_application.project_ids = [(6, 0, projects.ids)]

    @api.model
    def is_allowed_transition(self, old_state, new_state):
        allowed = [
            ('draft', 'confirmed'),
            ('confirmed', 'investigation'),
            ('investigation', 'approval'),
            ('approval', 'approved'),
            ('approval', 'rejected'),
            ('confirmed', 'cancelled'),
            ('investigation', 'cancelled'),
            ('approval', 'cancelled'),
        ]
        return (old_state, new_state) in allowed

    def change_state(self, new_state):
        for rec in self:
            if rec.is_allowed_transition(rec.state, new_state):
                rec.state = new_state
            else:
                raise ValidationError(_("The state has been already changed. Please refresh the page."))

    def action_confirm(self):
        for rec in self:
            rec.change_state('confirmed')
            rec.name = self.env['ir.sequence'].next_by_code('credit.application') or _('New')

    def action_for_investigation(self):
        for rec in self:
            rec.change_state('investigation')

    def action_for_approval(self):
        for rec in self:
            rec.change_state('approval')

            vals = []
            for approver in self.env['credit.application.approval.configuration'].search([]):
                vals.append((0, 0, {'user_id': approver.user_id.id, 'state': 'pending'}))
                rec.activity_schedule('tf_peec_credit_application.mail_act_capp_approval', user_id=approver.user_id.id)

            rec.write({'approver_ids': vals})

    def approval_process(self, action):
        self.ensure_one()
        current_user = self.env.user
        for approver in self.approver_ids:
            if current_user == approver.user_id and approver.state == 'pending':
                approver.state = action
                return True
        return False

    def action_approve(self):
        for rec in self:
            if rec.approval_process('approved'):
                rec.activity_feedback(['tf_peec_credit_application.mail_act_capp_approval'], self.env.uid)
                if 'pending' not in rec.approver_ids.mapped('state'):
                    rec.change_state('approved')

    def action_reject(self):
        for rec in self:
            if rec.approval_process('rejected'):
                rec.activity_unlink(['tf_peec_credit_application.mail_act_capp_approval'], self.env.uid)
                rec.change_state('rejected')

    def action_cancel(self):
        for rec in self:
            rec.approver_ids.write({'state': 'cancelled'})
            rec.change_state('cancelled')
            rec.activity_unlink(['tf_peec_credit_application.mail_act_capp_approval'])


class CreditApplicationApprover(models.Model):
    _name = 'credit.application.approver'
    _description = 'Credit Application - Approver'

    credit_application_id = fields.Many2one('credit.application', 'Credit Application')
    user_id = fields.Many2one('res.users', 'Approver', required=True)
    state = fields.Selection(
        [('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')],
        'State',
        default='pending', required=True)


class ApprovalConfiguration(models.Model):
    _name = 'credit.application.approval.configuration'
    _description = 'Credit Application - Approval Configuration'

    user_id = fields.Many2one('res.users', 'Approver', required=True)


class OutstandingLoan(models.Model):
    _name = 'credit.application.loan'
    _description = 'Credit Application - Oustanding Loan'

    credit_application_id = fields.Many2one('credit.application', 'Credit Application')
    name = fields.Char('Name of Creditor', required=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.user.company_id.currency_id)
    outstanding_loan_amount = fields.Monetary('Outstanding Loan Amount')
    nature_of_loan = fields.Char('Nature of Loan')
    collateral = fields.Char('Collateral')


class TradeReference(models.Model):
    _name = 'credit.application.reference.trade'
    _description = 'Credit Application - Trade Reference'

    credit_application_id = fields.Many2one('credit.application', 'Credit Application')
    name = fields.Char('Name of Supplier', required=True)
    contact_person = fields.Char('Contact Person', help='Indicates the contact person of the supplier', required=True)
    position = fields.Char('Position', help='Indicates the position of the contact person', required=True)
    telephone_no = fields.Char('Telephone No.', help='Indicates the telephone number of the contact person',
                               required=True)
    email_address = fields.Char('Email Address', help='Indicates the email address of the contact person',
                                required=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.user.company_id.currency_id)
    approved_credit_line = fields.Monetary('Approved Credit Line',
                                           help='The amount of credit approved to the customer by the supplier')
    approved_credit_term = fields.Integer('Approved Credit Term',
                                          help='Indicates the length of approved credit term, '
                                               'as indicated by the Approved Credit Term Measure')
    approved_credit_term_measure = fields.Selection(_CREDIT_TERM_MEASURES,
                                                    'Approved Credit Term Measure', default='days')
    approved_credit_term_display = fields.Char('Approved Credit Term (Display)',
                                               compute="_compute_approved_credit_term_display")
    items_purchased = fields.Text('Items Purchased', help='Indicates the items purchased from the supplier')
    relationship_length = fields.Integer('Length of Relationship', help='Indicates the length of relationship in years')
    has_bounced_cheques = fields.Boolean('Bounced Cheques', help='Indicates if there are any bounced cheques')
    has_stop_payments = fields.Boolean('Stop Payments', help='Indicates if there are any stop payments')
    has_daif = fields.Boolean('DAIF', help='Indicates if there are any DAIF')
    has_delayed_payments = fields.Boolean('Delayed Payments', help='Indicates if there are any delayed payments')
    bounced_cheques_count = fields.Integer('No. of Bounced Cheques', help='Indicates the number of bounced cheques')
    stop_payments_count = fields.Integer('No. of Stop Payments', help='Indicates the number of stop payments')
    daif_count = fields.Integer('No. of DAIF', help='Indicates the number of DAIF')
    delayed_payments_count = fields.Integer('No. of Delayed Payments', help='Indicates the number of delayed payments')
    comments = fields.Text()
    ci_done_by = fields.Many2one('res.partner', 'CI Done By')
    ci_done_on = fields.Date('CI Done On')

    def _compute_approved_credit_term_display(self):
        for rec in self:
            rec.approved_credit_term_display = "%s %s" % (
                rec.approved_credit_term,
                dict(self._fields['approved_credit_term_measure'].selection).get(rec.approved_credit_term_measure)
            )


class BankReference(models.Model):
    _name = 'credit.application.reference.bank'
    _description = 'Credit Application - Bank Reference'

    credit_application_id = fields.Many2one('credit.application', 'Credit Application')
    name = fields.Char('Name of Bank', required=True)
    branch_name = fields.Char('Branch', required=True)
    account_type = fields.Char('Account Type', required=True)
    account_no = fields.Char('Account No.', required=True)
    contact_person = fields.Char('Contact Person', help='Indicates the contact person of the supplier', required=True)
    position = fields.Char('Position', help='Indicates the position of the contact person', required=True)
    telephone_no = fields.Char('Telephone No.', help='Indicates the telephone number of the contact person',
                               required=True)
    email_address = fields.Char('Email Address', help='Indicates the email address of the contact person',
                                required=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.user.company_id.currency_id)
    ave_monthly_balance = fields.Monetary('Ave. Monthly Balance', required=True,
                                          help='Indicates the average monthly balance of the bank account')
    items_purchased = fields.Text('Items Purchased', help='Indicates the items purchased from the supplier')
    relationship_length = fields.Integer('Length of Relationship', help='Indicates the length of relationship in years')
    has_bounced_payments = fields.Boolean('Bounced Payments', help='Indicates if there are any bounced payments')
    has_stop_payments = fields.Boolean('Stop Payments', help='Indicates if there are any stop payments')
    has_daif = fields.Boolean('DAIF', help='Indicates if there are any DAIF')
    bounced_payments_count = fields.Integer('No. of Bounced Cheques', help='Indicates the number of bounced cheques')
    stop_payments_count = fields.Integer('No. of Stop Payments', help='Indicates the number of stop payments')
    daif_count = fields.Integer('No. of DAIF', help='Indicates the number of DAIF')
    comments = fields.Text()
    bi_done_by = fields.Many2one('res.partner', 'CI Done By')
    bi_done_on = fields.Date('CI Done On')
