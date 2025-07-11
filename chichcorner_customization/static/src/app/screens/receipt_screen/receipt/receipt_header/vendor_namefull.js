/** @odoo-module **/
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { TextAreaPopup } from "@point_of_sale/app/utils/input_popups/textarea_popup";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

patch(PaymentScreen.prototype, {
      setup(){
      super.setup();
      this.pos = usePos();
      this.popup = useService("popup");
      this.notification = useService("notification");
    },
      async customer_suggestion(){
       const { confirmed, payload: inputSection } = await this.popup.add(TextAreaPopup, {
           title: _t("Add Vendor Name"),
       });
        if (confirmed) {
    if (!inputSection) {
        this.notification.add(_t("Vendor name cannot be empty!"), {
            type: "danger",
        });
    } else {
        this.pos.get_order().set_customer_suggestion(inputSection);
        this.notification.add(_t("Vendor created successfully!"), {
            type: "success",
        });
    }
} return 'done by anass';
        },});
