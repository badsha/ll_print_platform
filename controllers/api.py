import base64
import time
from odoo import fields, http
from odoo.http import request


_RATE_STATE = {}

def _payload_to_b64(payload):
    if not payload:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, (bytes, bytearray)):
        try:
            return payload.decode("ascii")
        except Exception:
            return base64.b64encode(payload).decode("ascii")
    return ""

def _get_json_body():
    try:
        return request.get_json_data() or {}
    except Exception:
        return {}


def _rate_limit(key, limit, window_seconds):
    if not key:
        return False
    now = time.time()
    window_start = now - window_seconds
    entries = _RATE_STATE.get(key) or []
    entries = [t for t in entries if t >= window_start]
    if len(entries) >= limit:
        _RATE_STATE[key] = entries
        return True
    entries.append(now)
    _RATE_STATE[key] = entries
    return False


def _get_agent_from_request():
    auth_header = request.httprequest.headers.get("Authorization") or ""
    token = ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    api_key = token or request.httprequest.headers.get("X-Print-Agent-Key") or request.params.get("api_key")
    if not api_key:
        return None
    if _rate_limit(api_key, limit=120, window_seconds=60):
        return "rate_limited"
    agent = request.env["ll.print.platform.agent"].sudo().search([("api_key", "=", api_key), ("active", "=", True)], limit=1)
    return agent


class PrintApi(http.Controller):
    @http.route("/api/print/jobs", type="http", auth="none", methods=["GET"], csrf=False)
    def get_jobs(self, **kwargs):
        limit = request.params.get("limit") or 20
        lease_seconds = request.params.get("lease_seconds") or 30
        printer_id = request.params.get("printer_id")
        agent = _get_agent_from_request()
        if agent == "rate_limited":
            return request.make_json_response({"status": "error", "message": "Rate limited."}, status=429)
        if not agent:
            return request.make_json_response({"status": "error", "message": "Unauthorized."}, status=401)

        printer_ids = None
        if printer_id:
            printer_ids = [int(printer_id)]

        jobs = request.env["ll.print.queue.service"].lease_jobs(agent, limit=limit, lease_seconds=lease_seconds, printer_ids=printer_ids)
        return request.make_json_response({
            "status": "success",
            "jobs": [
                {
                    "id": j.id,
                    "name": j.name,
                    "printer_identifier": j.printer_id.agent_identifier,
                    "job_type": j.job_type,
                    "payload": _payload_to_b64(j.payload),
                    "lease_uuid": j.lease_uuid,
                }
                for j in jobs
            ],
        })

    @http.route("/api/print/job/<int:job_id>/ack", type="http", auth="none", methods=["POST"], csrf=False)
    def ack_job(self, job_id, **kwargs):
        data = _get_json_body()
        lease_uuid = data.get("lease_uuid")
        agent = _get_agent_from_request()
        if agent == "rate_limited":
            return request.make_json_response({"status": "error", "message": "Rate limited."}, status=429)
        if not agent:
            return request.make_json_response({"status": "error", "message": "Unauthorized."}, status=401)
        if not lease_uuid:
            return request.make_json_response({"status": "error", "message": "Missing lease_uuid."}, status=400)
        ok = request.env["ll.print.queue.service"].ack(agent, job_id, lease_uuid)
        return request.make_json_response({"status": "success" if ok else "error"}, status=200 if ok else 409)

    @http.route("/api/print/job/<int:job_id>/done", type="http", auth="none", methods=["POST"], csrf=False)
    def done_job(self, job_id, **kwargs):
        data = _get_json_body()
        lease_uuid = data.get("lease_uuid")
        agent = _get_agent_from_request()
        if agent == "rate_limited":
            return request.make_json_response({"status": "error", "message": "Rate limited."}, status=429)
        if not agent:
            return request.make_json_response({"status": "error", "message": "Unauthorized."}, status=401)
        if not lease_uuid:
            return request.make_json_response({"status": "error", "message": "Missing lease_uuid."}, status=400)
        ok = request.env["ll.print.queue.service"].done(agent, job_id, lease_uuid)
        return request.make_json_response({"status": "success" if ok else "error"}, status=200 if ok else 409)

    @http.route("/api/print/job/<int:job_id>/fail", type="http", auth="none", methods=["POST"], csrf=False)
    def fail_job(self, job_id, **kwargs):
        data = _get_json_body()
        lease_uuid = data.get("lease_uuid")
        error_message = data.get("error") or data.get("error_message")
        agent = _get_agent_from_request()
        if agent == "rate_limited":
            return request.make_json_response({"status": "error", "message": "Rate limited."}, status=429)
        if not agent:
            return request.make_json_response({"status": "error", "message": "Unauthorized."}, status=401)
        if not lease_uuid:
            return request.make_json_response({"status": "error", "message": "Missing lease_uuid."}, status=400)
        ok = request.env["ll.print.queue.service"].fail(agent, job_id, lease_uuid, error_message)
        return request.make_json_response({"status": "success" if ok else "error"}, status=200 if ok else 409)

    @http.route("/api/print/printers/sync", type="http", auth="none", methods=["POST"], csrf=False)
    def sync_printers(self, **kwargs):
        data = _get_json_body()
        printers = data.get("printers") or []
        agent = _get_agent_from_request()
        if agent == "rate_limited":
            return request.make_json_response({"status": "error", "message": "Rate limited."}, status=429)
        if not agent:
            return request.make_json_response({"status": "error", "message": "Unauthorized."}, status=401)
        created = []
        for p in printers:
            agent_identifier = (p or {}).get("agent_identifier") or (p or {}).get("identifier")
            name = (p or {}).get("name") or agent_identifier
            printer_type = (p or {}).get("printer_type") or (p or {}).get("type") or "receipt"
            code = (p or {}).get("code") or agent_identifier
            if not agent_identifier:
                continue
            existing = request.env["ll.print.printer"].sudo().search(
                [("tenant_id", "=", agent.tenant_id.id), ("agent_identifier", "=", agent_identifier)],
                limit=1,
            )
            if existing:
                existing.write(
                    {
                        "name": name,
                        "printer_type": printer_type,
                        "agent_id": agent.id,
                        "is_active": True,
                        "code": existing.code or code,
                    }
                )
                created.append(existing.id)
            else:
                rec = request.env["ll.print.printer"].sudo().create(
                    {
                        "name": name,
                        "code": code,
                        "printer_type": printer_type,
                        "agent_identifier": agent_identifier,
                        "tenant_id": agent.tenant_id.id,
                        "agent_id": agent.id,
                        "active": True,
                    }
                )
                created.append(rec.id)
        agent.sudo().write({"last_seen_at": fields.Datetime.now()})
        return request.make_json_response({"status": "success", "printer_ids": created})
