/** @odoo-module */


import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";

patch(ClosePosPopup.prototype, {
    setup() {
        super.setup();
    },

     async downloadJournalReport() {
        this.env.services.action.doAction({
            type: "ir.actions.report",
            report_name: "chichcorner_customization.journal_report_template",
            report_type: "qweb-pdf",
            context: {
                active_ids: [this.pos.pos_session.id],
            },
        });
    },
});