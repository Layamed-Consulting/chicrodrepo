from odoo import models,api,_


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def get_bon_de_sortie_data(self):

        data = []
        for move in self.move_ids_without_package:
            data.append({
                'product': f"[{move.product_id.default_code or ''}] {move.product_id.name}",
                'quantity': move.quantity,
                'delivered': move.quantity
            })
        return data


class BonDeSortieReport(models.AbstractModel):
    _name = 'report.chichcorner_customization.report_bon_de_sortie'
    _description = 'Bon De Sortie Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['stock.picking'].browse(docids)
        return {
            'docs': docs,
        }