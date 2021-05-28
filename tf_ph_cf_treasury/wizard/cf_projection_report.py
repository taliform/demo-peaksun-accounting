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
from dateutil.relativedelta import relativedelta
from odoo import models


class TfCfProjectionReport(models.TransientModel):
    _name = 'tf.cf.projection.report'
    _description = "Cash Flow Projection Report"
    _inherit = 'tf.cf.projection'

    def action_generate(self):
        # Init
        line_ids = []
        vals = {'date_from': self.date_from, 'date_to': self.date_to}
        # Internal Transfer
        line_ids += self.env['tf.cf.undeposited'].create(
            {'date_from': self.date_from, 'date_to': self.date_to, 'type': 'internal'}
        ).with_context({'return_id': True}).action_generate()
        # Collection
        line_ids += self.generate_collections()
        # Disbursements
        line_ids += self.env['tf.cf.disbursement'].create(
            {'date_from': self.date_from, 'date_to': self.date_to, 'type': 'disbursement'}
        ).with_context({'return_id': True}).action_generate()
        # Customer PDC
        line_ids += self.env['tf.cf.customer.pdc'].create(
            {'date_from': self.date_from, 'date_to': self.date_to, 'type': 'customer_pdc'}
        ).with_context({'return_id': True}).action_generate()
        # Vendor PDC
        line_ids += self.env['tf.cf.vendor.pdc'].create(
            {'date_from': self.date_from, 'date_to': self.date_to, 'type': 'vendor_pdc'}
        ).with_context({'return_id': True}).action_generate()

        return {
            'name': "Cash Flow Projection Report: %s - %s" % (self.date_from, self.date_to),
            'type': 'ir.actions.act_window',
            'view_mode': 'pivot,tree',
            'domain': [('id', 'in', line_ids)],
            'res_model': 'tf.cf.projection.line',
            'views': [(self.env.ref('tf_ph_cf_treasury.tf_cf_report_pivot_view').id, 'pivot'),
                      (self.env.ref('tf_ph_cf_treasury.tf_cf_projection_line_tree').id, 'tree')],
            'context': {
                'search_default_group_report_type': 1,
                'search_default_group_bank': 1,
                'search_default_group_transaction': 1}
        }

    def generate_collections(self):
        self.ensure_one()
        # Init
        line_ids = []
        init_bal = 0.0
        date_from = self.date_from
        projection_line_obj = self.env['tf.cf.projection.line']
        collection_id = self.env['tf.cf.collection'].search([
            ('date_from', '<=', date_from),
            ('date_to', '>=', date_from),
        ], limit=1)

        if not collection_id:
            return line_ids

        while date_from <= self.date_to:
            if date_from == self.date_from:
                init_bal = collection_id.get_initial_balance()
            else:
                init_bal -= collection_id.get_payments_aof_date(date_from)

            line_ids.append(projection_line_obj.create({
                'type': 'collection',
                'date': date_from,
                'amount': init_bal,
            }).id)
            date_from += relativedelta(days=1)

        return line_ids
