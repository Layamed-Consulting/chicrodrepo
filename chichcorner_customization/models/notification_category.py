from odoo import models, fields

class NotificationMessage(models.Model):
    _name = 'notification.message'
    _description = 'Notification Message'

    title = fields.Char(string='Title', required=True)
    message = fields.Text(string='Message', required=True)
    severity = fields.Selection([
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ], default='warning', string='Severity')

