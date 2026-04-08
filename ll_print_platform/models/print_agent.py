from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PrintAgent(models.Model):
    _name = "ll.print.platform.agent"
    _description = "Print Agent"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    api_key = fields.Char(required=True, tracking=True)
    tenant_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    active = fields.Boolean(default=True, tracking=True)
    last_seen_at = fields.Datetime(readonly=True, tracking=True)
    allowed_printer_ids = fields.Many2many(
        "ll.print.printer",
        "print_agent_printer_rel",
        "agent_id",
        "printer_id",
        string="Allowed Printers",
    )

    _sql_constraints = [
        ("api_key_uniq", "unique(api_key)", "API key must be unique."),
    ]

    @api.constrains("api_key")
    def _check_api_key_format(self):
        for rec in self:
            if rec.api_key and len(rec.api_key.strip()) < 16:
                raise ValidationError("API key must be at least 16 characters.")
