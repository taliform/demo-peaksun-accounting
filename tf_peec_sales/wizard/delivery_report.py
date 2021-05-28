# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2021 Taliform Inc.
#
# Author: Ana Trajano <ana@taliform.com>
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
from odoo import fields, models, api, _
from datetime import date
import calendar


class SaleDeliveryOrderReportPDF(models.TransientModel):
    _name = 'sale.delivery.order.report.pdf'
    _description = "Sales Order - Summary of Deliveries (PDF)"

    @api.depends('company_id')
    def _get_company_details(self):
        for rec in self:
            rec.company_address = rec.company_info = rec.company_tin = city = tel = fax = address = ""

            if rec.company_id:
                company = rec.company_id
                if company.street: address += company.street
                if company.street2: address += ' ' + company.street2
                if company.city:
                    city = company.city
                    if 'city' in city or 'City' in city:
                        address += ' ' + city
                    else:
                        address += ' ' + city + ' City'
                if company.state_id: address += ' - ' + company.state_id.name
                if company.zip: address += ' ' + company.zip

                rec.company_address = address

                # Phone
                if rec.company_id.phone:
                    tel = 'Tel. No.: ' + rec.company_id.phone
                elif rec.company_id.partner_id.phone:
                    tel = 'Tel. No.: ' + rec.company_id.partner_id.phone
                else:
                    tel = 'Tel. No.: '

                # Fax
                if rec.company_id.partner_id.fax:
                    fax = '        Fax. No.: ' + rec.company_id.partner_id.fax
                else:
                    fax = '        Fax. No.: '

                rec.company_info = tel + fax
                rec.company_tin = 'VAT Reg. TIN: ' + rec.company_id.vat

    partner_id = fields.Many2one('res.partner', 'Customer')
    po_id = fields.Many2one('purchase.order', 'Purchase Order',
                            help="Indicates the purchase order related to filter all selected sales order")
    batching_plant_id = fields.Many2one('res.partner', 'Batching Plant',
                                        help="Indicates the batching plant to filter all selected sales orders")
    date_from = fields.Date("From", default=date.today().replace(day=1), required=True,
                            help="Indicates the starting date to filter all selected sales orders")
    date_to = fields.Date("To", required=True,
                          default=date.today().replace(day=calendar.monthrange(date.today().year,
                                                                               date.today().month)[1]),
                          help="Indicates the ending date to filter all selected sales orders")
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    so_ids = fields.Many2many('sale.order', string='Sale Order')
    company_address = fields.Char(compute='_get_company_details')
    company_info = fields.Char(compute='_get_company_details')
    company_tin= fields.Char(compute='_get_company_details')
    packaging = fields.Selection([('bulk','Bulk'), ('bagged', 'Bagged')], default='bulk')
    sale_type = fields.Selection([('cement', 'Cement',), ('hauling', 'Hauling')], default='cement')

    @api.onchange('partner_id', 'date_from', 'date_to', 'batching_plant_id', 'po_id')
    def onchange_details(self):
        active_ids = self._context.get('active_ids')
        if self._context.get('sale_type', False):
            self.sale_type = self._context['sale_type']

        if active_ids:
            so_ids = self.filtered_so_ids(active_ids)
        elif self._context.get('retrieve_all', False):
            so_ids_sch = self.env['sale.order'].search([('sale_type', '=', self.sale_type),('state', 'in', ['sale', 'done', 'close'])]).ids
            so_ids = self.filtered_so_ids(so_ids_sch)

        if so_ids:
            # Check if there are sales orders based on the conditions (Customer,PO, Batching, Date From and Date To)
            cust_so_ids = so_ids.filtered(lambda l: l.partner_id == self.partner_id
                                         and l.invoice_status == 'invoiced')
            if cust_so_ids:
                # Check Delivery Orders

                res = self.check_delivery_orders(cust_so_ids)
                if res:
                    with_packaging = res['with_packaging']
                    if with_packaging:
                        self.so_ids = res['do_so_ids']
                        self.so_ids.filtered(lambda s: self.date_from <= s.date_order.date() <= self.date_to)

    def filtered_so_ids(self, active_ids):
        temp_so_ids = self.env['sale.order']
        so_ids = False
        if active_ids:
            for active_id in active_ids:
                so_id = self.env['sale.order'].browse(active_id)
                temp_so_ids += so_id

        if temp_so_ids:
            if temp_so_ids[0].sale_type == 'cement':
                so_ids = temp_so_ids.filtered(lambda so_id: so_id.sale_type == 'cement'
                                              and so_id.state in ('sale', 'done', 'close'))
            elif temp_so_ids[0].sale_type == 'hauling':
                so_ids = temp_so_ids.filtered(
                    lambda so_id: so_id.sale_type == 'hauling' and so_id.state in ('sale', 'done', 'close'))
        return so_ids

    def check_delivery_orders(self, so_ids):
        do_so_ids = self.env['sale.order']
        with_do = atw_id = with_packaging = False
        for so_id in so_ids:
            do_ids = self.env['logistics.delivery.order']
            # Check if there's a delivery order based on the conditions
            for do_id in so_id.delivery_order_ids.filtered(lambda l: l.state == 'closed'):
                # Single Sales Order
                if not do_id.is_multiple_sale:
                    # Check if the same batching plant
                    if do_id.batching_plant_id == self.batching_plant_id:
                        # Check if there's a delivery order with the same purchase order indicated
                        if do_id.atw_id and do_id.atw_id.purchase_id:
                            po_id = do_id.atw_id.purchase_id
                            if po_id == self.po_id and self.packaging == do_id.atw_id.packaging:
                                atw_id = do_id.atw_id
                                do_ids += do_id
                                with_do = with_packaging = True

                else:
                    # Multiple Sales Order
                    # Check if there's a delivery order with the same purchase order indicated
                    if do_id.atw_id and do_id.atw_id.purchase_id:
                        po_id = do_id.atw_id.do_id.atw_id.purchase_id
                        if po_id == self.po_id:
                            # Check Allocations if the same batching plant and done status
                            alloc_id = do_id.allocation_ids.filtered(lambda l: l.sale_id == so_id)
                            if alloc_id:
                                if alloc_id.batching_plant_id == self.batching_plant_id and alloc_id.state == 'done'\
                                        and self.packaging == do_id.atw_id.packaging:
                                    atw_id = do_id.atw_id
                                    do_ids += do_id
                                    with_do = with_packaging = True


            if do_ids and with_do:
                do_so_ids += so_id

        if with_do:
            return {'do_so_ids': do_so_ids,
                    'do_ids': do_ids,
                    'atw_id': atw_id,
                    'with_packaging': with_packaging,
                    }
        else:
            return False

    def action_generate(self):
        self._get_company_details()
        self.onchange_details()
        if self.so_ids:
            data = {
                'model_id': self.id,
                'model': self._name,
                'so_ids': self.so_ids.ids,
            }
            return self.env.ref('tf_peec_sales.action_report_sale_delivery_order_pdf').report_action(self, data=data)


