# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################
from odoo import models, fields, _
from odoo.exceptions import AccessError, UserError
from itertools import groupby
from odoo.tools import float_is_zero, float_compare


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    is_downpayment = fields.Boolean(
        string="Is a down payment", help="Down payments are made when creating bills from a purchase order."
                                         " They are not copied when duplicating purchase orders.")

    def _prepare_invoice_line(self, po_id):
        self.ensure_one()
        if self.product_id.purchase_method == 'purchase':
            qty = self.product_qty - self.qty_invoiced
        else:
            qty = self.qty_received - self.qty_invoiced

        if self.currency_id == po_id.currency_id:
            currency = False
        else:
            currency = po_id.currency_id

        return {
            'name': '%s: %s' % (po_id.name, self.name),
            'currency_id': currency and currency.id or False,
            'purchase_line_id': self.id,
            'product_uom_id': self.product_uom.id,
            'product_id': self.product_id.id,
            'price_unit': self.price_unit,
            'quantity': qty,
            'partner_id': po_id.partner_id.id,
            'analytic_account_id': self.account_analytic_id.id,
            'analytic_tag_ids': [(6, 0, self.account_analytic_id.ids)],
            'tax_ids': [(6, 0, self.taxes_id.ids)],
            'display_type': self.display_type,
        }

    def _get_invoice_line_sequence(self, new=0, old=0):
        """
        Method intended to be overridden in third-party module if we want to prevent the resequencing
        of invoice lines.

        :param int new:   the new line sequence
        :param int old:   the old line sequence

        :return:          the sequence of the SO line, by default the new one.
        """
        return new or old


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def copy_data(self, default=None):
        if default is None:
            default = {}
        if 'order_line' not in default:
            default['order_line'] = [
                (0, 0, line.copy_data()[0]) for line in self.order_line.filtered(lambda l: not l.is_downpayment)
            ]
        return super(PurchaseOrder, self).copy_data(default)

    def _prepare_bill(self):
        """
        Prepare the dict of values to create the new invoice for a purchase order.
        """
        self.ensure_one()
        # ensure a correct context for the _get_default_journal method and company-dependent fields
        self = self.with_context(default_company_id=self.company_id.id, force_company=self.company_id.id)
        journal = self.env['account.move'].with_context(default_type='in_invoice')._get_default_journal()
        if not journal:
            raise UserError(_('Please define an accounting purchase journal for the company %s (%s).')
                            % (self.company_id.name, self.company_id.id))

        bill_vals = {
            'ref': self.name or '',
            'type': 'in_invoice',
            'narration': self.notes,
            'currency_id': self.currency_id.id,
            'invoice_user_id': self.user_id and self.user_id.id,
            'partner_id': self.partner_id.id,
            'invoice_partner_bank_id': self.partner_id.bank_ids[:1].id,
            'fiscal_position_id':  self.fiscal_position_id.id or self.partner_id.property_account_position_id.id,
            'journal_id': journal.id,  # company comes from the journal
            'invoice_origin': self.name,
            'invoice_payment_term_id': self.payment_term_id.id,
            'invoice_payment_ref': self.partner_ref,
            'invoice_line_ids': [],
            'company_id': self.company_id.id,
        }
        return bill_vals

    def _get_bill_grouping_keys(self):
        return ['company_id', 'partner_id', 'currency_id']

    def _create_bills(self, grouped=False, final=False):
        """
        Create the invoice associated to the PO.
        :param grouped: if True, invoices are grouped by PO id. If False, invoices are grouped by
                        (partner_invoice_id, currency)
        :param final: if True, refunds will be generated if necessary
        :returns: list of created bills
        """
        if not self.env['account.move'].check_access_rights('create', False):
            try:
                self.check_access_rights('write')
                self.check_access_rule('write')
            except AccessError:
                return self.env['account.move']

        # 1) Create bills.
        bills_vals_list = []
        for order in self:
            pending_section = None

            # Invoice values.
            bill_vals = order._prepare_bill()

            # Invoice line values (keep only necessary sections).
            for line in order.order_line:
                if line.display_type == 'line_section':
                    pending_section = line
                    continue

                if line.product_qty > 0 or (line.product_qty == 0.0 and final) or line.display_type == 'line_note':
                    if pending_section:
                        bill_vals['invoice_line_ids'].append((0, 0, pending_section._prepare_invoice_line(order)))
                        pending_section = None
                    bill_vals['invoice_line_ids'].append((0, 0, line._prepare_invoice_line(order)))

            if not bill_vals['invoice_line_ids']:
                raise UserError(
                    _('There is no billable line. If a product has received quantities control policy, '
                      'please make sure that a quantity has been received.'))

            bills_vals_list.append(bill_vals)

        if not bills_vals_list:
            raise UserError(_(
                'There is no billable line. If a product has received quantities control policy, please make sure '
                'that a quantity has been received.'))

        # 2) Manage 'grouped' parameter: group by (partner_id, currency_id).
        if not grouped:
            new_bills_vals_list = []
            bill_grouping_keys = self._get_bill_grouping_keys()
            for grouping_keys, bills in groupby(
                    bills_vals_list, key=lambda x: [x.get(grouping_key) for grouping_key in bill_grouping_keys]):
                origins = set()
                payment_refs = set()
                refs = set()
                ref_bill_vals = None
                for bill_vals in bills:
                    if not ref_bill_vals:
                        ref_bill_vals = bill_vals
                    else:
                        ref_bill_vals['invoice_line_ids'] += bill_vals['invoice_line_ids']
                    origins.add(bill_vals['invoice_origin'])
                    payment_refs.add(bill_vals['invoice_payment_ref'])
                    refs.add(bill_vals['ref'])
                ref_bill_vals.update({
                    'ref': ', '.join(refs)[:2000],
                    'invoice_origin': ', '.join(origins),
                    'invoice_payment_ref': len(payment_refs) == 1 and payment_refs.pop() or False,
                })
                new_bills_vals_list.append(ref_bill_vals)
            bills_vals_list = new_bills_vals_list

        # 3) Create Bills.

        # As part of the bill creation, we make sure the sequence of multiple PO do not interfere
        # in a single bill. Example:
        # PO 1:
        # - Section A (sequence: 10)
        # - Product A (sequence: 11)
        # PO 2:
        # - Section B (sequence: 10)
        # - Product B (sequence: 11)
        #
        # If PO 1 & 2 are grouped in the same invoice, the result will be:
        # - Section A (sequence: 10)
        # - Section B (sequence: 10)
        # - Product A (sequence: 11)
        # - Product B (sequence: 11)
        #
        # Resequencing should be safe, however we resequence only if there are less bills than
        # orders, meaning a grouping might have been done. This could also mean that only a part
        # of the selected PO are billable, but resequencing in this case shouldn't be an issue.
        if len(bills_vals_list) < len(self):
            pol_obj = self.env['purchase.order.line']
            for bills in bills_vals_list:
                sequence = 1
                for line in bills['invoice_line_ids']:
                    line[2]['sequence'] = pol_obj._get_invoice_line_sequence(new=sequence, old=line[2]['sequence'])
                    sequence += 1

        # Manage the creation of bills in sudo because a purchase user must be able to generate an invoice from a
        # purchase order without "billing" access rights. However, he should not be able to create a bill from scratch.
        moves = self.env['account.move'].sudo().with_context(default_type='in_invoice').create(bills_vals_list)

        # 4) Some moves might actually be refunds: convert them if the total amount is negative
        # We do this after the moves have been created since we need taxes, etc. to know if the total
        # is actually negative or not
        if final:
            moves.sudo().filtered(lambda m: m.amount_total == 0.0).action_switch_invoice_into_refund_credit_note()
        for move in moves:
            move.message_post_with_view('mail.message_origin_link',
                values={'self': move, 'origin': move.line_ids.mapped('purchase_line_id.order_id')},
                subtype_id=self.env.ref('mail.mt_note').id
            )
        # raise ValueError("Bamboo Bamboo")
        return moves






