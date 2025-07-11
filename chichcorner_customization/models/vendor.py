from odoo import fields, models
import logging
_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
  _inherit = 'pos.order'

  suggestion = fields.Char(string='Vendor name', readonly=True, help='Vendor name')
  stan = fields.Char(string='STAN Number', readonly=True, help='System Trace Audit Number for the journal entry.')
  identite_number = fields.Char(string="Identité Number")
  cheque_number = fields.Char(string="Numero Chèque")
  banque = fields.Selection([
    ('attijari_wafabank', 'ATTIJARI WAFABANK'),
    ('banque_populaire', 'Banque Populaire'),
    ('SGMB', 'Socièté Général'),
    ('LPB', 'AL BARID BANK'),
    ('BCP', 'BANQUE CENTRALE POPULAIRE'),
    ('BMCE', 'BANK OF AFRICA'),
    ('BMCI', 'BANQUE MAROCAINE POUR LE COMMERCE ET L’INDUSTRIE'),
    ('CADM', 'CREDIT AGRICOLE DU MAROC'),
    ('CFG', 'CFG BANK'),
    ('CDM', 'CREDIT DU MAROC'),
    ('CITI', 'CITIBANK MAGHREB'),
    ('ABM', 'ARAB BANK MAROC'),
    ('CIH', 'CREDIT IMMOBILIER ET HOTELIER')
  ], string="Banque")
  status = fields.Selection([
    ('ok', 'OK'),
    ('ko', 'KO'),
  ], string="Status", default="ok")
  # New fields for the new payment method
  vir_number = fields.Char(
    string='Numéro du virement',
    help='The number associated with the virtual payment method.'
  )
  num_client = fields.Char(
    string='Num du client',
    help='The client number for the virtual payment method.'
  )
  vir_montant = fields.Float(
    string='Montant',
    help='The amount paid using the virtual payment method.'
  )
  ref_cmd = fields.Char(
    string='Reference de la commande',
    help='Reference of the associated order for the virtual payment.'
  )
  date_commande = fields.Date(
    string='Date Ordre',
    help='The date when the order was placed for the virtual payment.'
  )
  cheque_date = fields.Date(string="Date du Chèque", help="Date of the cheque.")


  def _order_fields(self, ui_order):
    result = super()._order_fields(ui_order)
    _logger.debug("UI Order: %s", ui_order)
    result['suggestion'] = ui_order.get('suggestion')
    result['stan'] = ui_order.get('stan')
    result['identite_number'] = ui_order.get('identite_number')
    result['cheque_number'] = ui_order.get('cheque_number')
    result['banque'] = ui_order.get('banque')
    result['cheque_date'] = ui_order.get('cheque_date')
    # virement part
    result['vir_number'] = ui_order.get('vir_number')
    result['num_client'] = ui_order.get('num_client')
    result['vir_montant'] = ui_order.get('vir_montant')
    result['ref_cmd'] = ui_order.get('ref_cmd')
    result['date_commande'] = ui_order.get('date_commande')
    return result



