from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    use_ll_print = fields.Boolean(string="Use Print Master", default=False)
    ll_receipt_printer_id = fields.Many2one(
        "ll.print.printer",
        string="Receipt Printer",
        domain="[('printer_type', 'in', ['receipt', 'report']), ('tenant_id', '=', company_id), ('active', '=', True)]",
    )
    ll_kitchen_printer_id = fields.Many2one(
        "ll.print.printer",
        string="Kitchen Printer",
        domain="[('printer_type', 'in', ['kitchen', 'receipt', 'report']), ('tenant_id', '=', company_id), ('active', '=', True)]",
    )
    # Note: do NOT override _load_pos_data_fields for pos.config.
    # An empty field list means "load all fields" in Odoo POS. Returning a
    # partial list (as older Print Master builds did) drops fields like
    # show_product_images and crashes ProductCard (imageUrl undefined).
