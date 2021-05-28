# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Joshua <joshua@taliform.com>
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
import base64
import hashlib

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    @api.model
    def render_qweb_pdf(self, res_ids=None, data=None):
        """ Hook into this function to detect when Billing Statement is generated. """
        pdf_content, file_type = super(IrActionsReport, self).render_qweb_pdf(res_ids, data)

        if self.report_name == 'tf_peec_bir_cas.delivery_receipt':
            StockPicking = self.env['stock.picking']
            pdf_encoded = base64.b64encode(pdf_content)
            h = hashlib.md5()
            h.update(pdf_content)
            hash_code = h.hexdigest()
            for picking_id in res_ids:
                picking = StockPicking.browse([picking_id])
                if picking.picking_type_code == 'outgoing':
                    vals = {
                        'delivery_receipt': pdf_encoded,
                        'hash_code': hash_code
                    }
                    picking.write(vals)

        if self.report_name == 'tf_peec_bir_cas.report_billing_statement':
            AccountMove = self.env['account.move']
            pdf_encoded = base64.b64encode(pdf_content)
            h = hashlib.md5()
            h.update(pdf_content)
            hash_code = h.hexdigest()
            for move_id in res_ids:
                move = AccountMove.browse([move_id])
                vals = {
                    'date_generated': fields.Date.today(),
                    'generated_by': self.env.uid,
                    'billing_statement': pdf_encoded,
                    'hash_code': hash_code
                }
                if not move.billing_statement_id:
                    vals['invoice_id'] = move.id
                    bs = self.env['account.billing.statement'].create(vals)
                    move.write({'billing_statement_id': bs.id})
                else:
                    move.billing_statement_id.write(vals)

        return pdf_content, file_type
