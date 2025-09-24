from odoo import models, api, _

class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def action_print_custom_payslip(self):
        """Print the custom payslip report"""
        return self.env.ref('chichcorner_customization.custom_payslip_report').report_action(self)
