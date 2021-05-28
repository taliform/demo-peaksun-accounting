from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_tire = fields.Boolean('Is a Tire')

    @api.onchange('is_tire')
    def _onchange_is_tire(self):
        for product in self:
            if product.is_tire:
                product.tracking = 'serial'
