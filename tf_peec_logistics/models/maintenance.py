from odoo import api, fields, models


class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    delivery_order_id = fields.Many2one('logistics.delivery.order', 'Delivery Order')
    trip_log_id = fields.Many2one('logistics.log.trip', 'Trip Log')
