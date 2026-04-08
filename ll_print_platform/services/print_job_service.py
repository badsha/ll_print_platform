import base64
from odoo import api, models


class PrintJobService(models.AbstractModel):
    _name = "ll.print.job.service"
    _description = "Print Job Service"

    @api.model
    def create_job_from_report(self, report_ref, res_ids, printer):
        if not report_ref:
            raise ValueError("Missing report_ref.")
        if not res_ids:
            raise ValueError("Missing res_ids.")
        if not printer or not printer.exists():
            raise ValueError("Invalid printer.")

        pdf_content, _report_type = self.env["ir.actions.report"]._render_qweb_pdf(report_ref, res_ids=list(res_ids))
        return self.env["ll.print.platform.job"].create(
            {
                "report_name": report_ref,
                "payload": base64.b64encode(pdf_content),
                "job_type": "pdf",
                "printer_id": printer.id,
                "tenant_id": printer.tenant_id.id,
                "status": "pending",
            }
        )

    @api.model
    def create_job_from_payload(self, payload_b64, job_type, printer, report_name=None, priority=10):
        if not payload_b64:
            raise ValueError("Missing payload.")
        payload_bytes = base64.b64decode(payload_b64, validate=True)
        if not printer or not printer.exists():
            raise ValueError("Invalid printer.")

        return self.env["ll.print.platform.job"].create(
            {
                "report_name": report_name,
                "payload": base64.b64encode(payload_bytes),
                "job_type": job_type,
                "priority": int(priority or 10),
                "printer_id": printer.id,
                "tenant_id": printer.tenant_id.id,
                "status": "pending",
            }
        )
