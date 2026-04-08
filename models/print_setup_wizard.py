import base64
import secrets

from odoo import api, fields, models
from odoo.exceptions import UserError


class PrintSetupWizard(models.TransientModel):
    _name = "ll.print.setup.wizard"
    _description = "Print Setup"

    tenant_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    odoo_url = fields.Char(compute="_compute_odoo_url")
    download_url = fields.Char(default="https://github.com/CHANGE_ME/print-agent/releases/latest")

    agent_id = fields.Many2one("ll.print.platform.agent", readonly=True)
    api_key = fields.Char(related="agent_id.api_key", readonly=True)

    agent_config = fields.Text(compute="_compute_agent_config")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        tenant_id = res.get("tenant_id") or self.env.company.id
        if "agent_id" in fields_list or not fields_list:
            agent = self.env["ll.print.platform.agent"].sudo().search(
                [("tenant_id", "=", tenant_id), ("active", "=", True)],
                limit=1,
            )
            if agent:
                res["agent_id"] = agent.id
        return res

    @api.onchange("tenant_id")
    def _onchange_tenant_id_load_agent(self):
        for rec in self:
            if not rec.tenant_id:
                rec.agent_id = False
                continue
            rec.agent_id = self.env["ll.print.platform.agent"].sudo().search(
                [("tenant_id", "=", rec.tenant_id.id), ("active", "=", True)],
                limit=1,
            )

    @api.depends("tenant_id")
    def _compute_odoo_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        for rec in self:
            rec.odoo_url = base_url

    @api.depends("odoo_url", "api_key")
    def _compute_agent_config(self):
        for rec in self:
            odoo_url = (rec.odoo_url or "").strip()
            api_key = (rec.api_key or "").strip()
            rec.agent_config = "\n".join(
                [
                    f"odoo_url: {odoo_url}",
                    f"api_key: {api_key}",
                    "polling_interval: 3",
                    "lease_seconds: 30",
                ]
            )

    def action_prepare_agent(self):
        self.ensure_one()
        Agent = self.env["ll.print.platform.agent"].sudo()
        agent = Agent.search([("tenant_id", "=", self.tenant_id.id), ("active", "=", True)], limit=1)
        if not agent:
            agent = Agent.create(
                {
                    "name": f"Print Agent ({self.tenant_id.name})",
                    "tenant_id": self.tenant_id.id,
                    "api_key": secrets.token_urlsafe(32),
                    "active": True,
                }
            )
        self.agent_id = agent.id
        return {
            "type": "ir.actions.act_window",
            "res_model": "ll.print.setup.wizard",
            "view_mode": "form",
            "target": "new",
            "res_id": self.id,
        }

    def action_regenerate_api_key(self):
        self.ensure_one()
        if not self.agent_id:
            return self.action_prepare_agent()
        self.agent_id.sudo().write({"api_key": secrets.token_urlsafe(32)})
        return {
            "type": "ir.actions.act_window",
            "res_model": "ll.print.setup.wizard",
            "view_mode": "form",
            "target": "new",
            "res_id": self.id,
        }

    def action_download_agent(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": (self.download_url or "").strip(),
            "target": "new",
        }


class PrintDirectWizard(models.TransientModel):
    _name = "ll.print.platform.direct.print.wizard"
    _description = "Direct Print"

    tenant_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    report_id = fields.Many2one(
        "ir.actions.report",
        required=True,
        domain=[("report_type", "=", "qweb-pdf")],
    )
    printer_id = fields.Many2one(
        "ll.print.printer",
        required=True,
        domain="[('tenant_id', '=', tenant_id), ('active', '=', True)]",
    )
    res_model = fields.Char(compute="_compute_res_model", readonly=True, store=False)
    record_ids = fields.Char(required=True)

    @api.depends("report_id")
    def _compute_res_model(self):
        for rec in self:
            rec.res_model = rec.report_id.model or ""

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get("active_model")
        active_ids = self.env.context.get("active_ids") or []
        if active_ids and ("record_ids" in fields_list or not fields_list):
            res["record_ids"] = ",".join(str(i) for i in active_ids)
        if active_model == "account.move" and ("report_id" in fields_list or not fields_list):
            report = self.env.ref("account.account_invoices", raise_if_not_found=False)
            if report:
                res["report_id"] = report.id
        tenant_id = res.get("tenant_id") or self.env.company.id
        report_id = res.get("report_id")
        if "printer_id" in fields_list or not fields_list:
            printer_domain = [("tenant_id", "=", tenant_id), ("active", "=", True)]
            if report_id:
                report = self.env["ir.actions.report"].browse(int(report_id))
                if getattr(report, "is_invoice_report", False):
                    printer_domain.append(("default_for_invoice", "=", True))
                else:
                    printer_domain.append(("default_for_report", "=", True))
            printer = self.env["ll.print.printer"].sudo().search(printer_domain, limit=1)
            if printer:
                res["printer_id"] = printer.id
        return res

    def action_queue_print(self):
        self.ensure_one()
        if self.report_id.model and self.report_id.model != (self.res_model or self.report_id.model):
            raise UserError("Invalid report/model.")
        raw_ids = (self.record_ids or "").replace(" ", "")
        try:
            res_ids = [int(x) for x in raw_ids.split(",") if x]
        except Exception:
            raise UserError("Invalid record IDs.")
        if not res_ids:
            raise UserError("Missing record IDs.")
        records = self.env[self.report_id.model].browse(res_ids).exists()
        if not records:
            raise UserError("Records not found.")
        pdf_content, _report_type = self.env["ir.actions.report"]._render_qweb_pdf(self.report_id, res_ids=records.ids)
        self.env["ll.print.platform.job"].sudo().create(
            {
                "name": f"{self.report_id.name}",
                "report_name": self.report_id.report_name,
                "payload": base64.b64encode(pdf_content),
                "job_type": "pdf",
                "status": "pending",
                "printer_id": self.printer_id.id,
                "tenant_id": self.tenant_id.id,
            }
        )
        return {"type": "ir.actions.act_window_close"}
