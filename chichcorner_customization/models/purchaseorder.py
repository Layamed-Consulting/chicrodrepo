from odoo import models, fields, api,_
from collections import defaultdict
from odoo.exceptions import UserError
from odoo.tools import float_is_zero

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    total_product_qty = fields.Float(
        string="Total Product Quantity",
        compute="_compute_total_product_qty",
        store=True
    )

    total_qty_received = fields.Float(
        string="Total Received Quantity",
        compute="_compute_total_quantities",
        store=True
    )

    @api.depends('order_line.product_qty', 'order_line.qty_received')
    def _compute_total_quantities(self):
        for order in self:
            order.total_product_qty = sum(line.product_qty for line in order.order_line)
            order.total_qty_received = sum(line.qty_received for line in order.order_line)

    def _get_numero_facture_groups(self):
        """Group each order's real (non-section/note) lines by
        x_studio_numero_facture.

        Returns {order: {numero_facture_key: purchase.order.line recordset}}
        The key is '' for lines with no value (blank), never skipped.
        """
        groups_by_order = {}
        for order in self:
            groups = defaultdict(lambda: self.env['purchase.order.line'])
            for line in order.order_line:
                if line.display_type:
                    continue
                key = line.x_studio_numero_de_facture or ''
                groups[key] |= line
            groups_by_order[order] = dict(groups)
        return groups_by_order

    def _create_bills(self, restrict_map=None):
        """Create vendor bills, one per (order, numero_facture) group.

        :param restrict_map: optional {order_id: set(numero_facture)} used
            by the selection wizard to only generate the chosen groups.
            When None, every group that still has something to invoice is
            processed (this is the direct / no-wizard path).
        :return: account.move recordset of the bills created.
        """
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure'
        )
        invoice_vals_list = []
        groups_by_order = self._get_numero_facture_groups()

        for order, groups in groups_by_order.items():
            if order.company_id not in self.env.user.company_ids:
                raise UserError(_(
                    "You cannot create an invoice for a purchase order that "
                    "belongs to a different company than the one you're "
                    "logged into."
                ))

            # Only one numero_facture (or none at all) on this order:
            # behave exactly like standard Odoo, no ref/origin override.
            is_single_group = len(groups) <= 1
            allowed = restrict_map.get(order.id) if restrict_map else None

            for numero_facture, lines in groups.items():
                if allowed is not None and numero_facture not in allowed:
                    continue

                invoiceable_lines = lines.filtered(
                    lambda l: not float_is_zero(
                        l.qty_to_invoice, precision_digits=precision
                    )
                )
                if not invoiceable_lines:
                    # nothing left to bill for this group (already invoiced,
                    # or nothing ordered) - silently skip
                    continue

                invoice_vals = order._prepare_invoice()

                if not is_single_group and numero_facture:
                    invoice_vals['ref'] = numero_facture
                    invoice_vals['invoice_origin'] = "%s - %s" % (
                        order.name, numero_facture
                    )

                invoice_line_vals = []
                sequence = 10
                for line in invoiceable_lines.sorted(key=lambda l: l.sequence):
                    line_vals = line._prepare_account_move_line()
                    line_vals['sequence'] = sequence
                    invoice_line_vals.append((0, 0, line_vals))
                    sequence += 10

                invoice_vals['invoice_line_ids'] = invoice_line_vals
                invoice_vals_list.append(invoice_vals)

        if not invoice_vals_list:
            raise UserError(_('There is no invoiceable line.'))

        AccountMove = self.env['account.move'].with_context(
            default_move_type='in_invoice'
        )
        moves = self.env['account.move']
        for vals in invoice_vals_list:
            moves |= AccountMove.with_company(vals['company_id']).create(vals)

        # Some generated moves might actually be refunds - convert them,
        # same as core Odoo. Method name is version-dependent, hence the
        # hasattr guard.
        refund_candidates = moves.filtered(lambda m: m.amount_total < 0)
        if refund_candidates:
            if hasattr(refund_candidates, 'action_switch_move_type'):
                refund_candidates.action_switch_move_type()
            elif hasattr(refund_candidates, 'action_switch_invoice_move_type'):
                refund_candidates.action_switch_invoice_move_type()

        return moves

    # ------------------------------------------------------------------
    # Button action
    # ------------------------------------------------------------------
    def action_create_invoice(self):
        """Override the standard 'Create Bill' action.

        - If every selected order has at most one distinct
          x_studio_numero_facture value, there's nothing to choose:
          bills are created immediately, exactly like standard Odoo.
        - Otherwise, a wizard opens showing each numero_facture group with
          its total amount, letting the user pick which ones to generate.
          Groups that are already fully invoiced are shown greyed out and
          cannot be reselected.
        """
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure'
        )
        groups_by_order = self._get_numero_facture_groups()

        needs_wizard = any(len(groups) > 1 for groups in groups_by_order.values())

        if not needs_wizard:
            moves = self._create_bills()
            return self.action_view_invoice(moves)

        wizard_lines = []
        for order, groups in groups_by_order.items():
            for numero_facture, lines in groups.items():
                invoiceable_lines = lines.filtered(
                    lambda l: not float_is_zero(
                        l.qty_to_invoice, precision_digits=precision
                    )
                )
                already_invoiced = not invoiceable_lines
                total = sum(lines.mapped('price_subtotal'))
                wizard_lines.append((0, 0, {
                    'order_id': order.id,
                    'numero_facture': numero_facture,
                    'amount_total': total,
                    'already_invoiced': already_invoiced,
                    'to_generate': not already_invoiced,
                }))

        wizard = self.env['purchase.invoice.split.wizard'].create({
            'order_ids': [(6, 0, self.ids)],
            'line_ids': wizard_lines,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Select invoices to generate'),
            'res_model': 'purchase.invoice.split.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }