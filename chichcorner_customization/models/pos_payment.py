from odoo import fields, models,api

class PosPayment(models.Model):
    _inherit = 'pos.payment'

    stan = fields.Char(
        string='STAN Number',
        related='pos_order_id.stan',
        readonly=True,
        help='System Trace Audit Number from the associated POS order.'
    )
    identite_number = fields.Char(
        string='CIN',
        related='pos_order_id.identite_number',
        readonly=True,
        help='System Trace Audit Number from the associated POS order.'
    )
    cheque_number = fields.Char(
        string='Check number',
        related='pos_order_id.cheque_number',
        readonly=True,
        help='System Trace Audit Number from the associated POS order.'
    )
    banque = fields.Selection(
        string='Banque',
        related='pos_order_id.banque',
        readonly=True,
        help='System Trace Audit Number from the associated POS order.'
    )
    cheque_date = fields.Date(
        string='Date du chèque',
        related='pos_order_id.cheque_date',
        readonly=True,
        help='The date associated with the cheque payment from the POS order.'
    )
    # Nouveaux champs pour le paiement virtuel
    vir_number = fields.Char(
        string='Numéro de Virement',
        related='pos_order_id.vir_number',
        readonly=True,
        help='Numéro de virement associé à la commande POS.'
    )
    num_client = fields.Char(
        string='Numéro Client',
        related='pos_order_id.num_client',
        readonly=True,
        help='Numéro de client associé à la commande POS.'
    )
    vir_montant = fields.Float(
        string='Montant du Virement',
        related='pos_order_id.vir_montant',
        readonly=True,
        help='Montant associé au virement virtuel.'
    )
    ref_cmd = fields.Char(
        string='Référence de Commande',
        related='pos_order_id.ref_cmd',
        readonly=True,
        help='Référence de commande associée à la commande POS.'
    )
    date_commande = fields.Date(
        string='Date de Commande',
        related='pos_order_id.date_commande',
        readonly=True,
        help='Date de la commande POS associée.'
    )
    @api.depends('payment_method_id')
    def _compute_field_visibility(self):
        for record in self:
            method = record.payment_method_id.name
            record.show_stan = method == 'Carte Bancaire'
            record.show_cheque_fields = method in ['Chèque', 'Chèque MDC']
            record.show_date = method == 'Chèque MDC'
            record.show_identite = method in ['Chèque MDC', 'Chèque']
            # virement part
            record.show_vir_number = method == 'Virement'
            record.show_num_client = method == 'Virement'
            record.show_vir_montant = method == 'Virement'
            record.show_ref_cmd = method == 'Virement'
            record.show_date_commande = method == 'Virement'

    show_stan = fields.Boolean(compute='_compute_field_visibility')
    show_cheque_fields = fields.Boolean(compute='_compute_field_visibility')
    show_date = fields.Boolean(compute='_compute_field_visibility')
    show_identite = fields.Boolean(compute='_compute_field_visibility')
    # virement part
    show_vir_number = fields.Boolean(compute='_compute_field_visibility')
    show_num_client = fields.Boolean(compute='_compute_field_visibility')
    show_vir_montant = fields.Boolean(compute='_compute_field_visibility')
    show_ref_cmd = fields.Boolean(compute='_compute_field_visibility')
    show_date_commande = fields.Boolean(compute='_compute_field_visibility')


