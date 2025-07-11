# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
import datetime


class ProductProduct(models.Model):
    _inherit = 'product.product'

    collection = fields.Char('Collection', index=True, copy=False)
    style = fields.Char('Style', index=True, copy=False)
    hs_code = fields.Char('HS Code', index=True, copy=False)
    composition = fields.Char('Composition', index=True, copy=False)
    origine_id = fields.Many2one('res.country', 'Origine', index=True, copy=False)
    chic_lot_ids = fields.One2many('chic.lot', 'product_id', string="Lot de fabrication")


class ChicLot(models.Model):
    _name = 'chic.lot'
    _description = 'Lots de fabrication'
    

    date_arrivage = fields.Datetime('Date arrivage', required=True)
    name = fields.Char('N° de lot', required=True, index=True)
    date_peremption = fields.Datetime('Date péremption', required=True, index=True)
    product_id = fields.Many2one('product.product', index=True)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    pricelist_price = fields.Float(
        string="Prix de vente",
        compute="_compute_pricelist_price",
        store=False
    )
    copied_category = fields.Many2one(
        'product.category',
        string="Catégorie de Produit",
        compute='_compute_copied_category',
        store=True
    )

    @api.depends('categ_id')
    def _compute_copied_category(self):
        for product in self:
            product.copied_category = product.categ_id

    def _compute_pricelist_price(self):
        for product in self:
            pricelist_item = self.env['product.pricelist.item'].search([
                ('product_tmpl_id', '=', product.id)
            ], limit=1)
            product.pricelist_price = pricelist_item.fixed_price if pricelist_item else 0.0