# Print Master (ll_print_platform) — Odoo 19

Odoo App Store: https://apps.odoo.com/apps/modules/19.0/ll_print_platform/

Local print agent repository: https://github.com/badsha/odoo-print-agent

## Overview

Print Master queues print jobs in Odoo (POS receipts, invoices, reports). A **local agent** on a PC with printers polls Odoo over HTTP(S) with an API key, prints locally, and updates job status.

## Install (Odoo module)

1. Install **Print Master** from the App Store (or this repo).
2. Ensure dependencies are installed:
   - Point of Sale
   - Invoicing / Accounting
3. Open **Printing → Configuration → Printing Setup**
4. Select company (Tenant) → **Generate / Load API Key** → copy the key

## Agent setup — choose one path

### Option A — Quick setup (Windows, recommended for shops)

1. Open the latest agent release: https://github.com/badsha/odoo-print-agent/releases/latest
2. Download the **Windows EXE** from **Assets** (when published).
3. Run:

```text
odoo-print-agent.exe configure --odoo-url http://YOUR-ODOO:8069 --database YOUR_DB --api-key YOUR_KEY
odoo-print-agent.exe doctor
odoo-print-agent.exe run
```

4. Optional: `odoo-print-agent.exe install` (elevated) to run as a Windows service.

### Option B — Manual / build from source (developers)

1. Install [Go](https://go.dev/dl/)
2. Clone https://github.com/badsha/odoo-print-agent
3. Build and run:

```bash
cd odoo-print-agent
go build -o odoo-print-agent.exe .   # Windows
# or: go run . ...

go run . configure --odoo-url http://YOUR-ODOO:8069 --database YOUR_DB --api-key YOUR_KEY
go run . doctor
go run . run
```

### Windows extras

- **wkhtmltopdf** must be available to the Odoo server (PATH) for invoice PDFs.
- **SumatraPDF** is used by the agent for PDF and POS receipt image printing on Windows (`sumatra_pdf_path` in config if needed).
- If Odoo hosts **multiple databases**, set `database` in the agent config (or `--database`).

## POS printing

1. **Point of Sale → Configuration → Point of Sale** → your POS
2. Enable **Print Master** → select Receipt Printer (and Kitchen if needed)
3. Save → start a **new** POS session → print a receipt
4. Check **Printing → Operations → Jobs**

## Invoice printing

1. Open invoice → **Queue Print** → choose printer
2. Verify job in **Printing → Operations → Jobs**

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `401 Unauthorized` | Wrong/regenerated API key |
| Jobs stay `pending` | Agent not running / wrong URL |
| `404` / API missing | Multi-DB: set agent `database` |
| POS checkbox missing | Upgrade to this module version |
| Windows raw/POS fail | Use updated agent + Sumatra |

## License

LGPL-3 (see module manifest)
