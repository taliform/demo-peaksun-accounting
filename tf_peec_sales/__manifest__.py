# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2021 Taliform Inc.
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
    'name': 'Peaksun Sales Customizations',
    'version': '13.0.1.6',
    'category': 'Peaksun Customization',
    'summary': 'Peaksun customizations for Sales',
    'author': 'Taliform Inc.',
    'website': 'https://www.taliform.com',
    'depends': [
        'sale',
        'sales_team',
        'sale_stock',
        'tf_peec_logistics',
        'tf_peec_purchase',
        'tf_ph_partner_tax',
        # 'tf_peec_credit_line_management',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'wizard/rate_computation_wizard_views.xml',
        'wizard/delivery_order_wizard_views.xml',
        'wizard/so_line_offhire_wizard_views.xml',
        'reports/cement_delivery_report_layout.xml',
        'reports/cement_delivery_report.xml',
        'views/report_template_config.xml',
        'views/sale_location_views.xml',
        'views/sale_order_views.xml',
        'views/sale_cement_views.xml',
        'views/sale_agreement_views.xml',
        'views/sale_rate_views.xml',
        'views/sale_hauling_views.xml',
        'views/sale_offhire_views.xml',
        'views/delivery_order_views.xml',
        'views/atw_views.xml',
        'wizard/delivery_report_wizard_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
