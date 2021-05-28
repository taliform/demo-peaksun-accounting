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


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    vmrs_code_key_1_id = fields.Many2one('vmrs.code.key', 'Code Key 1 (Equipment Vocation)',
                                          config_parameter='tf_peec_maintenance.vmrs_code_key_1_id')
    vmrs_code_key_14_id = fields.Many2one('vmrs.code.key', 'Code Key 14 (Reason for Repair)',
                                          config_parameter='tf_peec_maintenance.vmrs_code_key_14_id')
    vmrs_code_key_15_id = fields.Many2one('vmrs.code.key', "Code Key 15 (Work Accomplished)",
                                          config_parameter='tf_peec_maintenance.vmrs_code_key_15_id')
    vmrs_code_key_18_id = fields.Many2one('vmrs.code.key', "Code Key 18 (Technician Failure)",
                                          config_parameter='tf_peec_maintenance.vmrs_code_key_18_id')
    vmrs_code_key_31_id = fields.Many2one('vmrs.code.key', "Code Key 31 (System Level)",
                                          config_parameter='tf_peec_maintenance.vmrs_code_key_31_id')
    vmrs_code_key_32_id = fields.Many2one('vmrs.code.key', "Code Key 32 (Assembly Level)",
                                          config_parameter='tf_peec_maintenance.vmrs_code_key_32_id')
    vmrs_code_key_33_id = fields.Many2one('vmrs.code.key', "Code Key 33 (Component Level)",
                                          config_parameter='tf_peec_maintenance.vmrs_code_key_33_id')
    vmrs_code_key_34_id = fields.Many2one('vmrs.code.key', "Code Key 34 (Supplier Identifier)",
                                          config_parameter='tf_peec_maintenance.vmrs_code_key_34_id')
