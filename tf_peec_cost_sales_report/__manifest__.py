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
{
    'name': 'Peaksun Cost of Sales Report',
    'version': '13.0.1.0',
    'category': 'Peaksun Customization',
    'summary': 'Peaksun Module for Cost of Sales Report in Accounting',
    'author': 'Taliform Inc.',
    'website': 'http://taliform.com',
    'depends': ['account', 'tf_peec_logistics'],
    'data': [
        'security/ir.model.access.csv',
        'reports/tf_peec_cost_sales_report_view.xml',
        'reports/tf_peec_cost_sales_layout_view.xml',
        'wizard/account_cost_sales_view.xml'
        ],
    'installable': True,
    'auto_install': False,
}
