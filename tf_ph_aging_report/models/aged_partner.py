# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Andrian Jim Toscano Cubillas <andrian.cubillas@synersysph.com.ph>
# v13 Porting: Bamboo <martin@taliform.com>
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

from odoo import models, api, fields, _


class ReportAccountAgedPartner(models.AbstractModel):
    _inherit = "account.aged.partner"

    filter_date = {'date_from': '', 'date_to': '', 'filter': 'today'}
    filter_unfold_all = True
    filter_partner = True

    def _get_columns_name(self, options):
        columns = [
            {},
            {'name': _("Reference"), 'class': '', 'style': 'white-space:nowrap;'},
            {'name': _("Payment Reference"), 'class': '', 'style': 'white-space:nowrap;'},
            {'name': _("Salesperson"), 'class': '', 'style': 'white-space:nowrap;'},
            {'name': _("Invoice Date"), 'class': 'date', 'style': 'white-space:nowrap;'},
            {'name': _("Due Date"), 'class': 'date', 'style': 'white-space:nowrap;'},
            {'name': _("Balance"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("Actual Payment"), 'class': '', 'style': 'white-space:nowrap;'},
            {'name': _("PDC Amount"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("Remaining Balance"), 'class': '', 'style': 'white-space:nowrap;'},
            {'name': _("Days Due"), 'class': '', 'style': 'white-space:nowrap;'},
            {'name': _("Current"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("1 - 30"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("31 - 60"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("61 - 90"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("91 - 120"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("Older"), 'class': 'number', 'style': 'white-space:nowrap;'},
            {'name': _("Total"), 'class': 'number', 'style': 'white-space:nowrap;'}]

        return columns

    def compute_aging(self, partner_invoices):
        today = fields.Date.today()
        total_1 = total_2 = total_3 = total_4 = current = older = subtotal = partner_amount = partner_pdc = partner_residual = 0
        for invoice in partner_invoices:
            sign = -1 if invoice.type in ('in_refund', 'out_refund') else 1
            inv_amount = invoice.amount_total * sign
            residual = invoice.amount_residual * sign
            due_date = invoice.invoice_date_due if invoice.invoice_date_due else today
            no_of_days = (today - due_date).days
            if no_of_days <= 0:
                current += inv_amount
            elif no_of_days in range(0, 31):
                total_1 += residual
            elif no_of_days in range(30, 61):
                total_2 += residual
            elif no_of_days in range(60, 91):
                total_3 += residual
            elif no_of_days in range(90, 121):
                total_4 += residual
            elif no_of_days > 120:
                older += residual

            partner_amount += inv_amount
            partner_residual += residual
            subtotal = current + total_1 + total_2 + total_3 + total_4 + older

            partner_pdc = sum(invoice.pdc_line_ids.mapped('allocated_amt'))

        return total_1, total_2, total_3, total_4, current, older, subtotal, partner_amount, partner_residual, partner_pdc

    def get_pdc(self, partner_invoices):
        partner_pdc_amt = 0.0
        for invoice in partner_invoices:
            if invoice.pdc_line_ids:
                partner_pdc_amt += sum(invoice.pdc_line_ids.filtered(lambda l: l.pdc_state not in ('paid', 'cancel')).mapped('allocated_amt'))

        return partner_pdc_amt

    @api.model
    def _get_lines(self, options, line_id=None):
        AccountInvoice = self.env['account.move']
        ResPartner = self.env['res.partner']
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
            ('type', 'in', invoice_type)
        ])

        unfold_all = context.get('print_mode') and not options.get('unfolded_lines')
        lines = []
        partner_ids = partner_ids2 = []
        overall_current = overall_total_1 = overall_total_2 = overall_total_3 = overall_total_4 = overall_subtotal = overall_older = overall_amount = overall_residual = overall_payment = overall_pdc = 0

        if line_id:
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

        for partner in partner_ids:
            partner_inv_ids = invoice_ids.filtered(lambda l: l.partner_id == partner)
            total_1, total_2, total_3, total_4, current, older, subtotal, partner_amount, partner_residual=self.compute_aging(partner_inv_ids)
            partner_payment = partner_amount - partner_residual
            partner_pdc = self.get_pdc(partner_inv_ids)
            if partner_pdc:
               print(partner_pdc)
            vals = {
                'id': 'partner_%s' % (partner.id,),
                'name': partner.name,
                'level': 2,
                'unfoldable': True,
                'unfolded': 'partner_' + str(partner.id) in options.get('unfolded_lines') or unfold_all,
                'columns': [{'name': ''}] * 5 +
                           [{'name': self.format_value(v)} for v in
                            [partner_amount,
                             partner_payment,
                             partner_pdc,
                             partner_residual
                             ]
                            ] +
                           [{'name': ''}] +
                           [{'name': self.format_value(v)} for v in
                            [current, total_1, total_2, total_3, total_4, older, subtotal]],
            }
            lines.append(vals)

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

            for partner_inv in partner_inv_ids:
                due_date = partner_inv.invoice_date_due if partner_inv.invoice_date_due else today
                no_of_days = (today - due_date).days
                current = day_1 = day_31 = day_61 = day_91 = day_older = total = 0
                pdc_amount = 0

                sign = -1 if partner_inv.type in ('in_refund', 'out_refund') else 1
                inv_amount = partner_inv.amount_total * sign
                residual = partner_inv.amount_residual * sign

                if no_of_days <= 0:
                    current = inv_amount
                    no_of_days = 0
                elif no_of_days in range(0, 31): #0 #31
                    day_1 = residual
                elif no_of_days in range(30, 61): #30 #61
                    day_31 = residual
                elif no_of_days in range(60, 91): #60 #91
                    day_61 = residual
                elif no_of_days in range(90, 121):#90 #121
                    day_91 = residual
                elif no_of_days > 120:
                    day_older = residual

                total = current + day_1 + day_31 + day_61 + day_91 + day_older
                caret_type = 'account.invoice.in' if partner_inv.type in (
                    'in_refund', 'in_invoice') else 'account.invoice.out'
                payment = float(inv_amount - residual)
                pdc_amount = sum(partner_inv.pdc_line_ids.filtered(lambda l: l.pdc_state not in ('paid', 'cancel')).mapped('allocated_amt'))
                if 'partner_' + str(partner.id) in options.get('unfolded_lines') or unfold_all:
                    # If invoice, 'id' should the move_line_id of the invoice
                    move_line_ids = self.env['account.move.line'].search([('move_id', '=', partner_inv.id)])
                    vals = {
                        'id': move_line_ids[0].id,
                        'name': partner_inv.name,
                        'level': 4,
                        'colspan': 1,
                        'caret_options': caret_type,
                        'parent_id': 'partner_%s' % (partner.id,),
                        'columns': [{'name': v} for v in
                                    [partner_inv.ref,
                                     partner_inv.invoice_payment_ref,
                                     partner_inv.user_id.name,
                                     partner_inv.invoice_date,
                                     partner_inv.invoice_date_due,
                                     self.format_value(inv_amount),  #
                                     self.format_value(payment), #
                                     self.format_value(pdc_amount), #
                                     self.format_value(residual), #
                                     no_of_days, ]] +
                                   [{'name': self.format_value(v)} for v in
                                    [current, day_1, day_31, day_61, day_91, day_older, total]],
                    }
                    lines.append(vals)

        if not line_id or partner_ids2:
            total_line = {
                'id': 'grouped_partners_total',
                'name': _('Total'),
                'class': 'o_account_reports_domain_total',
                'level': 0,
                'columns': [{'name': ''}] * 5 +
                           [{'name': self.format_value(v)} for v in
                            [overall_amount,
                             overall_payment,
                             overall_pdc,
                             overall_residual]] +
                           [{'name': ''}] +
                           [{'name': self.format_value(v)} for v in
                            [overall_current, overall_total_1, overall_total_2, overall_total_3, overall_total_4,
                             overall_older, overall_subtotal]],
            }
            lines.append(total_line)

        return lines
