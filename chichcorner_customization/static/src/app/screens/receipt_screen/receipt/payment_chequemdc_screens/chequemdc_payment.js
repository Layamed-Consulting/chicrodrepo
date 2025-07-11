/** @odoo-module **/
import { useService } from "@web/core/utils/hooks";
import { useRef, useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook"; // Import POS hook for accessing the POS session
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { Input } from "@point_of_sale/app/generic_components/inputs/input/input";
import { _t } from "@web/core/l10n/translation";

export class ChequeMDCPaymentFormPopup extends AbstractAwaitablePopup {
    static template = "chichcorner_customization.ChequemdcPaymentForm";
    static components = { Input };

    setup() {
        super.setup();
        this.notification = useService("pos_notification");
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.pos = usePos();
        this.state = useState({
            identite_number: "",
            cheque_number: "",
            banque: "",
            cheque_date: "",
            isFieldEmpty: false,
            isInBlacklist: false,
            showErrors: false,
        });

        // Watch for changes to identite_number field for real-time validation
        this.state.identite_number = this.state.identite_number;
    }

    async checkBlacklist() {
        const cin = this.state.identite_number;
        const blacklistRecord = await this.orm.call('black.list', 'search_read', [
            [['cin', 'ilike', cin], ['status', '=', 'inactive']],
            ['cin', 'status']
        ]);

        // Check if the CIN exists in the blacklist
        if (blacklistRecord.length > 0 && blacklistRecord[0].status === 'inactive') {
        this.state.isInBlacklist = true;
        } else {
        this.state.isInBlacklist = false;
    }}

    async onIdentiteNumberInput() {
        // Perform real-time validation
        await this.checkBlacklist();
    }

    validateFields() {
        const { identite_number, cheque_number, banque,cheque_date } = this.state;
        this.state.isFieldEmpty =
            !identite_number.trim() || !cheque_number.trim() || !banque.trim() || !cheque_date.trim();;
    }

    async confirm() {
        const cin = this.state.identite_number;
        const cn = this.state.cheque_number;
        const bn = this.state.banque;
        const cdm = this.state.cheque_date;

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
            console.log("Your order is:", currentOrder);

            /*
            // Handle blacklist check again before final confirmation
            const blacklistRecord = await this.orm.call('black.list', 'search_read', [
                [['cin', 'ilike', cin]],
                ['cin']
            ]);
            if (blacklistRecord.length > 0) {
                this.state.isInBlacklist = true;
            }

             */

            // Update order with payment details
            currentOrder.set_identite_number(cin);
            currentOrder.set_cheque_number(cn);
            currentOrder.set_banque_name(bn);
            currentOrder.set_cheque_date(cdm);

            console.log('Payment details:', cin, cn, bn);
            result = { confirmed: true, payload: { cin, cn, bn, cdm } };
        }

        // Close the popup and show the success notification
        this.props.close();
        this.notification.add(
            _t("Cheque MDC Payment created successfully"),
            { type: "success" }
        );

        return result;
    }
}

