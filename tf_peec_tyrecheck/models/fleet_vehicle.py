from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    tyrecheck_id = fields.Char('TyreCheck ID')

    @api.constrains('tyrecheck_id')
    def _check_tyrecheck_id(self):
        for vehicle in self:
            if vehicle.tyrecheck_id and vehicle.search_count([('tyrecheck_id', '=', vehicle.tyrecheck_id)]) > 1:
                raise ValidationError(_('TyreCheck ID is already used in a different vehicle.'))
