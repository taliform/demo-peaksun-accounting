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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.    
#
# You should have received a copy of the GNU Affero General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
##############################################################################
{
    "name": "PH Cash Management",
    "version": "13.0.1.0",
    'category': 'Accounting/Accounting',
    "author": "Talifom Inc.",
    "website": "https://www.taliform.com",
    "depends": [
        'account',
        'account_asset',
        'tf_ph_partner_tax',
        'ss_portal_employee',
        'tf_ph_trial_balance',
        'tf_ph_payment'
    ],
    'data': [
        'data/ir_sequence_data.xml',
        'data/cm_user_groups.xml',
        'security/cm_record_rules.xml',
        'data/mail_data.xml',
        'security/ir.model.access.csv',
        'report/report_replenishment_view.xml',
        'report/report_replenishment_layout_view.xml',
        'report/report_replenishment_layout_wizard_view.xml',
        'views/res_config_settings_view.xml',
        'views/cm_view.xml',
        'views/cm_portal_view.xml',
        'views/cm_invoice_view.xml',
        'views/expense_category_view.xml',
        'wizard/cm_wizard_view.xml',
        'wizard/cm_replenishment_total_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}
