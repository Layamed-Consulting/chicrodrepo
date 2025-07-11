/** @odoo-module **/
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { TextInputPopup } from "@point_of_sale/app/utils/input_popups/text_input_popup";
import { _t } from "@web/core/l10n/translation";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup();
        this.popup = useService("popup");
        this.notification = useService("notification");
    },

    async addNewPaymentLine(paymentMethod) {
        const result = super.addNewPaymentLine(paymentMethod);
        if (result && paymentMethod.name === "Carte Bancaire") {
            const { confirmed, payload: stan } = await this.popup.add(TextInputPopup, {
                title: _t("Enter STAN Number"),
                startingValue: "",
            });
            if (confirmed) {
                this.currentOrder.set_stan(stan);
                console.log("your order is", this.currentOrder);
                this.notification.add(_t('STAN created successfully!'), {
                        type: "success",
                    });
            }
            /*
            else{
                const paymentLineCid = this.currentOrder.selected_paymentline.cid;
                this.deletePaymentLine(paymentLineCid);
                this.notification.add(_t('STAN not entered, payment line removed!'), {
                    type: "danger",
                });
            }

             */
        }
        return result;
    },
});
