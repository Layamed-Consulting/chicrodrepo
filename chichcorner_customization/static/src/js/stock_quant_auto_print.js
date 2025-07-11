/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { onMounted } from "@odoo/owl";

export class StockQuantListController extends ListController {
    setup() {
        super.setup();
        onMounted(() => {
            this.autoPrintLabel();
        });
    }

    autoPrintLabel() {

        if (this.props.context?.trigger_print_button) {
            setTimeout(() => {
                const printButton = document.querySelector('button[name="action_print_label"]');
                if (printButton) {
                    printButton.click();
                    if (this.isMobileDevice()) {
                        printButton.click();
                        /*
                        setTimeout(() => {
                            //window.click();
                        }, 2000);

                         */
                    }
                }
            }, 500);
        }
    }

    isMobileDevice() {
        return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    }
}


registry.category("views").add("stock_quant_list_inherit", {
    ...registry.category("views").get("list"),
    Controller: StockQuantListController,
});
