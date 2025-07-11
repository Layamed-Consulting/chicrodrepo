from odoo import models, fields

class BlackList(models.Model):
    _name = 'black.list'
    _description = 'Black List'

    cin = fields.Char(string="CIN", required=True, help="Identity Number")
    client_name = fields.Char(string="Client Name", required=True, help="Name of the Client")
    status = fields.Selection(
        [('active', 'OK'), ('inactive', 'KO')],
        string="Statut",
        help="Status of the blacklisting"
    )
    commentaire = fields.Text(string="Commentaire", help="Additional notes about the client")
