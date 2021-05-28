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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
##############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime


class StockLandedCost(models.Model):
    _inherit = 'stock.landed.cost'

    def _get_company_id(self):
        """
        @summary: This will default Company Id on the form by
        getting the attached company_id of the current User. 
        """
        user_id = self.env.uid
        company_id = self.env['res.users'].browse(user_id).company_id.id
        return company_id

    company_id = fields.Many2one('res.company', string='Company', default=_get_company_id, track_visibility='onchange')
    state = fields.Selection([('draft', 'Draft'),
                              ('confirm', 'Confirmed'),
                              ('done', 'Posted'),
                              ('cancel', 'Cancelled')], 'State', default='draft', copy=False, readonly=True,
                             track_visibility='onchange')
    partner_id = fields.Many2one('res.partner', 'Vendor', states={'done': [('readonly', True)]},
                                 track_visibility='onchange')
    broker_id = fields.Many2one('res.partner', 'Broker', states={'done': [('readonly', True)]},
                                track_visibility='onchange')
    importation_date = fields.Date('Importation Date', states={'done': [('readonly', True)]},
                                   track_visibility='onchange')
    country_id = fields.Many2one('res.country', 'Country of Origin', states={'done': [('readonly', True)]},
                                 track_visibility='onchange')
    is_taxable = fields.Boolean('Taxable Dutiable Amount', default=False)
    assessment_date = fields.Date('Assessment/Release Date', states={'done': [('readonly', True)]},
                                  track_visibility='onchange')
    import_number = fields.Char('Import Entry Declaration Number', states={'done': [('readonly', True)]},
                                track_visibility='onchange')
    dutiable_amt = fields.Float('Dutiable Amount', compute='_get_lc_amount', store=True)
    all_charges = fields.Float('All charges before release from BOC', compute='_get_all_charges', store=True)
    vat_paid = fields.Float('VAT Paid', compute='_get_lc_amount', store=True)
    official_receipt = fields.Char('Official Receipt', states={'done': [('readonly', True)]},
                                   track_visibility='onchange')
    vat_payment_date = fields.Date('Date of VAT Payment', states={'done': [('readonly', True)]},
                                   track_visibility='onchange')
    amount_exempt = fields.Float('Landed Cost - Exempt')
    amount_taxable = fields.Float('Landed Cost - Taxable', compute='_get_lc_amount', store=True)
    total_amount = fields.Float('Total Landed Cost', compute='_get_lc_amount', store=True)
    line_amount_exempt = fields.Float('Cost Lines - Exempt', compute='_get_lc_amount', store=True)
    line_amount_taxable = fields.Float('Cost Lines - Taxable', compute='_get_lc_amount', store=True)
    line_amount_dutiable = fields.Float('Cost Lines - Dutiable', compute='_get_lc_amount', store=True)

    gross_weight = fields.Float('Gross Weight', states={'done': [('readonly', True)]}, track_visibility='onchange')
    net_weight = fields.Float('Net Weight', states={'done': [('readonly', True)]}, track_visibility='onchange')
    expected_arrival = fields.Datetime('Expected Arrival Date', states={'done': [('readonly', True)]},
                                       track_visibility='onchange')
    bill_lading = fields.Char('Bill of Lading', states={'done': [('readonly', True)]}, track_visibility='onchange')
    reference = fields.Text('Reference', states={'done': [('readonly', True)]}, track_visibility='onchange')
    invoice_ref = fields.Char('Invoice Reference', states={'done': [('readonly', True)]}, track_visibility='onchange')
    hs_code = fields.Char('HS Code', states={'done': [('readonly', True)]}, track_visibility='onchange')
    description = fields.Text('Description')
    landed_cost_no = fields.Char('Landed Cost No.')
    local_boolean = fields.Boolean('Local Purchase (Non-Import)')
    incoterm_id = fields.Many2one('account.incoterms', 'Incoterm', states={'done': [('readonly', True)]})
    valuation_summary_ids = fields.One2many('stock.valuation.adjustment.summary', 'cost_id',
                                            'Stock Valuation Adjustment Summary')
    transaction_value = fields.Float('Transaction Value (Foreign Currency)')
    currency_id = fields.Many2one('res.currency', 'Currency',
                                  track_visibility='onchange')
    boc_exchange_rate = fields.Float('Exchange Rate', states={'done': [('readonly', True)]},
                                     track_visibility='onchange')

    def button_validate(self):
        if any(cost.state != 'confirm' for cost in self):
            raise UserError(_('Only confirmed landed costs can be validated'))
        if any(not cost.valuation_adjustment_lines for cost in self):
            raise UserError(_('No valuation adjustments lines. You should maybe recompute the landed costs.'))
        if not self._check_sum():
            raise UserError(_('Cost and adjustments lines do not match. You should maybe recompute the landed costs.'))

        for cost in self:
            move = self.env['account.move']
            move_vals = {
                'journal_id': cost.account_journal_id.id,
                'date': cost.date,
                'ref': cost.name,
                'line_ids': [],
            }
            for line in cost.valuation_adjustment_lines.filtered(lambda line: line.move_id):
                # Prorate the value at what's still in stock
                cost_to_add = (line.move_id.stock_valuation_layer_ids.remaining_qty / line.move_id.stock_valuation_layer_ids.quantity) * line.additional_landed_cost

                line.move_id.stock_valuation_layer_ids.write({
                    'stock_landed_cost_id': cost.id,
                    'value': line.move_id.stock_valuation_layer_ids.value + line.additional_landed_cost,
                    'unit_cost': (line.move_id.stock_valuation_layer_ids.value + line.additional_landed_cost) / line.move_id.stock_valuation_layer_ids.quantity
                })

                # line.move_id.write({
                #     'landed_cost_value': new_landed_cost_value,
                #     'value': line.move_id.value + line.additional_landed_cost,
                #     'remaining_value': line.move_id.remaining_value + cost_to_add,
                #     'price_unit': (line.move_id.value + line.additional_landed_cost) / line.move_id.product_qty,
                # })
                # `remaining_qty` is negative if the move is out and delivered proudcts that were not
                # in stock.
                qty_out = 0
                if line.move_id._is_in():
                    qty_out = line.move_id.product_qty - line.move_id.product_id.qty_available
                elif line.move_id._is_out():
                    qty_out = line.move_id.product_qty
                move_vals['line_ids'] += line._create_accounting_entries(move, qty_out)

            move = move.create(move_vals)
            cost.write({'state': 'done', 'account_move_id': move.id})
            move.post()

        if self.picking_ids:
            self.picking_ids.write({'has_landed_cost': True})
        return True

    def button_confirm(self):
        if not self.cost_lines:
            raise ValidationError(_('Indicate the cost lines of this Landed Cost record.'))
        else:
            self.compute_landed_cost()
            self.state = 'confirm'

    def button_set_to_draft(self):
        self.state = 'draft'

    def format_date(self, date):
        if date:
            return datetime.strptime(str(date), '%Y-%m-%d').strftime('%B %d, %Y')
        else:
            return '-'

    @api.onchange('vendor_bill_id')
    def onchange_vendor_bill_id(self):
        self.incoterm_id = self.vendor_bill_id.invoice_incoterm_id
        self.partner_id = self.vendor_bill_id.partner_id


    @api.depends('total_amount', 'vat_paid')
    def _get_all_charges(self):
        for rec in self:
            rec.all_charges = rec.total_amount + rec.vat_paid

    @api.depends('cost_lines', 'cost_lines.is_taxable', 'is_taxable', 'transaction_value', 'boc_exchange_rate',
                 'amount_exempt')
    def _get_lc_amount(self):
        for rec in self:
            input_vat = self.env.user.company_id.input_vat_id
            taxable = sum(rec.cost_lines.filtered(lambda cl: cl.is_taxable).mapped('price_unit'))
            exempt = sum(rec.cost_lines.filtered(lambda cl: not cl.is_taxable).mapped('price_unit'))
            dutiable = sum(rec.cost_lines.filtered(lambda cl: cl.is_dutiable).mapped('price_unit'))
            rec.amount_exempt = exempt
            rec.line_amount_taxable = taxable if rec.is_taxable else taxable
            rec.line_amount_exempt = exempt if not rec.is_taxable else exempt
            rec.line_amount_dutiable = dutiable

            rec.dutiable_amt = dutiable + (rec.transaction_value * rec.boc_exchange_rate)
            rec.amount_taxable = rec.dutiable_amt + (taxable - dutiable)
            rec.total_amount = rec.amount_taxable + rec.amount_exempt

            if input_vat:
                rec.vat_paid = rec.amount_taxable * (input_vat.amount / 100)
            else:
                rec.vat_paid = 0.00

    def view_stock_valuation_adjustments_action(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Detailed Valuation Adjustments'),
            'res_model': 'stock.valuation.adjustment.lines',
            'view_type': 'form',
            'view_mode': 'tree',
            'target': 'current',
            'context': {'default_cost_id': self.id},
            'domain': [('cost_id', '=', self.id)],
        }

    # Summary of Valuation Adjustment Lines
    def generate_summary_valuation(self):
        SummaryLines = self.env['stock.valuation.adjustment.summary']
        ValuationAdjustmentLines = self.env['stock.valuation.adjustment.lines']

        summary_lines = []
        SummaryLines.search([('cost_id', 'in', self.ids)]).unlink()
        adjustment_lines = ValuationAdjustmentLines.search([('cost_id', '=', self.id)])

        for record in adjustment_lines:
            move_id = record.move_id.id
            product_id = record.product_id.id
            product_name = record.product_id.name
            quantity = record.quantity
            former = record.former_cost
            allocated = record.additional_landed_cost

            summary_ids = SummaryLines.search([('cost_id', '=', self.id),
                                               ('move_id', '=', move_id),
                                               ('product_id', '=', product_id)])

            if summary_ids:
                summary_ids.allocated_cost = summary_ids.allocated_cost + allocated
            else:
                SummaryLines.create({'cost_id': self.id,
                                     'move_id': move_id,
                                     'product_id': product_id,
                                     'name': product_name,
                                     'quantity': quantity,
                                     'former_cost': former,
                                     'allocated_cost': allocated})

        return True

    def compute_landed_cost(self):
        res = super(StockLandedCost, self).compute_landed_cost()
        self.generate_summary_valuation()
        return res


