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
    'name': 'BIR Forms',
    'summary': 'MAP, SAWT, Form 1601-E, Form 2307',
    'category': 'Accounting',
    'author': 'Taliform Inc.',
    'website': 'https://www.taliform.com',
    'depends': [
        'account',
        'account_reports',
        'report_py3o',
        'tf_ph_reports',
        'tf_ph_partner_tax'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/tf_ph_bir_security.xml',
        'data/tf_ph_bir_data.xml',
        'views/tf_ph_bir_1601e_view.xml',
        'views/tf_ph_bir_2307_view.xml',
        'views/tf_ph_bir_alphalist_view.xml',
        'views/account_move_line_view.xml',
        'views/report_template_config.xml',
    ],
    'auto_install': False,
    'installable': True,

}
