# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
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
    'name': 'Trial Balance',
    'version': '13.0.1.0',
    'category': 'Accounting/Accounting',
    'author': 'Taliform Inc.',
    'website': 'https://www.taliform.com',
    'depends': [
        'account',
        'tf_ph_reports',
        'tf_ph_payment'
    ],
    'data': [
        'views/account_invoice_view.xml',
        # 'views/account_move_view.xml',
        'views/account_payment_view.xml',
        'views/tf_ph_trial_balance_view.xml',
        'security/ir.model.access.csv',
        'security/ph_trial_balance_security.xml',
        'data/account_type_report.xml'],
    'installable': True,
    'active': False,
    'auto_install': False,
}