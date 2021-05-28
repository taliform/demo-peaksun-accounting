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

from odoo import models


class TfCfUndepositedPdc(models.TransientModel):
    _name = 'tf.cf.undeposited.pdc'
    _description = "Generate Internal Transfer Cash Flow"
    _inherit = 'tf.cf.projection'


class TfCfUndeposited(models.TransientModel):
    _name = 'tf.cf.undeposited'
    _description = "Generate Internal Transfer Cash Flow"
    _inherit = 'tf.cf.projection'

    def action_generate(self):
        # Init
        return_id = self.env.context.get('return_id', False)
        projection_line_obj = self.env['tf.cf.projection.line']
        line_ids = []

        # Search for payments
        payment_ids = self.env['account.payment'].search([
            ('state', '!=',  ['draft', 'cancelled']),
            ('payment_date', '>=', self.date_from),
            ('payment_date', '<=', self.date_to),
            ('has_invoices', '=', True),
            ('for_undeposited_payment', '=', True),
            ('is_transferred', '=', False),
            ('pdc_id', '=', False)
        ])

        for payment_id in payment_ids:
            if payment_id.payment_method_type == 'adjustment':
                for payment_inv_line_id in payment_id.payment_inv_line_ids.filtered_domain([('allocation', '>', 0)]):
                    line_ids.append(projection_line_obj.create({
                        'type': 'internal',
                        'move_id': payment_inv_line_id.invoice_id.id,
                        'date': payment_id.payment_date,
                        'amount': payment_inv_line_id.allocation,
                        'journal_id': payment_id.journal_id.id,
                        'payment_id': payment_id.id,
                        }).id)
            else:
                for invoice_id in payment_id.invoice_ids:
                    line_ids.append(projection_line_obj.create({
                        'type': 'internal',
                        'move_id': invoice_id.id,
                        'date': payment_id.payment_date,
                        'amount': payment_id.amount,
                        'journal_id': payment_id.journal_id.id,
                        'payment_id': payment_id.id
                    }).id)

        if not return_id:
            return {
                'name': "Undeposited Payments: %s - %s" % (self.date_from, self.date_to),
                'type': 'ir.actions.act_window',
                'view_mode': 'pivot,tree',
                'domain': [('id', 'in', line_ids)],
                'res_model': 'tf.cf.projection.line',
            }
        else:
            return line_ids
