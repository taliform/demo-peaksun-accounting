# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2019 Synersys Consulting Inc.
#
# Author: Andrian Jim Toscano Cubillas <andrian.cubillas@synersysph.com.ph>
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

from datetime import datetime, timedelta
from odoo import models, fields, api
from odoo.tools.misc import formatLang, format_date
from odoo.tools.translate import _
from odoo.tools import append_content_to_html, DEFAULT_SERVER_DATE_FORMAT
from odoo.exceptions import UserError

class AccountFollowupReport(models.AbstractModel):
    _inherit = "account.followup.report"

    def _get_columns_name(self, options):
        """
        Override
        Return the name of the columns of the follow-ups report
        """
        headers = [{},
                   {'name': _('Date'), 'class': 'date', 'style': 'text-align:center; white-space:nowrap;'},
                   {'name': _('Due Date'), 'class': 'date', 'style': 'text-align:center; white-space:nowrap;'},
                   {'name': _('Source Doc.'), 'style': 'text-align:center; white-space:nowrap;'},
                   {'name': _('Payment Reference'), 'style': 'text-align:right; white-space:nowrap;'},
                   {'name': _('Invoice Amt.'), 'class': 'number', 'style': 'text-align:right; white-space:nowrap;'},
                   {'name': _('Actual Payment'), 'class': 'number', 'style': 'text-align:right; white-space:nowrap;'},
                   {'name': _('PDC Amount'), 'class': 'number', 'style': 'text-align:right; white-space:nowrap;'},
                   {'name': _('Aging'), 'style': 'text-align:right; white-space:nowrap;'},
                   {'name': _('Expected Date'), 'class': 'd-none', 'style': 'white-space:nowrap;'},
                   {'name': _('Excluded'), 'class': 'date', 'style': 'white-space:nowrap;'},
                   {'name': _('Total Due'), 'class': 'number', 'style': 'text-align:right; white-space:nowrap;'}
                  ]
        if self.env.context.get('print_mode'):
            headers = headers[:9] + headers[11:]  # Remove the 'Expected Date' and 'Excluded' columns
        return headers
    

    def _get_lines(self, options, line_id=None):
        """
        Override
        Compute and return the lines of the columns of the follow-ups report.
        """
        # Get date format for the lang
        partner = options.get('partner_id') and self.env['res.partner'].browse(options['partner_id']) or False
        if not partner:
            return []

        lang_code = partner.lang if self._context.get('print_mode') else self.env.user.lang or get_lang(self.env).code
        lines = []
        res = {}
        today = fields.Date.today()
        line_num = 0
        for l in partner.unreconciled_aml_ids.filtered(lambda l: l.company_id == self.env.company):
            if l.company_id == self.env.company:
                if self.env.context.get('print_mode') and l.blocked:
                    continue
                currency = l.currency_id or l.company_id.currency_id
                if currency not in res:
                    res[currency] = []
                res[currency].append(l)
        for currency, aml_recs in res.items():
            total = 0
            total_issued = 0
            for aml in aml_recs:
                amount = aml.amount_residual_currency if aml.currency_id else aml.amount_residual
                date_due = format_date(self.env, aml.date_maturity or aml.date, lang_code=lang_code)
                total += not aml.blocked and amount or 0
                is_overdue = today > aml.date_maturity if aml.date_maturity else today > aml.date
                is_payment = aml.payment_id
                if is_overdue or is_payment:
                    total_issued += not aml.blocked and amount or 0
                if is_overdue:
                    date_due = {'name': date_due, 'class': 'color-red date', 'style': 'white-space:nowrap;text-align:center;color: red;'}
                if is_payment:
                    date_due = ''
                move_line_name = aml.move_id.name or aml.name
                if self.env.context.get('print_mode'):
                    move_line_name = {'name': move_line_name, 'style': 'text-align:right; white-space:normal;'}
                amount = formatLang(self.env, amount, currency_obj=currency)
                line_num += 1
                expected_pay_date = format_date(self.env, aml.expected_pay_date, lang_code=lang_code) if aml.expected_pay_date else ''

                payment = abs(float(aml.move_id.amount_total) - (aml.move_id.amount_residual))
                invoice_due_date = aml.move_id.invoice_date_due if aml.move_id.invoice_date_due else aml.move_id.date
                no_of_days = (today - invoice_due_date).days

                pdc_amount = sum(aml.move_id.pdc_line_ids.mapped('allocated_amt'))
                if no_of_days <= 0:
                    status = "Current"
                elif no_of_days in range(0, 31):
                    status = "1-30"
                elif no_of_days in range(30, 61):
                    status = "31-60"
                elif no_of_days in range(60, 91):
                    status = "61-90"
                elif no_of_days in range(90, 121):
                    status = "91-120"
                elif no_of_days > 120:
                    status = "Older"

                columns = [
                    format_date(self.env, aml.date, lang_code=lang_code),
                    date_due,
                    aml.move_id.ref or '',
                    aml.move_id.invoice_payment_ref,
                    self.format_value(aml.move_id.amount_total),
                    self.format_value(payment),
                    self.format_value(pdc_amount),
                    status,
                    (aml.internal_note or ''),
                    {'name': '', 'blocked': aml.blocked},
                    self.format_value(aml.move_id.amount_residual)
                ]

                if self.env.context.get('print_mode'):
                    columns = [
                        format_date(self.env, aml.date, lang_code=lang_code),
                        date_due,
                        aml.move_id.ref or '',
                        aml.move_id.invoice_payment_ref,
                        self.format_value(aml.move_id.amount_total),
                        self.format_value(payment),
                        self.format_value(pdc_amount),
                        status,
                        self.format_value(aml.move_id.amount_residual)
                    ]
                lines.append({
                    'id': aml.id,
                    'account_move': aml.move_id,
                    'name': aml.move_id.name,
                    'caret_options': 'followup',
                    'move_id': aml.move_id.id,
                    'type': is_payment and 'payment' or 'unreconciled_aml',
                    'unfoldable': False,
                    'columns': [type(v) == dict and v or {'name': v} for v in columns],
                })
            total_due = formatLang(self.env, total, currency_obj=currency)
            line_num += 1
            lines.append({
                'id': line_num,
                'name': '',
                'class': 'total',
                'style': 'border-top-style: double',
                'unfoldable': False,
                'level': 3,
                'columns': [{'name': v} for v in [''] * (7 if self.env.context.get('print_mode') else 9) + [total >= 0 and _('Total Due') or '', total_due]],
            })
            if total_issued > 0:
                total_issued = formatLang(self.env, total_issued, currency_obj=currency)
                line_num += 1
                lines.append({
                    'id': line_num,
                    'name': '',
                    'class': 'total',
                    'unfoldable': False,
                    'level': 3,
                    'columns': [{'name': v} for v in [''] * (7 if self.env.context.get('print_mode') else 9) + [_('Total Overdue'), total_issued]],
                })
            # Add an empty line after the total to make a space between two currencies
            line_num += 1
            lines.append({
                'id': line_num,
                'name': '',
                'class': '',
                'style': 'border-bottom-style: none',
                'unfoldable': False,
                'level': 0,
                'columns': [{} for col in columns],
            })
        # Remove the last empty line
        if lines:
            lines.pop()
        return lines