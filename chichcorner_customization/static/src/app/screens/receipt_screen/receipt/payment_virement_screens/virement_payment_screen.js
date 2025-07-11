/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import {VirementPaymentFormPopup} from "./virement_payment";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup();
        this.popup = useService("popup");
        this.notification = useService("notification");
    },
    async addNewPaymentLine(paymentMethod) {
    const result = await super.addNewPaymentLine(paymentMethod);
    if (result && paymentMethod.name === "Virement") {
        const popupResult = await this.popup.add(VirementPaymentFormPopup, {
            title: _t("Veuillez entrer les détails du paiement par virement"),
        });
        if (popupResult && popupResult.confirmed !== undefined) {
            const { confirmed, payload } = popupResult;
            if (!confirmed) {
                const paymentLineCid = this.currentOrder.selected_paymentline.cid;
                this.deletePaymentLine(paymentLineCid);
                this.notification.add(_t("La méthode de paiement par virement a été supprimée"), {
                    type: "danger",
                });
            }
        } else {
            console.error("Popup result is invalid or missing 'confirmed' property");
        }
    }
    return result;
}
});

