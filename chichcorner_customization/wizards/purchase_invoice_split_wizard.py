# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseInvoiceSplitWizard(models.TransientModel):
    _name = 'purchase.invoice.split.wizard'
    _description = 'Select which Numero Facture groups to invoice'

    order_ids = fields.Many2many('purchase.order', string='Purchase Orders', readonly=True)
    line_ids = fields.One2many(
        'purchase.invoice.split.wizard.line', 'wizard_id', string='Groups'
    )

    def action_generate_invoices(self):
        self.ensure_one()
        selected = self.line_ids.filtered(
            lambda l: l.to_generate and not l.already_invoiced
        )
        if not selected:
            raise UserError(_(
                "Please select at least one numero de facture to generate."
            ))

        restrict_map = {}
        for line in selected:
            restrict_map.setdefault(line.order_id.id, set()).add(line.numero_facture)

        orders = self.env['purchase.order'].browse(list(restrict_map.keys()))
        moves = orders._create_bills(restrict_map=restrict_map)

        return orders.action_view_invoice(moves)


class PurchaseInvoiceSplitWizardLine(models.TransientModel):
    _name = 'purchase.invoice.split.wizard.line'
    _description = 'Numero Facture group line'
    _order = 'order_id, numero_facture'

    wizard_id = fields.Many2one(
        'purchase.invoice.split.wizard', required=True, ondelete='cascade'
    )
    order_id = fields.Many2one('purchase.order', required=True, readonly=True)
    numero_facture = fields.Char(readonly=True)
    currency_id = fields.Many2one(related='order_id.currency_id', readonly=True)
    amount_total = fields.Monetary(
        readonly=True, currency_field='currency_id',
        string='Total (HT)',
    )
    already_invoiced = fields.Boolean(readonly=True, string='Déjà facturé')
    to_generate = fields.Boolean(string='Générer', default=True)
    state = fields.Selection(
        [('to_invoice', 'To invoice'), ('invoiced', 'Déjà facturé')],
        compute='_compute_state', store=True,
    )

    @api.depends('already_invoiced')
    def _compute_state(self):
        for rec in self:
            rec.state = 'invoiced' if rec.already_invoiced else 'to_invoice'

    @api.onchange('already_invoiced')
    def _onchange_already_invoiced(self):
        for rec in self:
            if rec.already_invoiced:
                rec.to_generate = False
