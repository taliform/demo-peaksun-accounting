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
# GNU Affero General Public License for morewrite_date details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

from odoo import fields, api, models


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    is_manual = fields.Boolean('Is Manual', default=False)
    with_trial_balance = fields.Boolean('With Trial Balance', copy=False, compute="get_has_trial_bal", store=True)
    trial_approved = fields.Boolean('Trial Approved', default=False, copy=False)

    @api.depends('invoice_date', 'date')
    def get_has_trial_bal(self):
        date_today = fields.Date.today()
        tb_obj = self.env['tf.ph.trial.balance']
        for rec in self:
            if rec.type != 'entry' and rec.invoice_date != (rec.create_date or date_today):
                tb_id = tb_obj.search([('cut_off_date', '>=', rec.invoice_date)])
                rec.with_trial_balance = True if tb_id else False
            elif rec.type == 'entry' and rec.date != (rec.create_date or date_today):
                tb_id = tb_obj.search([('cut_off_date', '>=', rec.date)])
                rec.with_trial_balance = True if tb_id else False

    def trial_approve(self):
        self.trial_approved = True
