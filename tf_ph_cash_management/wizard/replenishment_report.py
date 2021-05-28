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
from odoo import models, fields, api


class ReplenishmentReport(models.TransientModel):
    _name = 'replenishment.report'
    _description = 'Replenishment Report'
      
    cash_reple_id = fields.Many2one('cash.replenishment', string='Replenishment')
    cash_fund = fields.Float(string='Cash Fund')
    ongoing_rep = fields.Float(string='Ongoing Replenishment')
    unrep_transac = fields.Float(string='Unreplenished Transactions')
    unliq_amt = fields.Float(string='Unliquidated Amount')
    reimbursement_amt = fields.Float(string='Reimbursement Amount')
    cash_balance = fields.Float(string='Cash Balance')
    tot_cash_count = fields.Float(string='Cash Count Total')
    overage_shortage = fields.Float(string='Overage/Shortage')
    
#     @api.multi
#     def generate_replenish_report(self):
#         replenish_id = self.cash_reple_id
#         data = replenish_id.read()[0]
#         
#         filename = "Replenishment Report for %s" % (replenish_id.name)
#         data = {'ids': [replenish_id.id],
#                 'model': 'cash.replenishment',
#                 'form': data }
#      
#         return {'type': 'ir.actions.report.xml',
#                 'report_name': 'ss_ph_cash_management_enterprise.report_replenishment_wizard_document',
#                 'name': filename,
#                 'datas': data }

        
class ReplenishmentCashCount(models.TransientModel):
    _name = 'replenishment.cash.count'
    _description = 'Replenishment Cash Count'

    cash_rep_id = fields.Many2one('cash.replenishment', 'Replenishment')
    cash_balance = fields.Float(string='Cash Balance')
    cash_count_total = fields.Float(string='Cash Count Total')
    diff_amt = fields.Float(compute='_check_amount', string='Difference Amount', store=True)
    diff_amt_compare = fields.Float(compute='_check_amount', string='Difference Amount Compare', store=True)

    @api.depends('cash_balance', 'cash_count_total')
    def _check_amount(self):
        for rec in self:
            rec.diff_amt = abs(rec.cash_count_total - rec.cash_balance)
            rec.diff_amt_compare = rec.cash_balance - rec.cash_count_total

    def replenish_validate(self):
        for rec in self:
            rec.cash_rep_id.cash_management_id.write({'is_locked': False})
            rec.cash_rep_id.write({'state': 'draft'})
