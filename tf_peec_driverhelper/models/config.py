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
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrDocType(models.Model):
    _name = "tf.hr.doc.type"
    _description = "Document Types for Driver/Helper"

    _sql_constraints = [('name_unique', 'unique(name)', 'Drive configuration already exists.')]

    name = fields.Char("Name", required=True, copy=False, help="Indicates the document type.")


class HrLicenseType(models.Model):
    _name = "tf.hr.license.type"
    _description = "License Types for Driver/Helper"

    _sql_constraints = [('name_unique', 'unique(name)', 'Drive configuration already exists.')]

    name = fields.Char("Name", required=True, copy=False, help="Indicates the license type.")


class HrLogisticDocumentType(models.Model):
    _name = 'tf.hr.logistic_doc.type'
    _description = 'Document Type'
    _inherit = ['mail.thread']

    name = fields.Char('Document Type', required=True, copy=False,
                       help="User will indicate the name of the document type.")
    certification_authority = fields.Char('Certification Authority',
                                          help="Indicate the certifying authority for the document type.")

    @api.constrains('name')
    def _check_name_unique(self):
        """
        @noted: This function checks for lowercase and uppercase alpha characters.
        """
        if self.name:
            name = self.name.lower()
            existing_name = self.search([('name', '!=', False)]).filtered(lambda x: x.name.lower() == name)
            if len(existing_name) > 1:
                raise ValidationError((_("Document Type Configuration - %s already exists.")) % existing_name[0].name)


class HrLogisticLicenseType(models.Model):
    _name = 'tf.hr.logistic_license.type'
    _description = 'License Type'
    _inherit = ['mail.thread']

    name = fields.Char('License Type', required=True, copy=False,
                       help="User will indicate the name of the license type.")
    certification_authority = fields.Char('Certification Authority',
                                          help="Indicate the certifying authority for the license type.")

    @api.constrains('name')
    def _check_name_unique(self):
        """
        @noted: This function checks for lowercase and uppercase alpha characters.
        """
        if self.name:
            name = self.name.lower()
            existing_name = self.search([('name', '!=', False)]).filtered(lambda x: x.name.lower() == name)
            if len(existing_name) > 1:
                raise ValidationError((_("License Type Configuration - %s already exists.")) % existing_name[0].name)

