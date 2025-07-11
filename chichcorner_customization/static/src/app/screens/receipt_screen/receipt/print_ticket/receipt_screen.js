/** @odoo-module **/
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup();
        this.printer = useService("printer");
    },

    async printGiftReceipt() {
        try {
            const order = this.pos.get_order();
            if (!order) {
                throw new Error('No active order found');
            }

            const receiptData = order.export_for_printing();
            const giftReceiptData = { ...receiptData };

            giftReceiptData.orderlines = receiptData.orderlines.map(line => ({
                ...line,
                quantity: Number(line.quantity) || 0,
                unit_name: line.unit_name || '',
                product_name: line.product_name || '',
                price: 0,
                unitPrice: 0,
                price_display: 0,
                price_with_tax: 0,
                price_without_tax: 0,
                tax: 0,
                discount: Number(line.discount) || 0
            }));

            // Fields that should be empty arrays
            const arrayFields = [
                'paymentlines',
                'tax_details'
            ];

            arrayFields.forEach(field => {
                giftReceiptData[field] = [];
            });

            // Fields that should be zero values (not empty strings!)
            const zeroValueFields = [
                'total_paid',
                'amount',
                'change',
                'amount_total',
                'unitPrice',
                'amount_tax',
                'total_without_tax',
                'subtotal',
                'tax',
                'total'
            ];

            zeroValueFields.forEach(field => {
                giftReceiptData[field] = 0;
            });

            // Mark as gift receipt
            giftReceiptData.is_gift_receipt = true;


            // Add a title for the gift receipt
            giftReceiptData.receipt_type = "Gift Receipt";

            // Create a custom formatCurrency function to handle gift receipt
            const originalFormatCurrency = this.env.utils.formatCurrency;
            const giftFormatCurrency = (value) => {
                // For gift receipts, we'll hide all currency values with dashes
                if (giftReceiptData.is_gift_receipt && value === 0) {
                    return "---";
                }
                // Otherwise use the normal formatter
                return originalFormatCurrency(value);
            };

            await this.printer.print(
                OrderReceipt, {
                    data: giftReceiptData,
                    formatCurrency: giftFormatCurrency, // Use our custom formatter
                },
                { webPrintFallback: true }
            );

            console.log("Gift receipt printed successfully");

        } catch (error) {
            console.error("Error in printGiftReceipt:", error);
        }
    }

    /*
    const report = await this.env.pos.proxy.printer.print_receipt('loyalty.gift_card_report', {
                data: reportData,
            });

            // Print the report directly
            if (report.successful) {
                await this.showTempScreen('ReceiptScreen', {
                    report: report.receipt,
                });
            }


    async printGiftReceipt() {
            let giftReceiptData;
            try {
                const order = this.pos.get_order();
                if (!order) {
                    throw new Error('No active order found');
                }

                const receiptData = order.export_for_printing();
                giftReceiptData = { ...receiptData };


                giftReceiptData.orderlines = receiptData.orderlines.map(line => ({
                    ...line,
                    quantity: Number(line.quantity) || "",
                    unit_name: line.unit_name || '',
                    product_name: line.product_name || '',
                    price: "",
                    change:"1",
                    amount_total:"1",
                    amount:"1",
                    oldUnitPrice:"",
                    unit:"",
                    qty:"",
                    unitPrice :"",
                    tax_details:"",
                    amount_tax:"",
                    total_without_tax:"",
                    tax: "",
                    discount: Number(line.discount) || "0"
                }));


                const zeroFields = [
                    'price',
                    'total_paid',
                    'amount',
                    'change',
                    'unitPrice',
                    'oldUnitPrice',
                    'qty',
                    'amount_total',
                    'tax_details',
                    'amount_tax',
                    'total_without_tax',
                    'unit',
                    'amount_total',
                    'change',
                    'subtotal',
                    'tax',
                    'total'
                ];

                zeroFields.forEach(field => {
                    giftReceiptData[field] = 0;
                });

                giftReceiptData.paymentlines = [];
                giftReceiptData.is_gift_receipt = true;


                const customFormatCurrency = (value) => {
                if (value === "----") {
                    return "--.--";
                }
                return this.env.utils.formatCurrency(value);
                };

                const tempContainer = document.createElement('div');
                tempContainer.className = 'pos-receipt-container';
                document.body.appendChild(tempContainer);

                await new Promise(resolve => setTimeout(resolve, 300));

                const receiptContent = document.querySelector('.pos-receipt-container');
                if (!receiptContent) {
                    throw new Error('Receipt content not found');
                }
                await this.printer.print(
                    OrderReceipt,{
                        data: giftReceiptData,
                        formatCurrency: this.env.utils.formatCurrency,
                    },
                    {webPrintFallback: true,}
                );

                console.log("data", giftReceiptData)
                    console.log("done, succes")



            } catch (error) {
                console.log("Error in printGiftReceipt:", error);
            }
        }


    async printGiftReceipt() {
        if (!this.printer) {
            try {
                this.printer = await this.env.services.printer;
                if (!this.printer) {
                    console.log("Printer service not available");
                }else{
                    console.log("passed 1")
                }
            } catch (error) {
                console.log("Failed to initialize printer service:", error);
                return;
            }
        }

        try {
            const order = this.pos.get_order();
            if (!order) {
                console.log("No active order found");
            }

            const receiptData = order.export_for_printing();
            const giftReceiptData = { ...receiptData };

            giftReceiptData.orderlines = giftReceiptData.orderlines?.map(line => ({
                ...line,
                price: parseFloat(line.price || "0"),
                price_display: parseFloat(line.price_display || "0"),
                price_with_tax: parseFloat(line.price_with_tax || "0"),
                price_without_tax: parseFloat(line.price_without_tax || "0"),
                tax: parseFloat(line.tax || "0"),
                unit_price: parseFloat(line.unit_price || "0"),
            })) || [];

            giftReceiptData.total_paid = parseFloat(giftReceiptData.total_paid || "0");
            giftReceiptData.total_with_tax = parseFloat(giftReceiptData.total_with_tax || "0");
            giftReceiptData.total_without_tax = parseFloat(giftReceiptData.total_without_tax || "0");
            giftReceiptData.total_tax = parseFloat(giftReceiptData.total_tax || "0");

            const receiptContainer = document.querySelector(".pos-receipt-container");
            if (!receiptContainer) {
                console.log("Receipt container not found");
            }else{
                console.log("passed 4")
            }
                const tempContainer = document.createElement('div');
                tempContainer.className = 'pos-receipt-container';
                document.body.appendChild(tempContainer);

            const isPrinted = await this.printer.print(
                OrderReceipt,
                {
                    data: giftReceiptData,
                    formatCurrency: this.env?.utils?.formatCurrency || (val => val.toString()),
                },
                { webPrintFallback: true }
            );
                console.log("passed 5")
            if (isPrinted && this.currentOrder) {
                this.currentOrder._printed = true;
                console.log("passed 6")
            }else{
                console.log("not passed 5")
            }
        } catch (error) {
            console.log("Printing error:", error);
        }
    }

     */

});
