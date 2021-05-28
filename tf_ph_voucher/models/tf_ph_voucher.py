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
from odoo.exceptions import Warning, ValidationError


class CopyCheckNo(models.Model):
    _name = 'copy.check.no'
    _description = 'Copy Check Number'

    def _get_company_id(self):
        """
        @summary: This will default Company Id on the form by
        getting the attached company_id of the current User. 
        """
        user_id = self.env.uid
        company_id = self.env['res.users'].browse(user_id).company_id.id
        return company_id
    
    company_id = fields.Many2one('res.company', string='Company', default=_get_company_id, track_visibility='onchange')

    def confirm_copy(self):
        for i in self.env['account.payment'].browse(self._context.get(('active_ids'), [])):
            if i.move_line_ids:
                for line in i.move_line_ids.filtered(lambda l: l.move_id):
                    line.move_id.check_no = i.check_no
            else:
                pass
