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


class AccountPaymentPDC(models.Model):
    _name = 'account.payment.pdc'
    _description = 'Post Dated Check'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    STATE = [('draft', 'Draft'),
             ('confirmed', 'Confirmed'),
             ('paid', 'Paid'),
             ('cancel', 'Cancelled')]

    PAYMENT_TYPE = [('customer', 'Customer'),
                    ('supplier', 'Vendor')]

    name = fields.Char('PDC Reference', track_visibility='onchange', copy=False)
    description = fields.Char('Description', track_visibility='onchange')
    check_no = fields.Char('Check Number', related='payment_id.check_no', track_visibility='onchange')
    check_date = fields.Date('Check Date', default=fields.Date.context_today, track_visibility='onchange')
    payment_id = fields.Many2one('account.payment', string='Payment Reference')
    journal_id = fields.Many2one('account.journal', 'Payment Journal', track_visibility='onchange', related='payment_id.journal_id')
    currency_id = fields.Many2one('res.currency', track_visibility='onchange',
                                  default=lambda self: self.env.user.company_id.currency_id)
    partner_id = fields.Many2one('res.partner', track_visibility='onchange')
    amount = fields.Monetary('Payment Amount', currency_field='currency_id', track_visibility='onchange')
    state = fields.Selection(selection=STATE, default='draft', copy=False, string="Status", track_visibility='onchange')
    partner_type = fields.Selection(selection=PAYMENT_TYPE, default='customer', copy=False, string='PDC Type')
    pdc_invoice_ids = fields.One2many('account.payment.pdc.invoice.line', 'pdc_id', 'PDC Invoice List')
    company_id = fields.Many2one('res.company', related='payment_id.company_id', string='Company')
    notes = fields.Text('Notes')

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
                'context': {'active_ids': [rec.payment_id.id],
                            'default_payment_id': rec.payment_id.id,
                            'default_journal_id': rec.payment_id.journal_id.id,
                            'default_payment_date': rec.payment_id.payment_date,
                            },
            }
    def cancel_pdc(self):
        for rec in self:
            rec.state = 'cancel'
            if rec.payment_id:
                rec.payment_id.state = 'cancelled'

    @api.constrains('pdc_invoice_ids')
    def _check_invoice_line(self):
        for rec in self:
            if not rec.pdc_invoice_ids:
                raise ValidationError('No invoice selected for PDC.')

class AccountPaymentPDCInvoice(models.Model):
    _name = 'account.payment.pdc.invoice.line'
    _description = 'PDC Invoice List'

    pdc_id = fields.Many2one('account.payment.pdc', 'PDC Reference', ondelete='cascade')
    invoice_id = fields.Many2one('account.move', 'Invoice')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.user.company_id.currency_id)
    allocated_amt = fields.Monetary('Allocated Amount')
    inv_state = fields.Selection(related='invoice_id.invoice_payment_state', string='Invoice Status')
    pdc_state = fields.Selection(related='pdc_id.state', string='PDC Status')
    check_no = fields.Char(related='pdc_id.check_no', string='Check Number')
    journal_id = fields.Many2one('account.journal', 'Payment Journal', track_visibility='onchange', related='pdc_id.journal_id')
    check_date = fields.Date(related='pdc_id.check_date', string='Check Date')
    invoice_date = fields.Date(related='invoice_id.invoice_date', string='Invoice Date')
    due_date = fields.Date(related='invoice_id.invoice_date_due', string='Due Date')
    company_id = fields.Many2one('res.company', related='invoice_id.company_id', string='Company')


class AccountInvoice(models.Model):
    _inherit = 'account.move'

    pdc_line_ids = fields.One2many('account.payment.pdc.invoice.line', 'invoice_id', 'PDC Reference')
