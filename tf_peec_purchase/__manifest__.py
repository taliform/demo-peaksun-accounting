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
    'name': 'Peaksun Purchase Customizations',
    'version': '13.0.1.5',
    'category': 'Peaksun Customization',
    'summary': 'Peaksun customizations for Purchases',
    'author': 'Taliform Inc.',
    'website': 'https://taliform.com',
    'depends': [
        'purchase',
        'purchase_requisition',
        'stock',
        'tf_peec_logistics',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/purchase_data.xml',
        'views/purchase_view.xml',
        'views/purchase_request_view.xml',
        'views/stock_view.xml',
        'views/canvass_sheet_view.xml',
        'views/atw_views.xml',
        'views/product_views.xml',
        'views/res_partner_views.xml',
        'wizard/po_merge_wizard_view.xml',
        'wizard/po_over_under_wizard_view.xml',
        'wizard/purchase_request_wizard_view.xml',
        'wizard/canvass_sheet_wizard_view.xml',
        'reports/cement_over_under_report.xml'
    ],
    # 'css': ['static/src/css/tf_peec_purchase_style.css'],
    'installable': True,
    'auto_install': False,
}
