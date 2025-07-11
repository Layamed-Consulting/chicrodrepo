from odoo import models, fields, api,_

class ProductLabelLayoutInherit(models.TransientModel):
    _inherit = 'product.label.layout'

    print_format = fields.Selection(selection_add=[
        ('etiquette_solde', 'Etiquette Solde')
    ], ondelete={'etiquette_solde': 'set default'})


    def _prepare_report_data(self):
        # Call the super method to retain original behavior
        xml_id, data = super()._prepare_report_data()
        if self.print_format == 'etiquette_solde':
            xml_id = 'chichcorner_customization.report_product_template_label_solde'

        return xml_id, data

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids', [])

        if active_ids and 'pricelist_id' in fields_list:
            if active_model == 'product.template':
                product_tmpl = self.env['product.template'].browse(active_ids[0])
                if product_tmpl.product_variant_ids:
                    pricelist_items = self.env['product.pricelist.item'].search([
                        ('product_tmpl_id', '=', product_tmpl.id)
                    ], limit=1)
                    if pricelist_items:
                        res['pricelist_id'] = pricelist_items[0].pricelist_id.id

            elif active_model == 'product.product':
                product = self.env['product.product'].browse(active_ids[0])
                # Search for pricelist items specific to this product variant
                pricelist_items = self.env['product.pricelist.item'].search([
                    '|',
                    ('product_id', '=', product.id),
                    ('product_tmpl_id', '=', product.product_tmpl_id.id)
                ], limit=1)
                if pricelist_items:
                    res['pricelist_id'] = pricelist_items[0].pricelist_id.id

        return res