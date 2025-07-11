/** @odoo-module **/
import { registry } from "@web/core/registry";

async function printAttachment(env, action) {
    try {
        if (action && action.params && action.params.html) {
            const reportHtml = action.params.html;


            const userAgent = navigator.userAgent || "";
            const isAndroid = /Android|iPhone|iPad|iPod/i.test(userAgent);

            const printStyles = `
<style>
    @media print {
        @page {
            size: 57mm 32mm;
            margin: 0;
        }

        body, html {
            margin: 0;
            padding: 0;
            width: 57mm;
            height: 32mm;
            overflow: hidden;
        }

        .print-content {
            width: 57mm;
            height: 32mm;
            transform: scale(1);
            transform-origin: top left;
        }

        .o_label_sheet {
            width: 100%;
            height: 100%;
        }

        .o_label_name {
            font-size: 10px;
            font-weight: bold;
            word-wrap: break-word;
            max-width: 100%;
        }

        .o_label_small_barcode img {
            max-width: 100%;
            max-height: 100%;
        }

        .o_label_price_small {
            font-size: 12px;
            font-weight: bold;
            color: black;
        }
    }
</style>
`;


            const modifiedHtml = `
                ${printStyles}
                <div class="print-content">
                    ${reportHtml}
                </div>
            `;
            if (isAndroid) {

                const iframe = document.createElement("iframe");
                iframe.style.position = "fixed";
                iframe.style.top = "0";
                iframe.style.left = "0";
                iframe.style.width = "100%";
                iframe.style.height = "100%";
                iframe.style.border = "none";
                iframe.style.zIndex = "9999";
                iframe.style.visibility = "hidden";

                document.body.appendChild(iframe);

                const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                iframeDoc.open();
                iframeDoc.write(modifiedHtml);
                iframeDoc.close();

                iframe.style.visibility = "visible";
                setTimeout(() => {
                    iframe.contentWindow.print();
                }, 200);

                setTimeout(() => {
                    document.body.removeChild(iframe); // Remove the iframe from the DOM
                    window.location = "/web#action=stock_barcode.stock_barcode_action_main_menu"; // Redirect back to the POS interface
                }, 4000);
                /*
                setTimeout(() => {
                    document.body.removeChild(iframe);
                }, 6000)

                 */
               // window.location = "/web#action=stock_barcode.stock_barcode_action_main_menu";
            } else {
                console.log("Android detected: Opening report in a new tab.");
                const newWindow = window.open("", "_blank");
                if (!newWindow) {
                    console.warn("Popup blocked! Enable popups to print automatically.");
                    return;
                }

                newWindow.document.open();
                newWindow.document.write(modifiedHtml);
                newWindow.document.close();
                newWindow.print();
                return;
            }

            /*
            if (isAndroid) {
                console.log("Android detected: Opening report in a new tab.");
                const newWindow = window.open("", "_blank");
                if (!newWindow) {
                    console.warn("Popup blocked! Enable popups to print automatically.");
                    return;
                }

                newWindow.document.open();
                newWindow.document.write(modifiedHtml);
                newWindow.document.close();
                newWindow.print();
                return;
            }

            let iframe = document.getElementById("printIframe");
            if (!iframe) {
                iframe = document.createElement("iframe");
                iframe.id = "printIframe";
                iframe.style.position = "absolute";
                iframe.style.width = "0px";
                iframe.style.height = "0px";
                iframe.style.border = "none";
                document.body.appendChild(iframe);
            }

            const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;

            iframeDoc.open();
            iframeDoc.write(modifiedHtml);
            iframeDoc.close();

            iframe.onload = function () {
                console.log("Report Loaded, trying to print...");
                setTimeout(() => {
                    try {
                        iframe.contentWindow.print();
                    } catch (e) {
                        console.error("Print blocked due to security restrictions:", e);
                    }
                }, 1000);
            };

             */
        } else {
            throw new Error("Report HTML content not provided or invalid");
        }
    } catch (error) {
        console.error("Error in printAttachment:", error);
    }
}

registry.category("actions").add("print_attachment", printAttachment);
