from odoo import fields, models


class PrintLog(models.Model):
    _name = "ll.print.platform.log"
    _description = "Print Log"
    _order = "timestamp desc, id desc"

    job_id = fields.Many2one("ll.print.platform.job", required=True, index=True, ondelete="cascade")
    timestamp = fields.Datetime(required=True, default=lambda self: fields.Datetime.now(), index=True)
    status = fields.Char(index=True)
    message = fields.Text()
