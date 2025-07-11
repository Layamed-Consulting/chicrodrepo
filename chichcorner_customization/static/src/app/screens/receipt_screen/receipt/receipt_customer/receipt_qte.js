/** @odoo-module */

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";

patch(Order.prototype, {
       setup(){
       super.setup(...arguments);
       },
       export_for_printing() {
        const result = super.export_for_printing(...arguments);

        let sum = 0;
        let unique_items = new Set();

        this.orderlines.forEach(function(line) {
            if (!line.is_reward_line) {
                sum += line.quantity;
                unique_items.add(line.product.id);
            }
        });

        result.sum = sum;
        result.unique_items_count = unique_items.size;
        return result;
    }

    /**
       export_for_printing() {
           const result = super.export_for_printing(...arguments);
          result.count = this.orderlines.length
          this.receipt = result.count
          var sum = 0;
          this.orderlines.forEach(function(t) {
                    sum += t.quantity;
                })
                result.sum = sum
        console.log('Exporting order:', result);
        return result;
       }
           **/

});
