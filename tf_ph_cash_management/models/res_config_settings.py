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
from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'
    
    cm_journal_id = fields.Many2one('account.journal', string='Clearing Journal',
                                    help='Select journal entry for clearing journal.')
    cm_cash_shortage_id = fields.Many2one('account.account', string='Cash Shortage Account',
                                          help='Select account for Cash Shortage.')
    cm_cash_overage_id = fields.Many2one('account.account', string='Cash Overage Account',
                                         help='Select account for Cash Overage.')
    cr_liq_journal_id = fields.Many2one('account.journal', string='CR Liquidation Journal',
                                        help='Select journal for the CR Liquidation.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    cm_journal_id = fields.Many2one(related='company_id.cm_journal_id', readonly=False, string='Clearing Journal',
                                    help='Select journal entry for clearing journal.')
    cm_cash_shortage_id = fields.Many2one(related='company_id.cm_cash_shortage_id', readonly=False,
                                          string='Cash Shortage Account', help='Select account for Cash Shortage.')
    cm_cash_overage_id = fields.Many2one(related='company_id.cm_cash_overage_id', readonly=False,
                                         string='Cash Overage Account', help='Select account for Cash Overage.')
    cr_liq_journal_id = fields.Many2one(related='company_id.cr_liq_journal_id', readonly=False,
                                        string='CR Liquidation Journal', help='Select journal for the CR Liquidation.')
