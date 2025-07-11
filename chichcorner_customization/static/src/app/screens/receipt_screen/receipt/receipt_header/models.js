/** @odoo-module */

import { Order, Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Orderline.prototype, {
    get_product_default_code() {
        return this.product.default_code;
    },
    getDisplayData() {
        var result = super.getDisplayData(...arguments);
        result.default_code = this.get_product_default_code();
        return result;
    }

});
