# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Allen Guarnes <allen@taliform.com>
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


class JourneyPlan(models.Model):
    _name = 'logistics.journey.plan'
    _description = 'Journey Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    name = fields.Char('Reference', default='New', copy=False, required=True, tracking=True, index=True)
    origin_id = fields.Many2one('res.partner', 'Origin', index=True)
    destination_id = fields.Many2one('res.partner', 'Destination', index=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda s: s.env.company, index=True)
    navigation_by_directions = fields.Html('Navigation By Directions')
    driver_comments = fields.Html('Driver Comments')
    hazards = fields.Html('Hazards')
    special_instructions = fields.Html('Special Instructions')

    def name_get(self):
        result = []
        for jp in self:
            name = "%s -> %s / %s" % (
                jp.origin_id.trade_name or jp.origin_id.name,
                jp.destination_id.trade_name or jp.destination_id.name,
                jp.name
            )
            result.append((jp.id, name))
        return result

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Assign sequence
            if vals.get('name', _('New')) == _('New'):
                IrSequence = self.env['ir.sequence']
                if 'company_id' in vals:
                    vals['name'] = IrSequence.with_context(force_company=vals['company_id']).next_by_code(
                        self._name) or _('New')
                else:
                    vals['name'] = IrSequence.next_by_code(self._name) or _('New')

        result = super(JourneyPlan, self).create(vals_list)
        return result
