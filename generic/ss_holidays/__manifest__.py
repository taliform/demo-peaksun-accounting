# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Allen Guarnes <allen@taliform.com>
# V13 Porting: Martin Perez <martin@taliform.com>
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
    'name': "Holiday Calendar",
    'version': '13.0.1.0',
    'summary': """Manage holidays""",
    'author': "Taliform Inc.",
    'website': 'http://www.taliform.com',
    'category': 'Taliform Apps',
    'depends': ['calendar'],
    'data': ['data/ss_holiday_type.xml',
             'views/ss_holidays_views.xml',
             'views/res_config_settings_view.xml',
             'security/ir.model.access.csv'
             ],
    'auto_install': False,
}
