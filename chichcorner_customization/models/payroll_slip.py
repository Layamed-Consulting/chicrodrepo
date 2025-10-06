from odoo import models, api,fields, _

class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    brut_imposable = fields.Monetary(compute='_compute_imposable_wages', store=True, string="Brut Imposable")
    net_imposable = fields.Monetary(compute='_compute_imposable_wages', store=True, string="Net Imposable")
    cnss_total = fields.Monetary(compute='_compute_imposable_wages', store=True, string="CNSS")
    ir_brut = fields.Monetary(compute='_compute_imposable_wages', store=True, string="IR Brut")
    jours_travailles = fields.Float(compute='_compute_imposable_wages', store=True, string="Jours Travaillés")
    jours_conges = fields.Float(compute='_compute_imposable_wages', store=True, string="Jours Congé")

    @api.depends('line_ids.total', 'worked_days_line_ids.number_of_days')
    def _compute_imposable_wages(self):
        line_values = (self._origin)._get_line_values(['GROSS_TAXABLE', 'SAL_Net_Imp', 'E_CNSS', 'GROSS_INCOME_TAX'])
        for payslip in self:
            payslip.brut_imposable = line_values['GROSS_TAXABLE'][payslip._origin.id]['total']
            payslip.net_imposable = line_values['SAL_Net_Imp'][payslip._origin.id]['total']
            payslip.cnss_total = line_values['E_CNSS'][payslip._origin.id]['total']
            payslip.ir_brut = line_values['GROSS_INCOME_TAX'][payslip._origin.id]['total']
            jours_travail = payslip.worked_days_line_ids.filtered(
                lambda l: l.work_entry_type_id.code in ['WORK', 'WORK100', 'ATT']
            )
            payslip.jours_travailles = sum(jours_travail.mapped('number_of_days'))

            # Calculer la somme des jours de congé (types LEAVE, LEAVES, etc.)
            jours_conge = payslip.worked_days_line_ids.filtered(
                lambda l: l.work_entry_type_id.code in ['LEAVE110', 'LEAVE', 'SICK', 'COMP_LEAVE', 'LEAVE90']
            )
            payslip.jours_conges = sum(jours_conge.mapped('number_of_days'))

    def action_print_custom_payslip(self):
        """Print the custom payslip report"""
        return self.env.ref('chichcorner_customization.custom_payslip_report').report_action(self)

    def action_print_bulletin_paie(self):
        """Print the custom payslip report"""
        return self.env.ref('chichcorner_customization.custom_bulettin_report').report_action(self)