class SaleDeliveryOrderReport(models.AbstractModel):
    _name = 'report.tf_peec_sales.report_sale_delivery_order_pdf'
    _description = 'Sales Summary Delivery Report'

    @api.model
    def _get_report_values(self, docids, data):
        sale_cement_report = self.env['sale.delivery.order.report.pdf']
        model_id = data['model_id']
        report_id = sale_cement_report.browse(model_id)
        sale_type = report_id.sale_type
        po_qty = sum(report_id.po_id.order_line.mapped('product_qty'))
        so_ids = self.env['sale.order'].search([('id', 'in', data['so_ids'])])

        # Group by Sales Agreement and Order Date
        query = """SELECT sales_agreement_id, do_so_order_date
                        FROM sale_order
                        WHERE id IN %(so_ids)s
                        GROUP BY sales_agreement_id, do_so_order_date"""
        self._cr.execute(query, {'so_ids': tuple(so_ids.ids)})
        result = self._cr.dictfetchall()

        records = []
        del_lines = []
        rec_created = []
        do_ids_report = []
        ctr = 1

        for rec in result:
            sa_id = self.env['sale.agreement'].browse(rec['sales_agreement_id'])
            order_date = rec['do_so_order_date']
            total_delivered = 0.0

            for so_id in so_ids.filtered(lambda so_id: so_id.sales_agreement_id == sa_id
                                         and so_id.do_so_order_date == order_date
                                         and so_id.sale_type == sale_type):
                res = report_id.check_delivery_orders(so_id)
                if res:
                    do_ids = res['do_ids']
                    sequence = 0

                    # Create Lines
                    for do_id in do_ids:
                        if not do_id.is_report:
                            # Same Packaging Type
                            if report_id.packaging == do_id.atw_id.packaging:
                                sequence += 1
                                if not do_id.is_multiple_sale:
                                    qty = sum(so_id.order_line.filtered(lambda l: l.product_id == do_id.product_id). \
                                              mapped('qty_delivered'))
                                    price_unit = so_id.order_line.filtered(lambda l: l.product_id == do_id.product_id). \
                                        mapped('price_unit')

                                    if sale_type == 'cement':
                                        del_lines.append({'rec_id': ctr,
                                                          'departure_date': do_id.departure_date and do_id.departure_date.date(),
                                                          'atw_id': do_id.atw_id.name,
                                                          'invoice_id': so_id.invoice_ids and so_id.invoice_ids[0].name or False,
                                                          'delivery_receipt_id': do_id.picking_id.name,
                                                          'price_unit': price_unit[0],
                                                          'product_id': do_id.product_id and do_id.product_id.name or False,
                                                          'delivery_site_id': report_id.batching_plant_id.name,
                                                          'deliver_to_id': report_id.batching_plant_id.name,
                                                          'sequence': sequence,
                                                          'quantity': qty,
                                                          })
                                    elif sale_type == 'hauling':
                                        del_lines.append({'rec_id': ctr,
                                                          'departure_date': do_id.departure_date and do_id.departure_date.date(),
                                                          'atw_id': do_id.atw_id.name,
                                                          'invoice_id': so_id.invoice_ids and so_id.invoice_ids[ 0].name or False,
                                                          # 'delivery_receipt_id': do_id.picking_id.name,
                                                          'price_unit': price_unit[0],
                                                          # 'product_id': do_id.product_id and do_id.product_id.name or False,
                                                          'delivery_site_id': report_id.batching_plant_id.name,
                                                          'deliver_to_id': report_id.batching_plant_id.name,
                                                          'sequence': sequence,
                                                          'quantity': qty,
                                                          })
                                    total_delivered += qty
                                    sequence += 1
                                else:
                                    delivery_receipt_id = False
                                    qty = sum(so_id.order_line.filtered(lambda l: l.product_id == do_id.product_id). \
                                              mapped('qty_delivered'))
                                    price_unit = so_id.order_line.filtered(
                                        lambda l: l.product_id == do_id.product_id). \
                                        mapped('price_unit')
                                    alloc_id = do_id.allocation_ids.filtered(lambda l: l.sale_id == so_id)
                                    if alloc_id:
                                        delivery_receipt_id = alloc_id.picking_id

                                    if sale_type == 'cement':
                                        del_lines.append({'rec_id': ctr,
                                                          'departure_date': do_id.departure_date and do_id.departure_date.date(),
                                                          'atw_id': do_id.atw_id.name,
                                                          'invoice_id': so_id.invoice_ids and so_id.invoice_ids[0].name or False,
                                                          'delivery_receipt_id': delivery_receipt_id.name,
                                                          'price_unit': price_unit[0],
                                                          'product_id': do_id.product_id and do_id.product_id.name or False,
                                                          'delivery_site_id': report_id.batching_plant_id.name,
                                                          'deliver_to_id': report_id.batching_plant_id.name,
                                                          'sequence': sequence,
                                                          'quantity': qty,
                                                          })
                                    elif sale_type == 'hauling':
                                        del_lines.append({'rec_id': ctr,
                                                          'departure_date': do_id.departure_date and do_id.departure_date.date(),
                                                          'atw_id': do_id.atw_id.name,
                                                          'invoice_id': so_id.invoice_ids and so_id.invoice_ids[0].name or False,
                                                          # 'delivery_receipt_id': delivery_receipt_id.name,
                                                          'price_unit': price_unit[0],
                                                          # 'product_id': do_id.product_id and do_id.product_id.name or False,
                                                          'delivery_site_id': report_id.batching_plant_id.name,
                                                          'deliver_to_id': report_id.batching_plant_id.name,
                                                          'sequence': sequence,
                                                          'quantity': qty,
                                                          })
                                    total_delivered += qty
                                    sequence += 1

                            do_id.sudo().is_report = True
                            do_ids_report.append(do_id)

            if rec not in rec_created:
                records += self.create_report_records(ctr, report_id, sa_id, order_date, total_delivered)
                rec_created.append(rec)
            ctr += 1

        # Reset
        for do_id in do_ids_report:
            do_id.sudo().is_report = False

        return {'records': records,
                'partner_id': report_id.partner_id.name,
                'po_id': report_id.po_id.name,
                'po_qty': po_qty,
                'lines': del_lines,
                'company_name': report_id.company_id.partner_id.name,
                'company_address': report_id.company_address,
                'company_info': report_id.company_info,
                'company_tin': report_id.company_tin,
                'sale_type': sale_type
        }

    def create_report_records(self, ctr, report_id, sa_id, order_date, total_delivered):
        records = []
        atw_type = False
        if report_id.packaging == 'bagged':
            atw_type = 'Bagged'
        elif report_id.packaging == 'bulk':
            atw_type = 'Bulk'
        po_qty = sum(report_id.po_id.order_line.mapped('product_qty'))
        records.append({
                         'rec_id': ctr,
                         'partner_id': report_id.partner_id.name,
                         'po_id': report_id.po_id.name,
                         'sa_id': sa_id.name,
                         'order_date': order_date,
                         'po_qty': sum(report_id.po_id.order_line.mapped('product_qty')),
                         'type': atw_type,
                         'total_delivered': total_delivered,
                         'balance': po_qty - total_delivered,
                         'sale_type': report_id.sale_type,
                         })
        return records


