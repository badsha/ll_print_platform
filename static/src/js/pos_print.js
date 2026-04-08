/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

patch(PosStore.prototype, {
    async printReceipt({ basic = false, order = this.getOrder(), printBillActionTriggered = false } = {}) {
        const receiptPrinterId = this.config.ll_receipt_printer_id?.id ?? this.config.ll_receipt_printer_id;
        const kitchenPrinterId = this.config.ll_kitchen_printer_id?.id ?? this.config.ll_kitchen_printer_id;

        if (!this.config.use_ll_print || !receiptPrinterId) {
            return await super.printReceipt(...arguments);
        }

        try {
            const ticketImage = await this.env.services.renderer.toJpeg(
                OrderReceipt,
                { order, basic_receipt: basic },
                { addClass: "pos-receipt-print p-3" }
            );
            const contentB64 = ticketImage.split(",").pop();
            await this.data.call(
                "ll.print.platform.job",
                "create_from_pos",
                [
                    {
                        printer_id: receiptPrinterId,
                        content_b64: contentB64,
                        job_type: "raw",
                        priority: 10,
                    },
                ],
                {},
                true
            );
            if (kitchenPrinterId) {
                await this.data.call(
                    "ll.print.platform.job",
                    "create_from_pos",
                    [
                        {
                            printer_id: kitchenPrinterId,
                            content_b64: contentB64,
                            job_type: "raw",
                            priority: 20,
                        },
                    ],
                    {},
                    true
                );
            }
        } catch (e) {
        }

        return await super.printReceipt(...arguments);
    },
});
