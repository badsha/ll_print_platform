# Print Master — User Manual

## Overview

Print Master adds agent-based printing to Odoo:

- Odoo queues print jobs (POS receipts, invoices, reports)
- A local agent polls Odoo over HTTP(S) using an API key
- The agent prints locally and updates job status (ack/done/fail)

## Install

1. Install the module **Print Master**.
2. Ensure these dependencies are installed (they are required by the module):
   - Point of Sale
   - Invoicing / Accounting

## Fresh Start (Docker)

If you want to reset everything (database + filestore):

```bash
cd /Users/mohammadhamid/projects/odoo-dev
docker compose down -v --remove-orphans
docker compose up -d --build
```

Then open Odoo:
- `http://127.0.0.1:8069`
- Create a new database (master password: `admin`, from `config/odoo.conf`)

## Initial Setup (Per Company)

1. Open **Printing → Configuration → Printing Setup**.
2. Select the company in **Tenant**.
3. Click **Generate / Load API Key**.
4. Copy the API key and save it for the agent machine.

Notes:
- The API key is stored on the Agent record, not on the wizard.
- You can regenerate the key; the old one stops working immediately.

## Run the Local Agent (MVP)

This repository includes a Go agent in `odoo-print-agent/` which can be packaged separately.

1. Edit the agent config:

   - Default path (recommended):
     - macOS: `~/Library/Application Support/odoo-print-agent/config.json`
     - Linux: `~/.config/odoo-print-agent/config.json`
     - Windows: `%AppData%\\odoo-print-agent\\config.json`
   - If you run the agent from `odoo-print-agent/` and a local `./config.json` exists, it will use that file (convenient for development).
   - Set:
     - `odoo_url` to your Odoo base URL
     - `api_key` to the key from Printing Setup

2. Run the agent:

```bash
cd odoo-print-agent
go run . configure --odoo-url https://YOUR-ODOO-URL --api-key YOUR_API_KEY
go run . doctor
go run . run
```

MVP behavior:
- The agent syncs printers to Odoo (from `config.json`)
- It polls jobs and prints them locally based on each printer mapping:
  - `os_printer_name` (macOS/Linux CUPS queue)
  - `network_host`/`network_port` for LAN raw TCP printers (raw/ESC-POS)
  - otherwise spools to `spool_dir`

## Register Printers

You can register printers from the agent (recommended) or via API manually.

Agent-driven:
- Add printers to `odoo-print-agent/config.json` under `"printers": [...]`
- Run the agent; it will call `/api/print/printers/sync`

Manual API:

```bash
curl -sS -X POST "https://YOUR-ODOO-URL/api/print/printers/sync" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"printers":[{"agent_identifier":"test_printer_1","name":"Test Printer","printer_type":"receipt","code":"TEST1"}]}'
```

Verify in Odoo:
- **Printing → Configuration → Printers**

## POS Receipt Printing

1. Open **Point of Sale → Configuration → Point of Sale**.
2. Open your POS configuration.
3. Enable the Print Master option(s) in the POS configuration (receipt/kitchen printing).
4. Select the target printer(s).
5. Start a POS session and print a receipt.

Verify:
- **Printing → Operations → Jobs** shows new jobs.
- The agent should process jobs and mark them done.

## Invoice Printing

1. Open an invoice/bill.
2. Click **Queue Print**.
3. Select printer and confirm.

Verify:
- **Printing → Operations → Jobs**

## Reports (Any QWeb PDF)

Use **Printing → Operations → Direct Print**:

1. Select a report (PDF)
2. Select a printer
3. Set `record_ids` (comma-separated IDs for the report’s model)
   - To find a record ID: enable Developer Mode and open the record; the URL contains `id=<number>`
   - Easier: launch printing from a document (example: invoice “Queue Print”) so `record_ids` is pre-filled
4. Queue the job

## Printer Defaults (Per Document Type)

Printers support default flags:
- `default_for_invoice`: preferred for invoice reports
- `default_for_report`: preferred for other reports

You can set these on the printer form:
- **Printing → Configuration → Printers**

## Troubleshooting

- API returns `401 Unauthorized`: wrong/missing API key, or key regenerated.
- Jobs stay `pending`: agent not running, wrong Odoo URL, or agent cannot reach Odoo.
- Jobs `failed`: open the job and check the error message and logs.
- Printers missing: run printer sync again from the agent or the `/printers/sync` API.