class StockLandedCostLines(models.Model):
    _inherit = 'stock.landed.cost.lines'

    is_taxable = fields.Boolean('Taxable')
    is_dutiable = fields.Boolean('Dutiable')

    @api.onchange('product_id')
    def onchange_product_id(self):
        product_id = self.product_id
        if not product_id:
            self.quantity = 0.0

        self.update({
            'is_dutiable': product_id.dutiable,
            'is_taxable':  product_id.taxable,
            'account_id': product_id.property_account_expense_id.id or
                          product_id.categ_id.property_account_expense_categ_id.id,
            'price_unit': product_id.standard_price or 0.0,
            'split_method': self.split_method or 'equal',
            'name': product_id.name or ''
        })


class StockValuationAdjustmentLines(models.Model):
    _inherit = 'stock.valuation.adjustment.lines'

    final_cost_per_unit = fields.Float('Final Cost (Per Unit)', compute='_compute_cost_per_unit', digits=0, store=True)
    add_cost_per_unit = fields.Float('Additional Incidental Cost (Per Unit)', compute='_compute_cost_per_unit',
                                     digits=0, store=True)
    product_uom_id = fields.Many2one(related='product_id.uom_po_id', string="Purchase Unit of Measure")
    former_cost_per_unit = fields.Float(
        'Former Cost(Per Unit)', compute='_compute_former_cost_per_unit',
        digits=0, store=True)

    @api.depends('former_cost', 'quantity')
    def _compute_former_cost_per_unit(self):
        for rec in self:
            rec.former_cost_per_unit = rec.former_cost / (rec.quantity or 1.0)

    @api.depends('final_cost', 'additional_landed_cost', 'quantity')
    def _compute_cost_per_unit(self):
        for rec in self:
            rec.final_cost_per_unit = rec.final_cost / (rec.quantity or 1.0)
            rec.add_cost_per_unit = rec.additional_landed_cost / (rec.quantity or 1.0)


