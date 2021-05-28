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
from odoo import fields, models


class TargetSUCF(models.Model):
    _name = 'logistics.target.sucf'
    _description = 'Target SUCF'

    origin_id = fields.Many2one('res.partner', 'Origin', required=True, index=True)
    destination_id = fields.Many2one('res.partner', 'Destination', required=True, index=True)
    target = fields.Float('Target SUCF', required=True)
    is_loaded = fields.Boolean('Loaded')

    def name_get(self):
        result = []
        for ts in self:
            name = "%s -> %s / Target SUCF: %s" % (
                ts.origin_id.trade_name or ts.origin_id.name,
                ts.destination_id.trade_name or ts.destination_id.name,
                ts.target
            )
            result.append((ts.id, name))
        return result
