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
from odoo.tools.misc import formatLang, get_lang
from odoo.exceptions import ValidationError, RedirectWarning


class CashAdvance(models.Model):
    _inherit = "cash.advance"

    is_cf_required = fields.Boolean(
        default=
        lambda self: self.env.user.company_id.dr_journal_id.req_cashflow if self.env.user.company_id.dr_journal_id
        else False)
    cf_html_type_id = fields.Many2one('account.financial.html.report.line', string="Cash Flow Type",
                                      domain="[('cf_type','=',True)]")
    cf_html_section_id = fields.Many2one('account.financial.html.report.line', string="Section: ")

    def line_val_post_process(self, account_id):
        res = super(CashAdvance, self).line_val_post_process()

        if self.cf_html_type_id and self.cf_html_section_id and account_id:
            if account_id.user_type_id.type == 'liquidity':
                res.update({
                    'cf_html_section_id': self.cf_html_section_id.id
                })

        return res

    def inv_val_post_process(self):
        res = super(CashAdvance, self).inv_val_post_process()
        if self.cf_html_type_id and self.cf_html_section_id:
            res.update({
                'cf_html_type_id': self.cf_html_type_id.id,
                'cf_html_section_id': self.cf_html_section_id.id
            })

        return res



