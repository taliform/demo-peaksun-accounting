# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Bamboo <joshua@taliform.com>
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
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_STATES = [
    ('draft', 'Draft'),
    ('confirm', 'Confirmed'),
    ('validate', 'Validated')
]


class Reconcile2307(models.Model):
    _name = 'bir.creditable.tax.withheld.reconcile'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Reconcile 2307'

    name = fields.Char('Reference', default='Draft Reconcile (2307)', index=True)
    from_date = fields.Date('From Date', required=True)
    to_date = fields.Date('To Date', required=True)
    customer_id = fields.Many2one('res.partner', 'Customer', required=True, index=True)
    customer_vat = fields.Char(related='customer_id.vat', store=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    company_partner_id = fields.Many2one(related='company_id.partner_id', readonly=True)
    company_journal_id = fields.Many2one(related='company_id.reconcile_2307_journal_id', readonly=True,
                                         string='Journal')
    company_vat = fields.Char(related='company_id.vat', store=True)
    authorized_rep_id = fields.Many2one(related='company_id.authorized_rep_id')
    submitted_ids = fields.One2many('bir.creditable.tax.withheld.reconcile.submitted', 'reconcile_id', 'Submitted Form')
    detail_ids = fields.One2many('account.move.line', 'reconcile_id', 'Details')
    state = fields.Selection(_STATES, 'State', default='draft')
    move_ids = fields.One2many('account.move', 'reconcile_id', 'Adjusting Entries')

    def _update_details(self):
        if not self.submitted_ids:
            raise ValidationError(_('Submitted Form is required.'))

        items = self.env['account.move.line']
        for submitted in self.submitted_ids:
            if not submitted.atc_id:
                raise ValidationError(_('An ATC Code needs to be provided in Submitted Form.'))
            # Search Journal Items to add in Details
            items = items | self.env['account.move.line'].search([
                ('partner_id', '=', self.customer_id.id),
                ('tax_line_id', '=', submitted.atc_id.id),
                ('date', '>=', self.from_date),
                ('date', '<=', self.to_date),
                ('reconcile_id', '=', False),
                ('move_id.type', '=', submitted.atc_id.tax_due_2307)
            ])

        items.sorted(key=lambda i: i.date)
        return items

    def action_confirm(self):
        for rec in self:
            items = rec._update_details()
            rec.write({
                'name': self.env['ir.sequence'].sudo().next_by_code('bir.2307.ref'),
                'detail_ids': [(6, 0, items.ids)],
                'state': 'confirm'
            })

    def action_update(self):
        for rec in self:
            rec.detail_ids = [(5, 0, 0)]
            items = rec._update_details()
            rec.write({
                'detail_ids': [(6, 0, items.ids)]
            })

    def action_reconcile_all(self):
        for rec in self:
            for detail in rec.detail_ids:
                detail.is_reconcile = True
                detail.allocation = detail.tax_withheld

    def action_validate(self):
        for rec in self:
            for submitted in rec.submitted_ids:
                if submitted.withholding_amount != submitted.reconciled_amount:
                    raise ValidationError(_('Withholding Amount is not equal to Reconciled Amount. '
                                            'Please manually adjust allocations in Details.'))
                return {
                    'name': 'Generate Adjusting Entry',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'reconcile.2307.generate.adjusting.entry',
                    'view_id': self.env.ref('tf_peec_customer_2307.reconcile_2307_generate_adjusting_entry_view_form').id,
                    'context': {'default_reconcile_id': rec.id},
                    'type': 'ir.actions.act_window',
                    'target': 'new'
                }


class SubmittedForm(models.Model):
    _name = 'bir.creditable.tax.withheld.reconcile.submitted'
    _description = 'Reconcile 2307 - Submitted Form'

    reconcile_id = fields.Many2one('bir.creditable.tax.withheld.reconcile', 'Reconcile 2307')
    atc_id = fields.Many2one('account.tax', 'ATC Code', required=True)
    withholding_amount = fields.Monetary('Withholding Amount')
    reconciled_amount = fields.Monetary('Reconciled Amount', compute="_compute_reconciled_amount", store=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)

    @api.depends('reconcile_id', 'reconcile_id.detail_ids', 'reconcile_id.detail_ids.is_reconcile', 'reconcile_id.detail_ids.allocation')
    def _compute_reconciled_amount(self):
        print('its computing')
        for rec in self:
            reconciled_amount = 0
            if rec.reconcile_id:
                for detail in rec.reconcile_id.detail_ids:
                    reconciled_amount += detail.allocation if detail.is_reconcile else 0
            print(reconciled_amount)
            rec.reconciled_amount = reconciled_amount
