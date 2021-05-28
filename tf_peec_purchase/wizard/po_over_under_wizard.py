# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Martin Perez <martin@taliform.com>
# V13 Porting: Martin Perez <martin@taliform.com>
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
from datetime import date
import calendar
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PoOverUnder(models.TransientModel):
    _name = 'peec.po.over.under'
    _description = 'Purchase Order Cement Over Under Report'

    def _get_default_pos(self):
        if self.env.context.get('retrieve_all', False):
            return self.env['purchase.order'].search([
                    ('purchase_type', '=', 'cement'),
                    ('state', 'in', ['purchase', 'done'])
                ]).ids

    res_ids = fields.Many2many('purchase.order', 'po_over_under_res_ids_rel', string="Purchase Orders",
                               default=_get_default_pos)
    po_ids = fields.Many2many('purchase.order', 'po_over_under_po_ids_rel', string="Purchase Orders (Cement)",
                              domain="[('purchase_type', '=', 'cement')]")
    date_from = fields.Date("From", default=date.today().replace(day=1), required=True,
                            help="Indicates the starting date to filter all selected purchased orders from.")
    date_to = fields.Date("To",  required=True,
                          default=date.today().replace(day=calendar.monthrange(date.today().year,
                                                                               date.today().month)[1]),
                          help="Indicates the ending date to filter all selected purchased orders from")

    # This functions filters any PO that is not type cement and not in purchase status as we cannot selectively choose
    # which list view 'merge purchase orders' action will show. res_ids will contain every selected POs while po_ids
    # will contain the filtered ones
    @api.onchange('res_ids')
    def onchange_res_ids(self):
        if self.res_ids:
            self.po_ids = self.res_ids.\
                filtered(lambda po_id: po_id.purchase_type == 'cement' and po_id.state == 'purchase')

    def action_generate(self):
        date_from = self.date_from
        date_to = self.date_to
        po_ids = self.po_ids.filtered(lambda p: date_from <= p.date_approve.date() <= date_to)
        if po_ids:
            data = {
                'docs': po_ids.ids,
                'date_from': date_from,
                'date_to': date_to,
            }
            return self.env.ref('tf_peec_purchase.cement_over_under_pdf').report_action(self, data=data)


class PoOverUnderPrint(models.Model):
    _name = 'report.tf_peec_purchase.cement_over_under_pdf'
    _description = "Cement Over Under Report"

    def _get_report_values(self, docids, data):
        docs = []
        partner_names = {}
        lines_data = {}
        lines_total = {}
        partner_obj = self.env['res.partner']

        for result in self.env['purchase.order'].read_group([('id', 'in', data['docs'])],
                                                             ['partner_id', 'amount_untaxed', 'ids:array_agg(id)'],
                                                             ['partner_id']):
            if result['partner_id']:
                docid = result['partner_id'][0]
                docs.append(docid)
                partner = partner_obj.browse(docid)
                partner_names[docid] = partner.name
                lines_data[docid] = self.env['purchase.order'].browse(result['ids'])
                lines_total[docid] = result['amount_untaxed']

        print(docs)
        print(lines_data)
        print(lines_total)
        print(partner_names)
        return {
            'docs': self.env.user,
            'data': data,
            'partner_names': partner_names,
            'lines_data': lines_data,
            'lines_total': lines_total
        }
