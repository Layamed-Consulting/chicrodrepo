from odoo import models, fields
import logging
_logger = logging.getLogger(__name__)

class AccountJournal(models.Model):
    _inherit = 'pos.order'

    stan = fields.Char(string='STAN Number',readonly=True, help='System Trace Audit Number for the journal entry.')

    def _order_fields(self, ui_order):
        result = super()._order_fields(ui_order)
        _logger.debug("UI Order: %s", ui_order)  # Log the ui_order for debugging
        result['stan'] = ui_order.get('stan')
        return result
