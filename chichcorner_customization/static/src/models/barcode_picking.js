/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import BarcodePickingModel from '@stock_barcode/models/barcode_picking_model';

patch(BarcodePickingModel.prototype, {
    getTotalQtyDone() {
        return this.currentState.lines.reduce((total, line) => {
            return total + (line.qty_done || 0);
        }, 0);
    },

    get barcodeInfo() {
        const result = super.barcodeInfo;
        const totalScanned = this.getTotalQtyDone();

        if (result.class === 'scan_product_or_dest') {
            result.message = this.considerPackageLines
                ? _t(
                      "Scan a product, a package, or the destination location. (Quantité scannée: %s)",
                      totalScanned
                  )
                : _t(
                      "Scan a product or the destination location. (Quantité scannée: %s)",
                      totalScanned
                  );
        }
        return result;
    },
});
