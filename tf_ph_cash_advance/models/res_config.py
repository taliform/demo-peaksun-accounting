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

from odoo import models, fields


class CAConfigurationSettings(models.Model):
    _inherit = 'res.company'

    APPROVAL_LEVELS = [
        ('basic', 'Basic approval process (one step)'),
        ('two', 'Two level approval process (two step)'),
    ]

    def _get_manager_ids(self):
        '''
        @return: Returns list if CA Managers
        '''
        for rec in self:
            manager_ids = self.env['res.users']
            ca_group_id = self.sudo().env['res.groups'].search(
                [('category_id.name', '=', 'Cash Advance'), ('name', '=', 'Manager')])
            if ca_group_id and ca_group_id.users:
                for user_id in ca_group_id.users:
                    manager_ids += user_id
            rec.manager_ids = manager_ids

    ca_journal_id = fields.Many2one('account.journal', string='CA Liquidation Journal',
                                    help="Select journal for CA Liquidation Journal.")
    ca_inv_journal_id = fields.Many2one('account.journal', string='CA Liquidation Invoice Journal',
                                        help="Select journal for the CA Liquidation Invoice Journal.")
    ca_req_journal_id = fields.Many2one('account.journal', string='CA Request Journal',
                                        help="Select journal for CA Journal.")
    ca_return_journal_id = fields.Many2one('account.journal', string='CA Return Journal',
                                           help="Select journal for CA Returns.")
    ca_reimburse_journal_id = fields.Many2one('account.journal', string='CA Reimbursements Journal',
                                              help="Select journal for CA Reimbursements.")
    dr_journal_id = fields.Many2one('account.journal', string='DR Journal', help="Select journal entry for DR Journal.")
    basic_approver_id = fields.Many2one('res.users', string='Approver', help="Select the CA approver.")
    second_approver_id = fields.Many2one('res.users', string='Second Approver', help="Select the second CA approver.")
    ca_multiple_approval = fields.Selection(selection=APPROVAL_LEVELS, default='basic',
                                            string="Levels of Approvals *")
    manager_ids = fields.Many2many('res.users', compute='_get_manager_ids')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ca_journal_id = fields.Many2one(related='company_id.ca_journal_id', readonly=False, string='CA Liquidation Journal',
                                    help="Select journal for CA Liquidation Journal.")
    ca_inv_journal_id = fields.Many2one(related='company_id.ca_inv_journal_id', readonly=False,
                                        string='CA Liquidation Invoice Journal',
                                        help="Select journal for the CA Liquidation Invoice Journal.")
    ca_return_journal_id = fields.Many2one(related='company_id.ca_return_journal_id', readonly=False,
                                           string='CA Return Journal',
                                           help="Select journal for CA Returns.")
    ca_reimburse_journal_id = fields.Many2one(related='company_id.ca_reimburse_journal_id', readonly=False,
                                              string='CA Reimbursements Journal',
                                              help="Select journal for CA Reimbursements.")
    ca_req_journal_id = fields.Many2one(related='company_id.ca_req_journal_id', readonly=False,
                                        string='CA Request Journal',
                                        help="Select journal for CA Liquidation Journal.")
    dr_journal_id = fields.Many2one(related='company_id.dr_journal_id', readonly=False, string='DR Journal',
                                    help="Select journal for DR Journal.")
    basic_approver_id = fields.Many2one(related='company_id.basic_approver_id', readonly=False, string='Approver',
                                        help="Select the CA approver.")
    second_approver_id = fields.Many2one(related='company_id.second_approver_id', readonly=False,
                                         string='Second Approver', help="Select the second CA approver.")
    ca_multiple_approval = fields.Selection(related='company_id.ca_multiple_approval', readonly=False,
                                            string="Cash Advance Levels of Approvals *")
    manager_ids = fields.Many2many(related='company_id.manager_ids')
