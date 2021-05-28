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
import json

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountFinancialHtmlReportLine(models.Model):
    _inherit = 'account.financial.html.report.line'
    
    group_by = fields.Selection([('account_id', 'Accounts'), ('partner_id', 'Partners')], string="Presentation")
    cf_type = fields.Boolean(string="Is A Cash Flow Type")
    
    _sql_constraints = [
        ('name_uniq', 'unique(name, parent_id)', 'Section Name must be unique per Parent!'),
    ]
    
    @api.onchange('group_by', 'parent_id')
    def onchange_group_by(self):
        for rec in self:
            rec.groupby = rec.group_by  # need for Cash Flow Reports
            if rec.parent_id:
                section_ids = self.search([('parent_id', '=', rec.parent_id.id)]).sorted(key=lambda l: l.id)
                if not section_ids:
                    rec.sequence = rec.parent_id.sequence + 1
                else:
                    rec.sequence = section_ids[-1].sequence + 1
    
    @api.model
    def create(self, vals):
        parent = vals.pop('parent_id', False)
        if parent:
            parent_id = self.browse(parent)
            if parent_id.cf_type:
                code = vals.get('name')
                vals.update({
                    'parent_id': parent_id.id,
                    'code': code.replace(" ", "_")
                })
        
        res = super(AccountFinancialHtmlReportLine, self).create(vals)
        res = res.with_context({
            'recode': False
        })

        if res.parent_id.cf_type:
            res.domain = json.dumps([('cf_html_section_id', 'in', res.ids)])
            res.parent_id.create_cf_type_formula()
        return res

    def write(self, vals):
        res = super(AccountFinancialHtmlReportLine, self).write(vals)
        if self._context.get('recode', True):
            self = self.with_context({
                'recode': False
            })
            for rec in self.filtered(lambda x: x.parent_id.cf_type):
                rec.code = rec.name.strip().replace(".", "").replace(" ", "_")
        self.mapped('parent_id').filtered(lambda x: x.cf_type).create_cf_type_formula()
        return res

    def unlink(self):
        cf_type_ids = self.mapped('parent_id').filtered(lambda x: x.cf_type)
        res = super(AccountFinancialHtmlReportLine, self).unlink()
        cf_type_ids.create_cf_type_formula()
        return res

    def create_cf_type_formula(self):
        for rec in self:
            formula = False
            codes = rec.children_ids.mapped('code')
            for code in codes:
                if formula:
                    formula += " + " + code + ".balance"
                else:
                    formula = "balance = " + code + ".balance"
            rec.formulas = formula

    
class AccountPayment(models.Model):
    _inherit = 'account.payment'

    cf_html_type_id = fields.Many2one('account.financial.html.report.line', string="Type: ",
                                      domain="[('cf_type','=',True)]")
    cf_html_section_id = fields.Many2one('account.financial.html.report.line', string="Section: ")
    is_cf_required = fields.Boolean(related='journal_id.req_cashflow', string='Required Cash Flow')

    def post(self):
        res = super(AccountPayment, self).post()
        for rec in self:
            move_line_ids = rec.move_line_ids
            move_line_ids.mapped('move_id').write({
                'cf_html_type_id': rec.cf_html_type_id.id,
                'cf_html_section_id':rec.cf_html_section_id.id
            })
            move_line_ids.filtered(lambda l: l.account_id.user_type_id.type == 'liquidity').write({
                'cf_html_section_id': rec.cf_html_section_id.id
            })
        return res

    def write(self, vals):
        res = super(AccountPayment, self).write(vals)
        for rec in self:
            move_line_ids = rec.move_line_ids
            move_line_ids.mapped('move_id').write({
                'cf_html_type_id': rec.cf_html_type_id.id,
                'cf_html_section_id': rec.cf_html_section_id.id
            })
            move_line_ids.filtered(lambda l: l.account_id.user_type_id.type == 'liquidity').write({
                'cf_html_section_id': rec.cf_html_section_id.id
            })
        return res
    
    @api.onchange('cf_html_type_id')
    def onchange_cf_html_type_id(self):
        for rec in self:
            rec.cf_html_section_id = False


