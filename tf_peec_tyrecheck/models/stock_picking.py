from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_done(self):
        result = super(StockPicking, self).action_done()

        # # Do TyreCheck processing
        # for picking in self:
        #     if picking.picking_type_code == 'incoming':
        #         for line in picking.move_line_ids:
        #             if line.product_id.is_tire:

        return result
