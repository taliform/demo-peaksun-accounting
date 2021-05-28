# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Andrian Jim Toscano Cubillas <andrian.cubillas@synersysph.com.ph>
# V13 Porting: Bamboo <martin@taliform.com>
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
from odoo import models, api, fields, _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as OE_DFORMAT
from datetime import datetime


class AccountJournalSummary(models.AbstractModel):
    _name = 'account.journal.summary'
    _description = 'Journal Summary Report'
    _inherit = 'account.report'
    
    filter_date = {'date_from': '', 'date_to': '', 'filter': 'this_year'}
    filter_unfold_all = True
    filter_partner = True
    filter_journals = True

    def _get_company_id(self):
        """
        @summary: This will default Company Id on the form by
        getting the attached company_id of the current User. 
        """
        user_id = self.env.uid
        company_id = self.env['res.users'].browse(user_id).company_id.id
        return company_id
    
    company_id = fields.Many2one('res.company', string='Company', default=_get_company_id, track_visibility='onchange')
    
    def _get_columns_name(self, options):
        columns = [
            {},
            {'name': _('Journal Entry'), 'class': 'text'},
            {'name': _('Reference'), 'class': 'text'},
            {'name': _('Partner'), 'class': 'text'},
            {'name': _('Label'), 'class': 'text'},
            {'name': _('Account'), 'class': 'text'},
            {'name': _('Debit'), 'class': 'number'},
            {'name': _('Credit'), 'class': 'number'},
            {'name': _('Analytic Account'), 'class': 'text'},
            {'name': _('Matching Number'), 'class': 'number'},
            {'name': _('Amount Currency'), 'class': 'text'},
            ]
        return columns
    
    @api.model 
    def get_month(self, string_date):
        return datetime.strptime(string_date, OE_DFORMAT).month
