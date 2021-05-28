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
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"
    
    check_no = fields.Char('Check No.')
    payee_id = fields.Many2one('res.partner', string='Actual Payee')
    check_released = fields.Boolean('Payment Release?', default=False)
    check_release_date = fields.Date('Payment Release Date') 
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        res = super(AccountPayment, self)._onchange_partner_id()
        for rec in self:
            rec.payee_id = rec.partner_id if rec.partner_id else False
        return res

    # @api.constrains('check_no')
    # def _check_check_no(self):
    #     """
    #     @summary: This function checks for lower case and upper case alpha characters
    #     """
    #     for rec in self:
    #         if rec.check_no:
    #             check_no = rec.check_no.lower()
    #             existing_check_no = rec.search([("check_no", "!=", False)]).filtered(lambda x: x.check_no.lower() == check_no)
    #             if len(existing_check_no) > 1:
    #                 raise ValidationError(_("Check No. entered already exists. Please enter different value."))

    def post(self):
        res = super(AccountPayment, self).post()
        for rec in self:
            move_line_ids = rec.move_line_ids
            for line in move_line_ids.filtered(lambda l: l.move_id):
                line.move_id.check_no = rec.check_no
        return res

    def action_print_voucher(self):
        move_ids = self.env['account.move']
        for rec in self:
            for move_id in rec.move_line_ids.mapped('move_id'):
                if move_id not in move_ids:
                    move_ids += move_id
        if len(move_ids) > 1:
            return self.env.ref('tf_ph_voucher.action_report_check_voucher_multi').report_action(move_ids)
        elif move_ids:
            return self.env.ref('tf_ph_voucher.action_report_check_voucher').report_action(move_ids)

    def release_check(self):
        '''
        @summary: Returns a form view of the Check Payment Wizard.
        '''
        
        view_id = self.env['ir.ui.view'].search([('name', '=', 'check.payment.date.view')])
        
        return {
                'name':'Check Payment Date',
                'view_type':'form',
                'view_mode':'form',
                'res_model':'check.payment.date',
                'view_id':view_id.id,
                'type':'ir.actions.act_window',
                'target':'new',
                'context':{'payment_id': self.id},
                }
