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
import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_WEEKDAYS = [
    ('monday', 'Monday'),
    ('tuesday', 'Tuesday'),
    ('wednesday', 'Wednesday'),
    ('thursday', 'Thursday'),
    ('friday', 'Friday'),
    ('saturday', 'Saturday'),
    ('sunday', 'Sunday')
]


class Partner(models.Model):
    _inherit = 'res.partner'

    trade_name = fields.Char('Trade Name')
    vat = fields.Char('TIN', help='Tax Identification Number (format: XXX-XXX-XXX-XXXXX')
    fax = fields.Char('Fax')
    year_business_started = fields.Char('Year Business Started')
    is_company_officer = fields.Boolean('Company Officer')
    is_check_signatory = fields.Boolean('Check Signatory')
    signature = fields.Binary('Specimen Signature')
    classification_id = fields.Many2one('res.partner.classification', 'Customer Classification')
    nature_id = fields.Many2one('res.partner.nature', 'Nature of Business')
    project_ids = fields.One2many('res.partner.project', 'partner_id', 'Major Projects')
    collection_day = fields.Selection(_WEEKDAYS, 'Collection Day', default='monday')
    collection_time = fields.Float('Collection Time')
    collection_address = fields.Text('Collection Address')
    mode_of_payment = fields.Selection([('bank_credit', 'Bank Credit'), ('check', 'Check'), ('cash', 'Cash')],
                                       'Mode of Payment', default='bank_credit')
    is_cement_plant = fields.Boolean('Cement Plant')
    is_batching_plant = fields.Boolean('Batching Plant')

    @api.constrains('vat')
    def _check_tin(self):
        for partner in self:
            if partner.vat:
                tin_format = re.compile("^[0-9]{3}-[0-9]{3}-[0-9]{3}-[0-9]{5}$")
                if not bool(tin_format.match(partner.vat)):
                    raise ValidationError(_('Invalid TIN format.'))

    @api.constrains('year_business_started')
    def _check_year_business_started(self):
        for partner in self:
            if partner.year_business_started:
                year_format = re.compile("^[0-9]{4}$")
                if not bool(year_format.match(partner.year_business_started)):
                    raise ValidationError(_('Invalid year format.'))


class PartnerClassification(models.Model):
    _name = 'res.partner.classification'
    _description = 'Partner - Customer Classification'

    name = fields.Char('Classification Name', required=True, help='Indicates the name of the classification')
    description = fields.Text('Description', help='Indicates the description of the classification')


class PartnerNature(models.Model):
    _name = 'res.partner.nature'
    _description = 'Partner - Nature of Business'

    name = fields.Char('Nature of Business', required=True, help='Indicates the nature of business')
    description = fields.Text('Description', help='Describes the nature of business')


class PartnerProject(models.Model):
    _name = 'res.partner.project'
    _description = 'Partner - Project'

    name = fields.Char('Project Name', required=True, help='Indicates the name of the project')
    partner_id = fields.Many2one('res.partner', 'Partner')
    location = fields.Char('Location', help='Indicates the location of the project')
    state = fields.Selection([('completed', 'Completed'), ('in_progress', 'In Progress'), ('future', 'Future')],
                             'Project Status', default='completed', required=True,
                             help='Indicates the current status of the project')
    developer_id = fields.Many2one('res.partner', 'Developer', help='Indicates the Developer of the project')
    contractor_id = fields.Many2one('res.partner', 'Contractor', help='Indicates the Contractor of the project')
    batching_plant_ids = fields.Many2many('res.partner', string='Batching Plants',
                                         help='Indicates the Batching Plant of the project')
    cement_type = fields.Selection([('bagged', 'Bagged'), ('bulk', 'Bulk'), ('others', 'Others')],
                                   'Type of Cement Supply', help='Indicates the Type of Cement Supply of the project')
    cement_type_is_bagged = fields.Boolean('Type of Cement Supply - Bagged')
    cement_type_is_bulk = fields.Boolean('Type of Cement Supply - Bulk')
    cement_type_is_others = fields.Boolean('Type of Cement Supply - Others')
    duration = fields.Integer('Project Duration')
    duration_measure = fields.Selection([('months', 'Months'), ('years', 'Years')], 'Project Duration Measure',
                                        default='months')
    comments = fields.Text()
