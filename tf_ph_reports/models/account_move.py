from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    user_type_id = fields.Many2one('account.account.type', related='account_id.user_type_id', string='Account Type',
                                   index=True, store=True, readonly=True)
