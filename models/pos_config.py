from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    use_ll_print = fields.Boolean(string="Use LL Print Platform", default=False)
    ll_receipt_printer_id = fields.Many2one(
        "ll.print.printer",
        string="Receipt Printer",
        domain="[('printer_type', '=', 'receipt'), ('tenant_id', '=', company_id), ('active', '=', True)]",
    )
    ll_kitchen_printer_id = fields.Many2one(
        "ll.print.printer",
        string="Kitchen Printer",
        domain="[('printer_type', '=', 'kitchen'), ('tenant_id', '=', company_id), ('active', '=', True)]",
    )

    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = list(super()._load_pos_data_fields(config) or [])
        candidate_fields = [
            "id",
            "name",
            "company_id",
            "currency_id",
            "use_pricelist",
            "pricelist_id",
            "available_pricelist_ids",
            "payment_method_ids",
            "cash_control",
            "iface_tipproduct",
            "tip_product_id",
            "iface_tax_included",
            "iface_print_via_proxy",
            "iface_scan_via_proxy",
            "iface_customer_facing_display_via_proxy",
            "iface_customer_facing_display_local",
            "iface_splitbill",
            "iface_orderline_notes",
            "iface_printbill",
            "iface_big_scrollbars",
            "iface_electronic_scale",
            "iface_start_categ_id",
            "iface_available_categ_ids",
            "module_pos_restaurant",
            "module_pos_hr",
            "module_pos_discount",
            "module_pos_loyalty",
            "module_pos_sale",
            "is_table_management",
            "is_order_printer",
            "is_posbox",
            "trusted_config_ids",
            "use_ll_print",
            "ll_receipt_printer_id",
            "ll_kitchen_printer_id",
        ]
        for field_name in candidate_fields:
            if field_name in self._fields and field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list
