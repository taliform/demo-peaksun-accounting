# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Joshua <joshua@taliform.com>
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
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import get_lang


class AccountMove(models.Model):
    _inherit = 'account.move'

    # waiting for sales customization
    hauling_type = fields.Selection([
        ('time', 'Time Chartered'),
        ('voyage', 'Voyage Chartered')
    ], string='Hauling Type')
    billing_statement_id = fields.Many2one('account.billing.statement', 'Billing Statement')

    # BIR CAS
    business_style = fields.Char(string='Business Style', help="Indicates the company's business style", required=True,
                                 default=lambda self: self.env.company.business_style)
    permit_to_use_no = fields.Char(string="Permit to use No.",
                                   help="Indicates the permit to use CAS number provided by BIR.",
                                   default=lambda self: self.env.company.permit_to_use_no)
    date_issued = fields.Date(string="Date Issued", help="Indicates the date the permit is issued for the CAS.",
                              default=lambda self: self.env.company.date_issued)
    date_valid = fields.Date(string="Valid Until", help="Indicates the expiration date of the CAS permit.",
                             default=lambda self: self.env.company.date_valid)
    range_series_dr = fields.Char(string="Range of Series - Delivery Receipt",
                                  help="Indicates the permit's range of series.",
                                  default=lambda self: self.env.company.range_series_dr)
    range_series_bs = fields.Char(string="Range of Series - Billing Statement",
                                  help="Indicates the permit's range of series.",
                                  default=lambda self: self.env.company.range_series_bs)
    range_series_si = fields.Char(string="Range of Series - Sales Invoice",
                                  help="Indicates the permit's range of series.",
                                  default=lambda self: self.env.company.range_series_si)
    footnote = fields.Text(string="Footnote", help="Indicates the footnote for the official document printout.",
                           default=lambda self: self.env.company.footnote)

    def post(self):
        # Assign name before post
        for rec in self:
            if rec.hauling_type in ['time', 'voyage']:
                rec.write({'name': self.env['ir.sequence'].sudo().next_by_code('account.billing.statement')})
        super(AccountMove, self).post()

    # Overwrite action_invoice_print function because there's no way to modify function logic
    def action_invoice_sent(self):
        res = super(AccountMove, self).action_invoice_sent()

        if self.hauling_type in ['time', 'voyage']:
            template = self.env.ref('tf_peec_billing_statement.email_template_billing_statement',
                                    raise_if_not_found=False)
            lang = get_lang(self.env)
            if template and template.lang:
                lang = template._render_template(template.lang, 'account.move', self.id)
            else:
                lang = lang.code
            if 'default_use_template' in res['context']:
                res['context']['default_use_template'] = bool(template)
            if 'default_template_id' in res['context']:
                res['context']['default_template_id'] = template and template.id or False
            if 'model_description' in res['context']:
                res['context']['model_description'] = 'Billing Statement'

        return res


    total_discount = fields.Monetary(string='Less Discount', compute="_get_total_discount", store=True)
    invoice_terms_conditions = fields.Text('Terms and Conditions',
                                           default=lambda self:
                                           self.env.company.invoice_terms
                                           or self.env['ir.config_parameter']
                                           .sudo().get_param('account.use_invoice_terms') or '')
    @api.depends('invoice_line_ids')
    def _get_total_discount(self):
        for rec in self:
            rec.total_discount = 0
            invoice_total_discount = 0
            for line in rec.invoice_line_ids:
                total_discount = line.price_unit - (line.price_unit * (1 - (line.discount / 100.0)))
                invoice_total_discount += total_discount
            rec.total_discount = invoice_total_discount
