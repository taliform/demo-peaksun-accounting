# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Bamboo <joshua@taliform.com>
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
from datetime import timedelta

from odoo import api, fields, models,  _
from odoo.exceptions import ValidationError


class ReportAccountAgedPartner(models.AbstractModel):
    _inherit = "account.aged.partner"

    def _get_columns_name(self, options):
        columns = [
            {},
            {'name': _("Reference"), 'class': '', 'style': 'white-space:nowrap;'},
            {'name': _("Salesperson"), 'class': '', 'style': 'white-space:nowrap;'},
            {'name': _("Terms"), 'class': '', 'style': 'white-space:nowrap;'},
            {'name': _("Invoice Date"), 'class': 'date', 'style': 'white-space:nowrap;'},
            {'name': _("Due Date"), 'class': 'date', 'style': 'white-space:nowrap;'},
            {'name': _("Credit Limit"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("Total Advances"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("Claimed Amount"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("Unclaimed Balance"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("Actual Payment"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("PDC Amount"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("Remaining Balance"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("Balance"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("Days Due"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("Current"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("1 - 30"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("31 - 60"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("61 - 90"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("91 - 120"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("Older"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("Total"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("Total Overdue"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("Doubtful Amount"), 'class': 'number', 'style': 'white-space:nowrap;'}]

        return columns

    def get_advances_doubtful_amt(self, partner_inv_ids):
        today = fields.Date.today()

        total_advance = claimed_amt = unclaimed_bal = total_overdue = doubtful_amt = 0

        for invoice in partner_inv_ids:
            if invoice.is_customer_advance or invoice.is_downpayment:
                remaining_downpayment = invoice.remaining_downpayment
                total_downpayment = invoice.total_downpayment
                total_advance += total_downpayment
                unclaimed_bal += remaining_downpayment
                claimed_amt += (total_downpayment - remaining_downpayment)
            else:
                payment_term_days = timedelta(days=invoice.invoice_payment_term_id.line_ids.days)
                total_advance += 0
                claimed_amt += 0
                unclaimed_bal += invoice.remaining_downpayment
                if invoice.invoice_payment_term_id and (invoice.invoice_date + payment_term_days) <= today:
                    total_overdue += invoice.amount_residual
                doubtful_amt += invoice.est_doubtful_amt

        return total_advance, claimed_amt, unclaimed_bal, total_overdue, doubtful_amt

    @api.model
    def _get_lines(self, options, line_id=None):
        AccountInvoice = self.env['account.move']
        ResPartner = self.env['res.partner']
        CreditApplication = self.env['credit.application']
        context = self.env.context
        date_from = context.get('date_from')
        date_to = context.get('date_to')
        invoice_type = context.get('invoice_type')
        today = fields.Date.today()
        invoice_ids = AccountInvoice.search([
            ('date', '<=', date_to),
            ('date', '>=', date_from),
            ('state', '=', 'posted'),
            ('invoice_payment_state', '!=', 'paid'),
            ('is_customer_advance', '=', False),
            ('is_downpayment', '=', False),
            ('type', 'in', invoice_type)
        ])

        # Add Downpayment invoices to invoice list
        downpayment_inv_ids = AccountInvoice.search([
            ('date', '<=', date_to),
            ('date', '>=', date_from),
            ('state', '=', 'posted'),
            ('invoice_payment_state', '=', 'paid'),
            ('is_downpayment', '=', True),
            ('type', 'in', invoice_type)
        ])

        # Add Customer Advance invoices to invoice list
        ca_inv_ids = AccountInvoice.search([
            ('date', '<=', date_to),
            ('date', '>=', date_from),
            ('state', '=', 'posted'),
            ('invoice_payment_state', '=', 'paid'),
            ('is_customer_advance', '=', True),
            ('type', 'in', invoice_type)
        ])

        invoice_ids = invoice_ids | downpayment_inv_ids | ca_inv_ids

        unfold_all = context.get('print_mode') and not options.get('unfolded_lines')
        lines = []
        partner_ids = partner_ids2 = []
        overall_current = overall_total_1 = overall_total_2 = overall_total_3 = overall_total_4 = overall_subtotal = \
            overall_older = overall_amount = overall_residual = overall_payment = overall_pdc = 0

        overall_credit_limit = overall_total_advances = overall_claimed_amount = overall_unclaimed_balance \
            = overall_total_overdue = overall_doubtful_amount = 0

        if line_id and 'partner' in line_id:
            print(line_id)
            line_id = int(line_id.split('_')[1]) or None
            if line_id:
                partner_ids = ResPartner.browse(line_id)

        elif options.get('partner_ids'):
            # If a default partner is set, we only want to load the line referring to it.
            partner_ids2 = options['partner_ids']
            for p_id in partner_ids2:
                p_id = ResPartner.browse(p_id)
                line_id = p_id.id
                if p_id not in partner_ids:
                    partner_ids += p_id
                if line_id:
                    if 'partner_' + str(line_id) not in options.get('unfolded_lines', []):
                        options.get('unfolded_lines', []).append('partner_' + str(line_id))

            options.update({'partner_ids': list(dict.fromkeys(options['partner_ids']))})
        else:
            # Create partner list
            partner_ids = invoice_ids.mapped('partner_id')

        classifications = partner_ids.mapped('classification_id')
        ccs = [(_class.id, _class.name) for _class in classifications] + [(False, 'Unclassified')]

        for cc in ccs:
            if not line_id:
                vals = {
                    'id': 'classification_%s' % (cc[0],),
                    'name': cc[1],
                    'level': 2,
                    'unfoldable': True,
                    'unfolded': 'classification_' + str(cc[0]) in options.get('unfolded_lines') or unfold_all,
                    'columns': [{'name': ''}] * 23,
                }
                lines.append(vals)

            if not cc:
                cc = False

            for partner in partner_ids.filtered(lambda p: p.classification_id.id == cc[0]):
                partner_inv_ids = invoice_ids.filtered(lambda l: l.partner_id == partner)
                total_1, total_2, total_3, total_4, current, older, subtotal, partner_amount, partner_residual, partner_pdc = self.compute_aging(
                    partner_inv_ids)
                partner_payment = partner_amount - partner_residual
                total_advance, claimed_amt, unclaimed_bal, total_overdue, doubtful_amt = self.get_advances_doubtful_amt(partner_inv_ids)
                credit_limit = CreditApplication.search([
                    ('partner_id', '=', partner.id),
                    ('state', '=', 'approved')
                ]).approved_credit_line
                total_overdue = partner_residual - current
                partner_class = ''
                if total_overdue != 0 and partner_residual != 0:
                    total_overdue_percentage = total_overdue / partner_residual
                    if float(total_overdue_percentage) >= 0.2:
                        partner_class = 'table-danger'

                vals = {
                    'id': 'partner_%s' % (partner.id,),
                    'name': partner.name,
                    'level': 4,
                    'class': partner_class,
                    'unfoldable': True,
                    'unfolded': 'partner_' + str(partner.id) in options.get('unfolded_lines') or unfold_all,
                    'parent_id': 'classification_%s' % (cc[0],),
                    'columns': [{'name': ''}] * 5 +
                               [{'name': self.format_value(v)} for v in
                                [
                                 credit_limit,
                                 total_advance,
                                 claimed_amt,
                                 unclaimed_bal,
                                 partner_payment,
                                 partner_pdc,
                                 partner_residual,
                                 partner_amount
                                 ]
                                ] +
                               [{'name': ''}] +
                               [{'name': self.format_value(v)} for v in
                                [current,
                                 total_1, total_2, total_3, total_4, older, subtotal,
                                 total_overdue,
                                 doubtful_amt]],
                }
                lines.append(vals)

                overall_credit_limit += credit_limit
                overall_total_advances += total_advance
                overall_claimed_amount += claimed_amt
                overall_unclaimed_balance += unclaimed_bal
                overall_total_overdue += total_overdue
                overall_doubtful_amount += doubtful_amt

                overall_current += current
                overall_total_1 += total_1
                overall_total_2 += total_2
                overall_total_3 += total_3
                overall_total_4 += total_4
                overall_subtotal += subtotal
                overall_older += older
                overall_amount += partner_amount
                overall_residual += partner_residual
                overall_payment += partner_payment
                overall_pdc += partner_pdc

                current_type = 'dummy'
                for partner_inv in partner_inv_ids.sorted(key=lambda i: i.is_customer_advance):
                    if current_type != partner_inv.is_customer_advance:
                        vals = {
                            'id': 'customer_advance_%s' % (partner_inv.is_customer_advance,),
                            'name': 'Invoices' if not partner_inv.is_customer_advance else 'Advances',
                            'level': 6,
                            'unfoldable': True,
                            'unfolded': 'customer_advance_' + str(partner_inv.is_customer_advance) in options.get('unfolded_lines') or unfold_all,
                            'parent_id': 'partner_%s' % (partner.id,),
                            'columns': [{'name': ''}] * 23,
                        }
                        lines.append(vals)
                        current_type = partner_inv.is_customer_advance

                    due_date = partner_inv.invoice_date_due if partner_inv.invoice_date_due else today
                    no_of_days = (today - due_date).days
                    current = day_1 = day_31 = day_61 = day_91 = day_older = total = 0
                    pdc_amount = 0

                    sign = -1 if partner_inv.type in ('in_refund', 'out_refund') else 1
                    inv_amount = partner_inv.amount_total * sign
                    residual = partner_inv.amount_residual * sign

                    if no_of_days < 0:
                        current = inv_amount
                        no_of_days = 0
                    elif no_of_days in range(1, 30):
                        day_1 = residual
                    elif no_of_days in range(31, 60):
                        day_31 = residual
                    elif no_of_days in range(61, 90):
                        day_61 = residual
                    elif no_of_days in range(91, 120):
                        day_91 = residual
                    else:
                        day_older = residual

                    total = current + day_1 + day_31 + day_61 + day_91 + day_older
                    caret_type = 'account.invoice.in' if partner_inv.type in (
                        'in_refund', 'in_invoice') else 'account.invoice.out'
                    payment = float(inv_amount - residual)
                    pdc_amount = sum(partner_inv.pdc_line_ids.mapped('allocated_amt'))
                    if 'partner_' + str(partner.id) in options.get('unfolded_lines') or unfold_all:
                        # If invoice, 'id' should the move_line_id of the invoice
                        move_line_ids = self.env['account.move.line'].search([('move_id', '=', partner_inv.id)])
                        partner_inv_advance = 0
                        partner_inv_claimed_amt = 0
                        if partner_inv.is_customer_advance or partner_inv.is_downpayment:
                            partner_inv_advance = partner_inv.total_downpayment
                            partner_inv_claimed_amt = partner_inv.total_downpayment - partner_inv.remaining_downpayment
                        vals = {
                            'id': move_line_ids[0].id,
                            'name': partner_inv.name,
                            'level': 8,
                            'colspan': 1,
                            'caret_options': caret_type,
                            'parent_id': 'customer_advance_%s' % (partner_inv.is_customer_advance,),
                            'columns': [{'name': v} for v in
                                        [partner_inv.name,
                                         partner_inv.user_id.name,
                                         partner_inv.invoice_payment_term_id.name or partner_inv.invoice_date_due,
                                         partner_inv.invoice_date,
                                         partner_inv.invoice_date_due,
                                         '',  # Credit Limit
                                         self.format_value(partner_inv_advance),  # Total Advances
                                         self.format_value(partner_inv_claimed_amt),  # Claimed Amount
                                         self.format_value(partner_inv.remaining_downpayment),  # Unclaimed balance
                                         self.format_value(payment),  #
                                         self.format_value(pdc_amount),  #
                                         self.format_value(residual),  #
                                         self.format_value(inv_amount),  #
                                         no_of_days, ]] +
                                       [{'name': self.format_value(v)} for v in
                                        [current,
                                         day_1, day_31, day_61, day_91, day_older, total,
                                         residual - current,  # Total Overdue
                                         partner_inv.est_doubtful_amt,  # Doubtful Amount
                                         ]],
                        }
                        lines.append(vals)

        if not line_id or partner_ids2:
            total_line = {
                'id': 'grouped_partners_total',
                'name': _('Total'),
                'class': 'o_account_reports_domain_total',
                'level': 0,
                'columns': [{'name': ''}] * 6 +
                           [{'name': self.format_value(v)} for v in
                            [
                             overall_total_advances,
                             overall_claimed_amount,
                             overall_unclaimed_balance,
                             overall_payment,
                             overall_pdc,
                             overall_residual,
                             overall_amount]] +
                           [{'name': ''}] +
                           [{'name': self.format_value(v)} for v in
                            [overall_current,
                             overall_total_1, overall_total_2, overall_total_3, overall_total_4,
                             overall_older, overall_subtotal,
                             overall_total_overdue,
                             overall_doubtful_amount]],
            }
            lines.append(total_line)

        return lines