class AccountRegisterPayment(models.TransientModel):
    _inherit = 'account.payment.register'

    cf_html_type_id = fields.Many2one('account.financial.html.report.line', string="Type: ",
                                      domain="[('cf_type', '=', True)]")
    cf_html_section_id = fields.Many2one('account.financial.html.report.line', string="Section: ")
    is_cf_required = fields.Boolean(related='journal_id.req_cashflow', string='Required Cash Flow')

    def create_payments(self):
        """Create payments according to the invoices.
        Having invoices with different commercial_partner_id or different type (Vendor bills with customer invoices)
        leads to multiple payments.
        In case of all the invoices are related to the same commercial_partner_id and have the same type,
        only one payment will be created.

        :return: The ir.actions.act_window to show created payments.
        """
        Payment = self.env['account.payment']
        payments = Payment
        for payment_vals in self.get_payments_vals():
            if self.cf_html_type_id:
                payment_vals.update({
                    'cf_html_type_id': self.cf_html_type_id.id,
                    'cf_html_section_id': self.cf_html_section_id.id
                })
            if self.check_no:
                payment_vals.update({
                    'check_no': self.check_no
                })
            if self.payment_receipt:
                payment_vals.update({
                    'payment_receipt': self.payment_receipt
                })
            payments += Payment.create(payment_vals)
        payments.post()

        action_vals = {
            'name': _('Payments'),
            'domain': [('id', 'in', payments.ids), ('state', '=', 'posted')],
            'view_type': 'form',
            'res_model': 'account.payment',
            'view_id': False,
            'type': 'ir.actions.act_window',
        }
        if len(payments) == 1:
            action_vals.update({'res_id': payments[0].id, 'view_mode': 'form'})
        else:
            action_vals['view_mode'] = 'tree,form'
        return action_vals


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    cf_html_type_id = fields.Many2one('account.financial.html.report.line', string="Cash Flow Type",
                                      domain="[('cf_type','=',True)]")
    cf_html_section_id = fields.Many2one('account.financial.html.report.line', string="Section: ")
    is_cf_required = fields.Boolean(related='journal_id.req_cashflow', string='Required Cash Flow')

    def write(self, vals):
        res = super(AccountMove, self).write(vals)
        for rec in self:
            rec.line_ids.filtered(lambda l: l.account_id.user_type_id.type == 'liquidity').write({
                'cf_html_section_id': rec.cf_html_section_id.id
            })
        return res
    
    @api.onchange('cf_html_type_id')
    def onchange_cf_type(self):
        aaaData = self.line_ids
        if self.cf_html_type_id:
            self.cf_html_section_id = False
            self.line_ids.filtered(lambda l: l.account_id.user_type_id.type == 'liquidity').cf_html_section_id = False

    def action_post(self):
        res = super(AccountMove, self).action_post()
        for rec in self:
            if rec.is_cf_required:
                has_section = rec.invoice_line_ids.mapped('cf_html_section_id')
                if not has_section:
                    line_ids = rec.invoice_line_ids.filtered(lambda l: l.account_id.user_type_id.type == 'liquidity')
                    if line_ids:
                        raise ValidationError(_('Indicate the Section for %s account.') % line_ids[0].account_id.name)
                    else:
                        raise ValidationError(_('Indicate the account for the %s journal.') % rec.journal_id.name)
        return res


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
        
    cf_html_type_id = fields.Many2one(related='move_id.cf_html_type_id')
    cf_html_section_id = fields.Many2one('account.financial.html.report.line', string="Section: ")


class AccountJournal(models.Model):
    _inherit = 'account.journal'
    
    req_cashflow = fields.Boolean(help='If checked, Cash Flow will be required in the Journal Entries.')
