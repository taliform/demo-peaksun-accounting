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
    'name': 'Peaksun Customer 2307 Enhancement',
    'version': '13.0.1.0',
    'category': 'Peaksun Customization',
    'summary': 'Peaksun customizations for Custumer 2307 in Accounting',
    'author': 'Taliform Inc.',
    'website': 'http://taliform.com',
    'depends': [
        'account',
        'account_reports',
        'tf_ph_bir',
        'tf_ph_partner_tax',
        'tf_ph_payment'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_tax_view.xml',
        'views/reconcile_2307_view.xml',
        'views/res_config_settings_view.xml',
        'wizard/reconcile_2307_generate_adjusting_entry_view.xml'
    ],
    'installable': True,
    'auto_install': False,
}
