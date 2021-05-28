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
from odoo import models


class ReportAccountAgedReceivable(models.AbstractModel):
    _inherit = "account.aged.receivable"

    def _set_context(self, options):
        ctx = super(ReportAccountAgedReceivable, self)._set_context(options)
        ctx['account_type'] = 'receivable'
        ctx['invoice_type'] = ['out_invoice', 'out_refund']
        return ctx
