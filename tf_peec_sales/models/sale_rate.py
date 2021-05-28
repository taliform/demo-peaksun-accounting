# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2021 Taliform Inc.
#
# Author: Ana Trajano <ana@taliform.com>
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
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleRateTable(models.Model):
    _name = 'sale.rate'
    _description = "Rate Table"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    _TYPES = [('cement', 'Cement Sales'),
              ('hauling', 'Hauling')]

    # visibility true if cement salestype
    name = fields.Char(help="Indicates a name to differentiate the Rate Table")
    dp_line_ids = fields.One2many('sale.rate.dp', 'rate_table_id', 'DP Lines')
    rate_line_ids = fields.One2many('sale.rate.rate', 'rate_table_id', 'Rate Lines')
    diesel_cost = fields.Float('Diesel Cost', track_visibility='onchange', help="Indicates the Diesel Cost parameter")
    lt_km_factor = fields.Float('Liters / Km Factor', help="Indicates the Liters / Km Factor parameter",
                                track_visibility='onchange')
    avg_bag_per_trip = fields.Float('Average Bags Per Trip', help="Indicates the Average Bags Per Trip parameter",
                                    track_visibility='onchange')
    vat_rate = fields.Float('VAT Rate', track_visibility='onchange', help="Indicates the VAT Rate parameter")
    toll_fee = fields.Float('Toll Fee', track_visibility='onchange', help="Indicates the Toll Fee parameter")
    round_trip = fields.Float('Round Trip', track_visibility='onchange', help="Indicates the Round Trip parameter")
    maintenance_factor = fields.Float('Maintenance Factor', track_visibility='onchange',
                                      help="Indicates the Maintenance Factor parameter")
    tire_cost = fields.Float('Tire Cost (w/o VAT)', track_visibility='onchange', help="Indicates the Tire Cost "
                                                                                      "(w/o VAT) parameter")
    tire_qty = fields.Float('Tire Quantity', track_visibility='onchange', help="Indicates the Tire Quantity parameter")
    tire_lifespan = fields.Float('Tire Lifespan', track_visibility='onchange', help="Indicates the Tire Lifespan "
                                                                                    "parameter")
    tire_factor = fields.Float('Tire Factor', track_visibility='onchange', help="Indicates the Tire Factor parameter")
    salary_factor = fields.Float('Salary Factor', track_visibility='onchange', help="Indicates the Salary Factor "
                                 "parameter")
    avg_trip_per_month = fields.Float('Avg. Trips per Month', track_visibility='onchange', help="Indicates the Avg. "
                                                                                                "Trips per Month "
                                                                                                "parameter")
    er_govt_cont = fields.Float('ER Gov’t Contribution', track_visibility='onchange', help="Indicates the ER Gov’t "
                                                                                           "Contribution parameter")
    misc = fields.Float('Misc', track_visibility='onchange', help="Indicates the Misc parameter")
    fx_truck_misc = fields.Float('Fixed Truck Misc', track_visibility='onchange', help="Indicates the Fixed Truck "
                                                                                       "Misc parameter")
    fx_admin = fields.Float('Fixed Admin', track_visibility='onchange', help="Indicates the Fixed Admin parameter")

    type = fields.Selection(_TYPES, default='cement', track_visibility='onchange', help="Indicates the type of "
                                                                                        "Rate Table")
    # visibility true if hauling type
    rate_table_line_ids = fields.Many2one('sale.rate.line', track_visibility='onchange', help="Indicates the table "
                                                                                              "of Rate Table Lines")
    currency_id = fields.Many2one('res.currency', 'Currency', required=True,
                                  default=lambda self: self.env.company.currency_id.id)

    # use for computation
    rate_id_comp = fields.Many2one('sale.rate.rate', 'Rate', copy=False)
    km_comp = fields.Float('Km', copy=False)
    diesel_comp = fields.Float('Diesel', copy=False)
    maintenance_comp = fields.Float('Maintenance', copy=False)
    tires_comp = fields.Float('Tires', copy=False)
    driver_comp = fields.Float('Driver', copy=False)
    helper_comp = fields.Float('Helper', copy=False)
    salary_misc_comp = fields.Float('Salary - Misc', copy=False)
    toll_fee_comp = fields.Float('Toll Fee', copy=False)
    truck_ins_reg_comp = fields.Float('Truck Ins/Reg', copy=False)
    overhead_admin_comp = fields.Float('Overhead Admin', copy=False)
    total_vc_comp = fields.Float('Total VC', copy=False)
    total_fc_comp = fields.Float('Total FC', copy=False)
    total_vcfc_comp = fields.Float('Total VC & FC', copy=False)
    cost_bag_comp = fields.Float('Cost / Bag', copy=False)
    based_rate_comp = fields.Float('Based on Rate', copy=False)
    rate_total_comp = fields.Float('Total (w/ VAT)', copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        records = super(SaleRateTable, self).create(vals_list)
        for rec in records:
            if rec.type == 'cement':
                if rec.tire_lifespan <= 0:
                    raise UserError(_('Please indicate the Tire Lifespan to compute Tires.'))

                if rec.avg_trip_per_month <= 0:
                    raise UserError(_('Please indicate the Avg. Trips per Month to compute Salary Misc.'))

                if rec.avg_bag_per_trip <= 0:
                    raise UserError(_('Please indicate the Average Bags Per Trip to compute Cost / Bag.'))
        return records

    def compute_rate(self):
        for rec in self:
            # Initial Vals
            dp_driver_rate = dp_helper_rate = vat = 0.0

            # Input
            km = rec.km_comp
            rate = rec.rate_id_comp.rate

            # Start Computation
            # Diesel = KM * Diesel Cost * Liters / Km Factor * Round Trip
            rec.diesel_comp = km * rec.diesel_cost * rec.lt_km_factor * rec.round_trip

            # Maintenance = Diesel * Maintenance Factor
            rec.maintenance_comp = rec.diesel_comp * rec.maintenance_factor

            # Tires = KM * ((Tire Cost * Tire Quantity) / Tire Lifespan) * Tire Factor
            if rec.tire_lifespan <= 0:
                raise UserError(_('Please indicate the Tire Lifespan to compute Tires.'))
            else:
                rec.tires_comp = km * ((rec.tire_cost * rec.tire_qty) / rec.tire_lifespan) * rec.tire_factor

            # Driver = DP Rate[Driver] * Average Bags per Trip
            # Helper = DP Rate[Helper]
            if rec.dp_line_ids:
                for dp_id in rec.dp_line_ids:
                    if dp_id.km_from <= km <= dp_id.km_to:
                        dp_driver_rate = dp_id.driver_rate
                        dp_helper_rate = dp_id.helper_rate
                        break
                rec.driver_comp = dp_driver_rate * rec.avg_bag_per_trip
                rec.helper_comp = dp_helper_rate

            # Salary Misc = ((((Driver + Helper) * Salary Factor) + ER Gov't Contribution) / Avg. Trips per Month)
            # + Misc
            if rec.avg_trip_per_month <= 0:
                raise UserError(_('Please indicate the Avg. Trips per Month to compute Salary Misc.'))
            else:
                rec.salary_misc_comp = ((((rec.driver_comp + rec.helper_comp) * rec.salary_factor) + rec.er_govt_cont) /
                                        rec.avg_trip_per_month) + rec.misc

            # Toll Fee = Toll Fee
            rec.toll_fee_comp = rec.toll_fee

            # Total VC = Diesel + Maintenance + Tires + Driver + Helper + Salary Misc + Toll Fee
            rec.total_vc_comp = rec.diesel_comp + rec.maintenance_comp + rec.tires_comp + rec.driver_comp + \
                                rec.helper_comp + rec.salary_misc_comp + rec.toll_fee_comp

            # Truck Ins/Reg = Fixed Truck Misc
            rec.truck_ins_reg_comp = rec.fx_truck_misc

            # Overhead Admin = Fixed Admin
            rec.overhead_admin_comp = rec.fx_admin

            # Total FC = Truck Ins/Reg + Overhead Admin
            rec.total_fc_comp = rec.truck_ins_reg_comp + rec.overhead_admin_comp

            # Total VC & FC = Total VC + Total FC
            rec.total_vcfc_comp = rec.total_vc_comp + rec.total_fc_comp

            # Cost / Bag = Total VC & FC / Average Bags Per Trip
            if rec.avg_bag_per_trip <= 0:
                raise UserError(_('Please indicate the Average Bags Per Trip to compute Cost / Bag.'))
            else:
                rec.cost_bag_comp = rec.total_vcfc_comp / rec.avg_bag_per_trip

            # Based on Rate = Cost / Bag * (1+(Selected Rate/100))
            rec.based_rate_comp = rec.cost_bag_comp * (1 + (rate/100))

            # VAT = Based on Rate * (VAT Rate/100)
            vat = rec.based_rate_comp * (rec.vat_rate/100)

            # Rate Total = Based on Rate + VAT
            rec.rate_total_comp = rec.based_rate_comp + vat
        return {'based_on_rate': rec.based_rate_comp,
                'total_with_vat': rec.rate_total_comp}


class SaleRateTableLine(models.Model):
    _name = 'sale.rate.line'
    _description = "Rate Table Line"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'rate_table_id'

    rate_table_id = fields.Many2one('sale.rate', 'Rate Table', ondelete='cascade')
    cement_plant_id = fields.Many2one('res.partner', 'Cement Plant', track_visibility='onchange',
                                      help="Indicates the Cement Plant")
    batching_plant_id = fields.Many2one('res.partner', 'Batching Plant', track_visibility='onchange',
                                        help="Indicates the Batching Plant")
    distance = fields.Float(track_visibility='onchange')
    rate = fields.Monetary(track_visibility='onchange', help="Indicates the agreed rate")
    currency_id = fields.Many2one(related='rate_table_id.currency_id')


class SaleRateDP(models.Model):
    _name = 'sale.rate.dp'
    _description = "Sale Rate Table - DP"

    rate_table_id = fields.Many2one('sale.rate', 'Rate Table', ondelete='cascade')
    km_from = fields.Float('Km From', help="Indicates the minimum range of KM for the DP rate")
    km_to = fields.Float('Km To', help="Indicates the maximum range of KM for the DP rate")
    driver_rate = fields.Float('Driver Rate', help="Indicates the Driver rate for the KM range")
    helper_rate = fields.Float('Helper Rate', help="Indicates the Helper rate for the KM range")


class SaleRate(models.Model):
    _name = 'sale.rate.rate'
    _description = "Sale Rate"
    _rec_name = 'rate'

    rate_table_id = fields.Many2one('sale.rate', 'Rate Table')
    rate = fields.Float(help="Indicates the Rate")

