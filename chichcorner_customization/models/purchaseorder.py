from odoo import models, fields, api

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    total_product_qty = fields.Float(
        string="Total Product Quantity",
        compute="_compute_total_product_qty",
        store=True
    )

    total_qty_received = fields.Float(
        string="Total Received Quantity",
        compute="_compute_total_quantities",
        store=True
    )

    @api.depends('order_line.product_qty', 'order_line.qty_received')
    def _compute_total_quantities(self):
        for order in self:
            order.total_product_qty = sum(line.product_qty for line in order.order_line)
            order.total_qty_received = sum(line.qty_received for line in order.order_line)
