import datetime
from odoo import api, fields, models


class DispatchService(models.AbstractModel):
    _name = "ll.print.queue.service"
    _description = "Queue Service"

    @api.model
    def lease_jobs(self, agent, limit=20, lease_seconds=30, printer_ids=None):
        if not agent or not agent.exists() or not agent.active:
            return []
        now = fields.Datetime.now()
        leased_until = now + datetime.timedelta(seconds=int(lease_seconds))

        domain = [
            ("tenant_id", "=", agent.tenant_id.id),
            ("status", "in", ["pending", "failed"]),
            "|",
            ("next_retry_at", "=", False),
            ("next_retry_at", "<=", now),
            "|",
            ("leased_until", "=", False),
            ("leased_until", "<", now),
        ]
        if printer_ids:
            domain.append(("printer_id", "in", list(printer_ids)))
        else:
            allowed = agent.allowed_printer_ids
            if allowed:
                domain.append(("printer_id", "in", allowed.ids))

        candidates = self.env["ll.print.platform.job"].sudo().search(domain, order="priority desc, create_date asc", limit=int(limit) * 3)
        jobs = candidates.filtered(lambda j: j.status == "pending" or j.retry_count < j.max_retries)[: int(limit)]
        for job in jobs:
            job.mark_leased(agent, leased_until)
        agent.sudo().write({"last_seen_at": now})
        return jobs

    @api.model
    def ack(self, agent, job_id, lease_uuid):
        job = self.env["ll.print.platform.job"].sudo().browse(int(job_id))
        if not job.exists() or job.tenant_id.id != agent.tenant_id.id:
            return False
        if job.lease_uuid != lease_uuid or job.agent_id.id != agent.id:
            return False
        job.mark_assigned()
        return True

    @api.model
    def mark_printing(self, agent, job_id, lease_uuid):
        job = self.env["ll.print.platform.job"].sudo().browse(int(job_id))
        if not job.exists() or job.tenant_id.id != agent.tenant_id.id:
            return False
        if job.lease_uuid != lease_uuid or job.agent_id.id != agent.id:
            return False
        job.mark_printing()
        return True

    @api.model
    def done(self, agent, job_id, lease_uuid):
        job = self.env["ll.print.platform.job"].sudo().browse(int(job_id))
        if not job.exists() or job.tenant_id.id != agent.tenant_id.id:
            return False
        if job.lease_uuid != lease_uuid or job.agent_id.id != agent.id:
            return False
        job.mark_done()
        return True

    @api.model
    def fail(self, agent, job_id, lease_uuid, error_message):
        job = self.env["ll.print.platform.job"].sudo().browse(int(job_id))
        if not job.exists() or job.tenant_id.id != agent.tenant_id.id:
            return False
        if job.lease_uuid != lease_uuid or job.agent_id.id != agent.id:
            return False
        job.mark_failed(error_message or "Agent reported failure.")
        if job.can_retry():
            job.schedule_retry(job.compute_next_retry_at())
        return True

    @api.model
    def retry_stuck_jobs(self, minutes=10):
        now = fields.Datetime.now()
        cutoff = now - datetime.timedelta(minutes=int(minutes))
        stuck = self.env["ll.print.platform.job"].sudo().search([("status", "=", "printing"), ("write_date", "<=", cutoff)])
        for job in stuck:
            job.mark_failed("Job stuck in printing state.")
            if job.can_retry():
                job.schedule_retry(job.compute_next_retry_at())
