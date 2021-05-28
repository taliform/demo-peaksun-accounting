from odoo import models, fields


class Lead(models.Model):
    _inherit = 'crm.lead'

    company_currency = fields.Many2one(string='Currency', related='company_id.bag_currency_id', readonly=True,
                                       relation="res.currency")
