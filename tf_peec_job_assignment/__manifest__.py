# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2021 Taliform Inc.
#
# Author: Benjamin Cerdena Jr <benjamin@taliform.com>
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
    'name': 'Peaksun - Temporary Job Assignment',
    'version': '13.0.1.0',
    'category': 'Peaksun Customization',
    'summary': 'Create a temporary job assignment for driver/helper employees.',
    'author': 'Taliform Inc.',
    'website': 'https://taliform.com',
    'depends': [
        'hr',
        'ss_hris_compben',
    ],
    'data': [
        'security/job_assignment_security.xml',
        'security/ir.model.access.csv',
        'data/tf_peec_job_assignment_data.xml',
        'wizard/tf_hr_job_assignment_approve_wizard_view.xml',
        'wizard/tf_hr_job_assignment_logoff_wizard_view.xml',
        # 'wizard/tf_hr_job_assignment_sa_wizard_view.xml',
        'views/config_view.xml',
        'views/hr_job_assignment_view.xml',
        'views/hr_job_assignment_menu.xml',
            ],
    'installable': True,
    'auto_install': False,
}
