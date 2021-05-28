from odoo import api, fields, models


class DeliveryOrder(models.Model):
    _inherit = 'logistics.delivery.order'

    sale_type = fields.Selection(related='sale_id.sale_type', store=True)
    sale_operation = fields.Selection(related='sale_id.sale_operation', store=True)
    hauling_type = fields.Selection(related='sale_id.hauling_type', store=True)
    project_id = fields.Many2one(related='sale_id.project_id', store=True, index=True)


class DeliveryOrderAllocation(models.Model):
    _inherit = 'logistics.delivery.order.allocation'

    project_id = fields.Many2one(related='sale_id.project_id', store=True, index=True)
