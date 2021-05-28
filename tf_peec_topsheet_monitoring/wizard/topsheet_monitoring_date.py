from odoo import fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import datetime


class TopsheetMonitoringMoveStage(models.TransientModel):
    _name = 'topsheet.monitoring.move.stage'
    _description = 'Topsheet Monitoring Stage Wizard'

    movement_date = fields.Date(required=True, default=datetime.today())
    topsheet_id = fields.Many2one('account.topsheet', string='Topsheet')
    remarks = fields.Char('Remarks')
    to_stage = fields.Many2one('account.topsheet.stages', string='To Stage')

    def action_move(self):
        for rec in self:
            rec.topsheet_id.write({'move_remarks': rec.remarks, 'stage_id': rec.to_stage.id})
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

