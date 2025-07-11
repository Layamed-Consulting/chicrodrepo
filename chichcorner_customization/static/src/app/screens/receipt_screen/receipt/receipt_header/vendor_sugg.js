/** @odoo-module */
import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";


patch(Order.prototype, {
     setup(_defaultObj, options) {
           super.setup(...arguments);
           this.suggestion = this.suggestion || null;
       },
     init_from_JSON(json) {
      this.set_customer_suggestion(json.suggestion);
      super.init_from_JSON(...arguments);
   },
   export_as_JSON() {
       const json = super.export_as_JSON(...arguments);
       if (json) {
           json.suggestion = this.Suggestion;
       }
       return json;
   },
    set_customer_suggestion(suggestion) {
       this.Suggestion = suggestion;
   },
    get_customer_suggestion() {
        return this.suggestion;
    },
});
