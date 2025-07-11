from odoo import models, fields

class TransactionSession(models.Model):
    _name = "transaction.session"
    _description = "Transaction Session"

    session_id = fields.Many2one("pos.session", string="POS Session", required=True)
    notes = fields.Text(string="Closing Notes")
    cashier_name = fields.Char(string="Cashier Name")
    store_name = fields.Char(string="Store/Magasin Name")
    counted_cash = fields.Float(string="Counted")
    payment_differences = fields.Float(string="Payment Differences")
    expected = fields.Float(string="Expected Amount")
    close_time = fields.Datetime(string="Close Time", default=fields.Datetime.now)
    payment_method_id = fields.Many2one("pos.payment.method", string="Payment Method", required=True)
    payment_method_name = fields.Char(string="Payment Method Name")

    check_id = fields.Many2one("transaction.check", string="Relevés")
