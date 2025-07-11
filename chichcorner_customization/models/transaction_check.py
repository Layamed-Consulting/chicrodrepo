from odoo import models, fields,api,_
import datetime
from datetime import datetime, time
import logging

_logger = logging.getLogger(__name__)


class TransactionCheck(models.Model):
    _name = "transaction.check"
    _description = "Check Transaction"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    date = fields.Date(string="Date", required=True)
    magasin_name = fields.Many2one(
        'pos.config',
        string="Magasin",
        required=True,
        domain=[('id', '!=', False)]
    )
    status = fields.Selection([
        ('concrétiser', 'Concrétisé'),
        ('done', 'Done'),
        ('comptabilisé', 'Comptabilisé')
    ], string="Status", default='done')

    transaction_ids = fields.One2many("transaction.session", "check_id", string="Relevés")

    total_expected = fields.Float(
        string="Total Expected",
        compute="_compute_totals",
        store=True
    )
    total_counted = fields.Float(
        string="Total Counted",
        compute="_compute_totals",
        store=True
    )

    @api.depends('transaction_ids', 'transaction_ids.expected', 'transaction_ids.counted_cash')
    def _compute_totals(self):
        for record in self:
            record.total_expected = sum(record.transaction_ids.mapped('expected'))
            record.total_counted = sum(record.transaction_ids.mapped('counted_cash'))

    @api.onchange('date', 'magasin_name')
    def _filter_transactions_by_date(self):
        if self.date and self.magasin_name:
            _logger.info(f"Filtering transactions for date: {self.date}")


            start_datetime = datetime.combine(self.date, time.min)
            end_datetime = datetime.combine(self.date, time.max)

            _logger.info(f"Search range: {start_datetime} to {end_datetime}")

            sessions = self.env['pos.session'].search([
                ('config_id', '=', self.magasin_name.id),
                ('start_at', '<=', end_datetime),
                ('stop_at', '>=', start_datetime),
            ])

            _logger.info(f"Found {len(sessions)} sessions")

            transactions = self.env['transaction.session'].search([
                ('session_id', 'in', sessions.ids),
                ('check_id', '=', False),
                ('expected', '!=', 0)
            ])

            _logger.info(f"Found {len(transactions)} transactions")
            for trans in transactions:
                _logger.info(f"Transaction ID: {trans.id}, Session: {trans.session_id.name}")

            self.transaction_ids = [(5, 0, 0)]
            _logger.info("Cleared existing transaction records")

            if transactions:
                self.transaction_ids = [(4, transaction.id) for transaction in transactions]
                _logger.info(f"Added {len(transactions)} transactions to transaction_ids")
            else:
                _logger.warning("No transactions found for the selected date")

    def write(self, vals):
        _logger.info(f"Writing values to transaction.check: {vals}")
        return super(TransactionCheck, self).write(vals)

    def print_pdf_report(self):
        return self.env.ref('chichcorner_customization.transaction_check_pdf_report').report_action(self)