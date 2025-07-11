/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { useRef, useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook"; // Import POS hook for accessing the POS session
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { Input } from "@point_of_sale/app/generic_components/inputs/input/input";
import { _t } from "@web/core/l10n/translation";

export class VirementPaymentFormPopup extends AbstractAwaitablePopup {
    static template = "chichcorner_customization.VirementPaymentForm";
    static components = { Input };

    setup() {
        super.setup();
        const today = new Date().toISOString().split("T")[0];
        this.notification = useService("pos_notification");
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.pos = usePos();
        this.state = useState({
            vir_number: "",
            num_client: "",
            vir_montant: "",
            ref_cmd: "",
            date_commande: today,
            isFieldEmpty: false,
            showErrors: false,
        });
    }

    validateFields() {
        const { vir_number, num_client, vir_montant,date_commande } = this.state;
        this.state.isFieldEmpty =
            !vir_number.trim() || !num_client.trim() || !vir_montant.trim() || !date_commande.trim();
    }

    async confirm() {
        const vir_number = this.state.vir_number;
        const num_client = this.state.num_client;
        const vir_montant = this.state.vir_montant;
        const ref = this.state.ref_cmd;
        const date_commande = this.state.date_commande;

        // Validate fields
        this.validateFields();

        if (this.state.isFieldEmpty) {
            this.state.showErrors = true;
            return;
        } else {
            this.state.showErrors = false;
        }

        const currentOrder = this.pos.get_order();
        let result = { confirmed: false, payload: null };

        if (currentOrder) {
            // Update order with payment details
            currentOrder.set_vir_number(vir_number);
            currentOrder.set_num_client(num_client);
            currentOrder.set_vir_montant(vir_montant);
            currentOrder.set_ref_cmd(ref);
            currentOrder.set_date_commande(date_commande);
            console.log('Payment details:', vir_number, num_client, ref,vir_montant,date_commande );
            result = { confirmed: true, payload: { vir_number, num_client, vir_montant, ref, date_commande } };
        }

        // Close the popup and show the success notification
        this.props.close();
        this.notification.add(
            _t("Virement créé avec succès"),
            { type: "success" }
        );
        return result;
    }
}