class StockValuationAdjustmentSummary(models.Model):
    _name = 'stock.valuation.adjustment.summary'
    _description = 'Stock Valuation Adjustment Summary'

    def _get_company_id(self):
        """
        @summary: This will default Company Id on the form by
        getting the attached company_id of the current User. 
        """
        user_id = self.env.uid
        company_id = self.env['res.users'].browse(user_id).company_id.id
        return company_id

    cost_id = fields.Many2one('stock.landed.cost', string='Landed Cost')
    company_id = fields.Many2one('res.company', string='Company', default=_get_company_id, track_visibility='onchange')
    move_id = fields.Many2one('stock.move', 'Stock Move', readonly=True)
    product_id = fields.Many2one('product.product', string='Product')
    purchase_uom_id = fields.Many2one(related='product_id.uom_po_id', string="Purchase Unit of Measure")
    name = fields.Char('Name')
    quantity = fields.Float('Quantity')
    former_cost = fields.Float('Former Cost')
    former_cost_per_unit = fields.Float('Former Cost (per Unit)', compute='_compute_cost', digits=0, store=True)
    allocated_cost = fields.Float('Allocated Cost')
    allocated_cost_per_unit = fields.Float('Allocated Cost (per Unit)', compute='_compute_cost', digits=0, store=True)
    landed_cost = fields.Float('Landed Cost Amount', compute='_compute_cost', digits=0, store=True)
    landed_cost_per_unit = fields.Float('Landed Cost (per Unit)', compute='_compute_cost', digits=0, store=True)

    @api.depends('former_cost', 'allocated_cost', 'quantity')
    def _compute_cost(self):
        for rec in self:
            rec.former_cost_per_unit = rec.former_cost / (rec.quantity or 1.0)
            rec.allocated_cost_per_unit = rec.allocated_cost / (rec.quantity or 1.0)
            rec.landed_cost = rec.former_cost + rec.allocated_cost
            rec.landed_cost_per_unit = rec.landed_cost / (rec.quantity or 1.0)