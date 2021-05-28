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
    'name': 'PH Down Payments',
    'version': '13.0.1.0',
    'category': 'PH Localized Accounting',
    'summary': 'Extension of base down payment functions.',
    'author': 'Taliform Inc.',
    'website': 'http://taliform.com',
    'depends': [
        'account',
        'sale',
        'purchase',
        'tf_ph_payment',
        'tf_ph_cash_advance'
    ],
    'data': [
        'wizard/purchase_advance_payment_view.xml',
        'views/res_config_settings_view.xml',
        'views/purchase_view.xml',
        'views/account_move_view.xml'
    ],
    'installable': True,
    'auto_install': False,
}
