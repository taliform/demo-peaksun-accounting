# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Bamboo <martin@taliform.com>
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


class Partner(models.Model):
    _inherit = 'res.partner'

    def _domain_maximum_load_uom_id(self):
        return [('category_id', '=', self.env.company.logistics_cement_uom_category_id.id)]

    maximum_load = fields.Float('Maximum Load')
    maximum_load_uom_id = fields.Many2one('uom.uom', 'Maximum Load (UoM)', domain=_domain_maximum_load_uom_id)
    is_weight_checker = fields.Boolean('Weight Checker', help="Set to true if this partner should be selectable as "
                                                              "a check when creating weight logs.")
