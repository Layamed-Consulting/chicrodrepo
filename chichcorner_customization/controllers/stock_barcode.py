from odoo import http
from odoo.http import request
from odoo.addons.stock_barcode.controllers.stock_barcode import StockBarcodeController


class CustomStockBarcodeController(StockBarcodeController):

    def _try_open_product_location(self, barcode):
        """ Inherit the function to trigger action_print_label when opening the view. """
        result = request.env['product.product'].search_read([
            ('barcode', '=', barcode),
        ], ['id', 'display_name'], limit=1)

        if result:
            tree_view_id = request.env.ref('stock.view_stock_quant_tree').id
            kanban_view_id = request.env.ref('stock_barcode.stock_quant_barcode_kanban_2').id

            return {
                'action': {
                    'name': result[0]['display_name'],
                    'res_model': 'stock.quant',
                    'views': [(tree_view_id, 'list'), (kanban_view_id, 'kanban')],
                    'type': 'ir.actions.act_window',
                    'domain': [('product_id', '=', result[0]['id'])],
                    'context': {
                        'search_default_internal_loc': True,
                        'trigger_print_button': True
                    },
                },
            }
