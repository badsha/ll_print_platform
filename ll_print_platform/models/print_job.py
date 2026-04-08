import base64
import datetime
import uuid
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PrintJob(models.Model):
    _name = "ll.print.platform.job"
    _description = "Print Job"
    _order = "priority desc, create_date asc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, copy=False, default=lambda self: self.env["ir.sequence"].next_by_code("ll.print.platform.job"))
    report_name = fields.Char(index=True)
    payload = fields.Binary(required=True)
    job_type = fields.Selection(
        [
            ("pdf", "PDF"),
            ("escpos", "ESC/POS"),
            ("raw", "Raw Bytes"),
        ],
        required=True,
        default="pdf",
        index=True,
        tracking=True,
    )
    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("assigned", "Assigned"),
            ("printing", "Printing"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        default="pending",
        required=True,
        index=True,
        tracking=True,
    )
    priority = fields.Integer(default=10, index=True)
    retry_count = fields.Integer(default=0, index=True)
    max_retries = fields.Integer(default=3)
    printer_id = fields.Many2one("ll.print.printer", required=True, index=True)
    tenant_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    error_message = fields.Text()
    next_retry_at = fields.Datetime(index=True)

    log_ids = fields.One2many("ll.print.platform.log", "job_id", readonly=True)

    agent_id = fields.Many2one("ll.print.platform.agent", index=True)
    printer_agent_id = fields.Many2one(related="printer_id.agent_id", readonly=True)
    agent_last_seen_at = fields.Datetime(compute="_compute_agent_health", readonly=True)
    is_agent_offline = fields.Boolean(compute="_compute_agent_health", readonly=True)
    lease_uuid = fields.Char(index=True, copy=False)
    leased_at = fields.Datetime(index=True)
    leased_until = fields.Datetime(index=True)
    acked_at = fields.Datetime(index=True)
    done_at = fields.Datetime(index=True)

    @api.depends("printer_id.agent_id", "printer_id.agent_id.last_seen_at")
    def _compute_agent_health(self):
        offline_seconds = int(self.env["ir.config_parameter"].sudo().get_param("ll_print_platform.agent_offline_seconds", "60") or 60)
        now = fields.Datetime.now()
        threshold = now - datetime.timedelta(seconds=offline_seconds)
        for rec in self:
            agent = rec.printer_id.agent_id
            rec.agent_last_seen_at = agent.last_seen_at if agent else False
            if not agent or not agent.active:
                rec.is_agent_offline = True
            elif not agent.last_seen_at:
                rec.is_agent_offline = True
            else:
                rec.is_agent_offline = agent.last_seen_at < threshold

    @api.constrains("payload")
    def _check_payload_not_empty(self):
        for rec in self:
            if not rec.payload:
                raise ValidationError("Missing payload.")

    @api.constrains("printer_id", "tenant_id")
    def _check_tenant_consistency(self):
        for rec in self:
            if rec.printer_id and rec.tenant_id and rec.printer_id.tenant_id.id != rec.tenant_id.id:
                raise ValidationError("Printer tenant must match job tenant.")

    def _new_lease_uuid(self):
        return uuid.uuid4().hex

    def mark_leased(self, agent, leased_until):
        self.write(
            {
                "agent_id": agent.id,
                "lease_uuid": self._new_lease_uuid(),
                "leased_at": fields.Datetime.now(),
                "leased_until": leased_until,
            }
        )
        self.env["ll.print.platform.log"].sudo().create(
            {"job_id": self.id, "timestamp": fields.Datetime.now(), "status": "leased", "message": f"Leased to agent {agent.name}."}
        )

    def mark_assigned(self):
        self.write({"status": "assigned", "acked_at": fields.Datetime.now()})
        self.env["ll.print.platform.log"].sudo().create(
            {"job_id": self.id, "timestamp": fields.Datetime.now(), "status": "assigned", "message": "Agent acknowledged job."}
        )

    def mark_printing(self):
        self.write({"status": "printing", "error_message": False})
        self.env["ll.print.platform.log"].sudo().create(
            {"job_id": self.id, "timestamp": fields.Datetime.now(), "status": "printing", "message": "Agent started printing."}
        )

    def mark_done(self):
        self.write({"status": "done", "error_message": False, "done_at": fields.Datetime.now()})
        self.env["ll.print.platform.log"].sudo().create(
            {"job_id": self.id, "timestamp": fields.Datetime.now(), "status": "done", "message": "Printed successfully."}
        )

    def mark_failed(self, error_message):
        vals = {"status": "failed", "error_message": (error_message or "").strip()[:5000]}
        self.write(vals)
        self.env["ll.print.platform.log"].sudo().create(
            {"job_id": self.id, "timestamp": fields.Datetime.now(), "status": "failed", "message": vals["error_message"] or "Failed."}
        )

    def can_retry(self):
        self.ensure_one()
        return self.retry_count < self.max_retries

    def compute_next_retry_at(self):
        self.ensure_one()
        delay_seconds = min(900, (2 ** min(self.retry_count, 10)) * 5)
        return fields.Datetime.now() + datetime.timedelta(seconds=int(delay_seconds))

    def schedule_retry(self, next_retry_at):
        self.ensure_one()
        if not self.can_retry():
            return False
        self.write(
            {
                "status": "failed",
                "retry_count": self.retry_count + 1,
                "next_retry_at": next_retry_at,
                "agent_id": False,
                "lease_uuid": False,
                "leased_at": False,
                "leased_until": False,
                "acked_at": False,
            }
        )
        return True

    @api.model
    def create_from_pos(self, payload):
        printer_id = payload.get("printer_id")
        content_b64 = payload.get("content_b64") or ""
        job_type = payload.get("job_type", "escpos")
        priority = payload.get("priority", 10)
        if not printer_id or not content_b64:
            return {"status": "error", "message": "Missing printer_id or content_b64."}
        printer = self.env["ll.print.printer"].browse(int(printer_id))
        if not printer.exists() or not printer.active:
            return {"status": "error", "message": "Printer not found or inactive."}
        try:
            payload_bytes = base64.b64decode(content_b64, validate=True)
        except Exception as e:
            return {"status": "error", "message": f"Invalid base64 payload: {e}"}
        payload_b64 = base64.b64encode(payload_bytes)
        self.create(
            {
                "printer_id": printer.id,
                "tenant_id": printer.tenant_id.id,
                "payload": payload_b64,
                "job_type": job_type,
                "priority": priority,
                "status": "pending",
            }
        )
        return {"status": "success"}
