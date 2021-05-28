# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2021 Taliform Inc.
#
# Author: Joshua <Joshua@taliform.com>
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
from itertools import count

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TfVmrsCode(models.Model):
    _name = 'vmrs.code'
    _description = 'VMRS Code Model'
    _parent_name = 'parent_id'
    _parent_store = True

    code_key_id = fields.Many2one('vmrs.code.key', string='Code Key', track_visibility='onchange', required=False)
    parent_id = fields.Many2one('vmrs.code', 'Parent Code', index=True)
    parent_path = fields.Char(index=True)
    code = fields.Char(string="Code")
    name = fields.Char(string="Description")

    def name_get(self):
        result = []
        for vck in self:
            name = "%s - %s" % (
                vck.code,
                vck.name
            )
            result.append((vck.id, name))
        return result


class TfVmrsCodeKey(models.Model):
    _name = 'vmrs.code.key'
    _description = 'VMRS Code Keys'

    code = fields.Char(string="Code Key")
    name = fields.Char(string="Description")

    def name_get(self):
        result = []
        for vck in self:
            name = "%s (Code Key %s)" % (
                vck.name,
                vck.code
            )
            result.append((vck.id, name))
        return result

    @api.depends('code')
    def _get_name(self):
        for rec in self:
            rec.name = rec.code

    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []

        if name:
            recs = self.search(['|', ('code', operator, name), ('name', operator, name)] + args, limit=limit)
        else:
            recs = self.search([] + args, limit=limit)

        return recs.name_get()
