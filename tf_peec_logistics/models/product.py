from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_trip_expense = fields.Boolean('Is a Trip Expense')
