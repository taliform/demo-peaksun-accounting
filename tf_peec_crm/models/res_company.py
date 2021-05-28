from odoo import models, fields


class Company(models.Model):
    _inherit = 'res.company'

    bag_currency_id = fields.Many2one('res.currency', 'Bags Currency')
