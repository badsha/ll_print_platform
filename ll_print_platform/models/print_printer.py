from odoo import api, fields, models


class PrintPrinter(models.Model):
    _name = "ll.print.printer"
    _description = "Printer"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, index=True, tracking=True)
    printer_type = fields.Selection(
        [
            ("receipt", "Receipt"),
            ("kitchen", "Kitchen"),
            ("label", "Label"),
            ("report", "Report"),
        ],
        default="receipt",
        required=True,
        index=True,
        tracking=True,
    )
    agent_identifier = fields.Char(required=True, index=True, tracking=True)
    tenant_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    active = fields.Boolean(default=True, tracking=True)
    is_active = fields.Boolean(compute="_compute_is_active", inverse="_inverse_is_active", store=True, tracking=True)
    default_for_report = fields.Boolean(default=False, tracking=True)
    default_for_invoice = fields.Boolean(default=False, tracking=True)
    agent_id = fields.Many2one("ll.print.platform.agent", index=True, tracking=True)

    _sql_constraints = [
        ("code_tenant_uniq", "unique(code, tenant_id)", "Printer code must be unique per tenant."),
        ("agent_identifier_tenant_uniq", "unique(agent_identifier, tenant_id)", "Agent identifier must be unique per tenant."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_unique_defaults()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "default_for_invoice" in vals or "default_for_report" in vals:
            self._ensure_unique_defaults()
        return res

    def _ensure_unique_defaults(self):
        for rec in self.filtered(lambda r: r.default_for_invoice):
            self.search(
                [("tenant_id", "=", rec.tenant_id.id), ("id", "!=", rec.id), ("default_for_invoice", "=", True)]
            ).write({"default_for_invoice": False})
        for rec in self.filtered(lambda r: r.default_for_report):
            self.search(
                [("tenant_id", "=", rec.tenant_id.id), ("id", "!=", rec.id), ("default_for_report", "=", True)]
            ).write({"default_for_report": False})

    def _compute_is_active(self):
        for rec in self:
            rec.is_active = bool(rec.active)

    def _inverse_is_active(self):
        for rec in self:
            rec.active = bool(rec.is_active)
