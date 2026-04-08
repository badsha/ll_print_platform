import base64

from odoo import models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_ll_print_platform_queue(self):
        self.ensure_one()
        printer = self.env["ll.print.printer"].sudo().search(
            [("tenant_id", "=", self.company_id.id), ("active", "=", True), ("default_for_invoice", "=", True)],
            limit=1,
        )
        if not printer:
            printers = self.env["ll.print.printer"].sudo().search(
                [("tenant_id", "=", self.company_id.id), ("active", "=", True)],
                limit=2,
            )
            if len(printers) == 1:
                printer = printers[0]

        if printer and getattr(self, "is_invoice", None) and self.is_invoice(include_receipts=True):
            report = self.env.ref("account.account_invoices", raise_if_not_found=False)
            if not report:
                raise UserError(_("Invoice report not found."))

            pdf_content, _report_type = self.env["ir.actions.report"]._render_qweb_pdf(report, res_ids=self.ids)
            job = self.env["ll.print.platform.job"].sudo().create(
                {
                    "name": f"{report.name}",
                    "report_name": report.report_name,
                    "payload": base64.b64encode(pdf_content),
                    "job_type": "pdf",
                    "status": "pending",
                    "printer_id": printer.id,
                    "tenant_id": self.company_id.id,
                }
            )
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Print Job Created"),
                    "message": _("Invoice sent to %s (Job %s)") % (printer.name, job.name),
                    "type": "success",
                },
            }

        return {
            "type": "ir.actions.act_window",
            "name": _("Direct Print"),
            "res_model": "ll.print.platform.direct.print.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_model": "account.move",
                "active_ids": self.ids,
                "default_tenant_id": self.company_id.id,
            },
        }
