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
    'name': 'Peaksun Driver Helper Features',
    'version': '13.0.1.1',
    'category': 'Peaksun Customization',
    'summary': 'Adds driver helper functionalities for Taliform HRIS modules.',
    'author': 'Taliform Inc.',
    'website': 'https://taliform.com',
    'depends': [
        'hr',
        'hr_recruitment',
        'ss_hris_recruitment',
        'ss_hris_contract',
        'tf_peec_logistics',
        'tf_peec_partner',
        'ss_hris_emp_training',
        'ss_hris_schedule',
    ],
    'data': [
        'data/tf_peec_driverhelper_scheduler_data.xml',
        'security/driverhelper_security.xml',
        'security/ir.model.access.csv',
        'views/config_view.xml',
        'views/hr_view.xml',
        'views/res_partner_view.xml',
        'views/hr_logistics_menu.xml',
        'wizard/logistics_delivery_order_assign_views.xml',
            ],
    'installable': True,
    'auto_install': False,
}
