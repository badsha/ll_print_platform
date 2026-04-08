from odoo import api, models


class EscposTemplateService(models.AbstractModel):
    _name = "ll.print.escpos.template.service"
    _description = "ESC/POS Template Service"

    @api.model
    def render_restaurant_receipt(self, data):
        lines = []
        lines.append("\x1b@")
        lines.append("\x1ba\x01")
        lines.append((data.get("title") or "RECEIPT").strip()[:32])
        lines.append("\n")
        lines.append("\x1ba\x00")
        header = data.get("header") or {}
        if header.get("order"):
            lines.append(f"Order: {header.get('order')}\n")
        if header.get("table"):
            lines.append(f"Table: {header.get('table')}\n")
        if header.get("date"):
            lines.append(f"Date: {header.get('date')}\n")
        lines.append("--------------------------------\n")
        for item in data.get("items") or []:
            name = (item.get("name") or "").strip()
            qty = item.get("qty") or 1
            price = item.get("price")
            if price is None:
                lines.append(f"{qty}x {name}\n")
            else:
                lines.append(f"{qty}x {name}  {price}\n")
        lines.append("--------------------------------\n")
        if data.get("total") is not None:
            lines.append(f"TOTAL: {data.get('total')}\n")
        if data.get("footer"):
            lines.append(f"{data.get('footer')}\n")
        lines.append("\n\n\n")
        lines.append("\x1dV\x00")
        return "".join(lines)
