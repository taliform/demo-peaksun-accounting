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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################
{
    'name': 'Peaksun BIR Cas',
    'version': '13.0.1.0',
    'category': 'Peaksun Customization',
    'summary': 'Peaksun customizations for BIR Cas Reports',
    'author': 'Taliform Inc.',
    'website': 'https://www.taliform.com',
    'depends': [
        'account',
        'sale',
        'purchase_stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/sales_invoice_data.xml',
        'views/account_billing_statement_view.xml',
        'views/account_move_view.xml',
        'views/res_company_view.xml',
        'report/tf_peec_delivery_receipt_view.xml',
        'report/tf_peec_delivery_recepit_layout_view.xml',
        'report/tf_peec_billing_statement_report_layout_view.xml',
        'report/tf_peec_billing_statement_report_view.xml',
        'report/tf_peec_sales_invoice_report_layout_view.xml',
        'report/tf_peec_sales_invoice_report_view.xml',
        'data/account_move_data.xml',
    ],
    'installable': True,
    'auto_install': False
}
