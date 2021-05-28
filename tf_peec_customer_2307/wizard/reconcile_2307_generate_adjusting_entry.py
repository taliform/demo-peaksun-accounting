from odoo import fields, models, _
from odoo.exceptions import ValidationError


class Reconcile2307GenerateAdjustingEntry(models.TransientModel):
    _name = 'reconcile.2307.generate.adjusting.entry'
    _description = 'Reconcile 2307 - Generate Adjusting Entry'

    reconcile_id = fields.Many2one('bir.creditable.tax.withheld.reconcile', 'Reconcile (2307)')
    date = fields.Date(required=True)

    def action_generate(self):
        self.ensure_one()

        reconcile = self.reconcile_id
        moves = self.env['account.move']

        for submitted in reconcile.submitted_ids:
            if not self.env.company.reconcile_2307_journal_id:
                raise ValidationError(_('Please set up Reconcile (2307) Journal before proceeding.'))

            if not submitted.atc_id.withholding_tax_account_id:
                raise ValidationError(_('Please set up Withholding Tax Account of ATC Code before proceeding.'))

            credit_account = False
            for r in submitted.atc_id.invoice_repartition_line_ids:
                if r.account_id:
                    credit_account = r.account_id
                    break

            move = self.env['account.move'].create({
                'date': self.date,
                'ref': "%s: %s" % (reconcile.name, submitted.atc_id.name),
                'journal_id': self.env.company.reconcile_2307_journal_id.id,
                'line_ids': [
                    (0, 0, {
                        'account_id': submitted.atc_id.withholding_tax_account_id.id,
                        'debit': submitted.reconciled_amount,
                        'partner_id': reconcile.customer_id.id,
                    }), (0, 0, {
                        'account_id': credit_account.id,
                        'credit': submitted.reconciled_amount,
                        'partner_id': reconcile.customer_id.id,
                    })
                ]
            })
            move.action_post()
            moves = moves | move

        reconcile.write({
            'move_ids': [(6, 0, moves.ids)],
            'state': 'validate',
        })
