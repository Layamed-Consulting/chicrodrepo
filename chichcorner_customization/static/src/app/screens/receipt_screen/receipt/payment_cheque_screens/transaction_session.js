/** @odoo-module **/

import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConnectionLostError } from "@web/core/network/rpc_service";

//const OriginalCloseSession = ClosePosPopup.prototype.closeSession;

patch(ClosePosPopup.prototype, {
    async closeSession() {
        try {
            this.customerDisplay?.update({ closeUI: true });
            const syncSuccess = await this.pos.push_orders_with_closing_popup();
            if (!syncSuccess) {
                return;
            }

            if (this.pos.config.cash_control) {
                const cashDetails = this.props.default_cash_details;
                const countedCash = parseFloat(this.state.payments[cashDetails.id]?.counted || 0);
                const response = await this.orm.call(
                    "pos.session",
                    "post_closing_cash_details",
                    [this.pos.pos_session.id],
                    { counted_cash: countedCash }
                );
                if (!response.successful) {
                    return this.handleClosingError(response);
                }
            }

            const sessionId = this.pos.pos_session.id;
            const notes = this.state.notes || "";
            const cashierName = this.pos.cashier.name || "";
            const storeName = this.pos.config.name;
            const cashDetails = this.props.default_cash_details;
            const cashExpected = parseFloat(cashDetails.amount || "0");
            const cashCounted = parseFloat(this.state.payments[cashDetails.id]?.counted || "0");
        //const cashDifference = this.getDifference(); // Use getMaxDifference for cash
            const cashDifference = cashCounted - cashExpected;
            const paymentMethodsData = [
                {
                    session_id: sessionId,
                    payment_method_id: cashDetails.id,
                    cashier_name: cashierName, // Add cashier's name
                    store_name: storeName,
                    payment_method_name: cashDetails.name,
                    expected: cashExpected,
                    counted_cash: cashCounted,
                    payment_differences: cashDifference,
                    notes: notes,
                },
                ...this.props.other_payment_methods.map(paymentMethod => {
                const expected = parseFloat(paymentMethod.amount || 0);
                const counted = parseFloat(this.state.payments[paymentMethod.id]?.counted || 0);
                const difference =  counted - expected;
                return {
                    session_id: sessionId,
                    payment_method_id: paymentMethod.id,
                    cashier_name: cashierName, // Add cashier's name
                    store_name: storeName,
                    payment_method_name: paymentMethod.name,
                    expected: expected,
                    counted_cash: counted,
                    payment_differences: difference,
                    notes: notes,
                };
            }),

            ];
            for (const paymentMethodData of paymentMethodsData) {
                try {
                    await this.orm.call("transaction.session", "create", [paymentMethodData]);
                    console.log("Transaction session data saved successfully:", paymentMethodData);
                } catch (error) {
                    console.error("Failed to save transaction session data:", error);
                }
            }

            await this.orm.call("pos.session", "update_closing_control_state_session", [sessionId, notes]);
            const response = await this.orm.call("pos.session", "close_session_from_ui", [
                sessionId,
                this.props.other_payment_methods
                    .filter((pm) => pm.type == "bank")
                    .map((pm) => [pm.id, this.getDifference(pm.id)]),
            ]);

            if (!response.successful) {
                return this.handleClosingError(response);
            }

            window.location = "/web#action=point_of_sale.action_client_pos_menu";
        }
        catch (error) {

    if (error instanceof ConnectionLostError) {
        throw error;
    } else {
        console.error("Closing session error:", error);
        await this.popup.add(ErrorPopup, {
            title: "Closing Session Error",
            body: "Impossible d'enregistrer cette session.",
        });
        try {
            const sessionId = this.pos.pos_session.id;
            const response = await this.orm.call("pos.session", "close_session_from_ui", [
                sessionId,
                this.props.other_payment_methods
                    .filter((pm) => pm.type === "bank")
                    .map((pm) => [pm.id, this.getDifference(pm.id)]),
            ]);

            if (!response.successful) {
                return this.handleClosingError(response);
            }
        } catch (closingError) {
            console.error("Error during forced session closure:", closingError);
            await this.popup.add(ErrorPopup, {
                title: "Forced Session Closure Error",
                body: "Unable to forcibly close the session. Please contact support.",
            });
        }
        window.location = "/web#action=point_of_sale.action_client_pos_menu";
    }
}
    },
});
