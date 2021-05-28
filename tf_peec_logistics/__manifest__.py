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
    'name': 'Peaksun Logistics',
    'version': '13.0.1.2',
    'category': 'Peaksun Customization',
    'summary': 'Logistics',
    'author': 'Taliform Inc.',
    'website': 'https://www.taliform.com',
    'depends': [
        'stock',
        'tf_peec_fleet',
        'tf_peec_maintenance',
        'tf_peec_partner',
        'web_notify',
        'web_m2x_options'
    ],
    'data': [
        'security/logistics_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/mail_data.xml',
        'data/logistics_data.xml',
        'views/logistics_delivery_views.xml',
        'views/logistics_atw_views.xml',
        'views/logistics_journey_plan_views.xml',
        'views/logistics_log_views.xml',
        'views/logistics_target_sucf_views.xml',
        'views/logistics_dashboard_group_views.xml',
        'views/res_config_settings_views.xml',
        'views/logistics_menu_views.xml',
        'views/res_partner_view.xml',
        'views/employee_view.xml',
        'views/fleet_view.xml',
        'views/product_views.xml',
        'views/maintenance_view.xml',
        'wizard/logistics_delivery_order_assign_views.xml',
        'wizard/logistics_delivery_order_start_trip_views.xml',
        'wizard/logistics_delivery_order_end_trip_views.xml'
    ],
    'installable': True,
    'auto_install': False,
}
