from odoo import api, fields, models


class RetryService(models.AbstractModel):
    _name = "ll.print.retry.service"
    _description = "Retry Service"

    @api.model
    def run(self, stuck_minutes=10, batch_limit=500):
        now = fields.Datetime.now()
        Job = self.env["ll.print.platform.job"].sudo()
        Log = self.env["ll.print.platform.log"].sudo()

        due = Job.search(
            [
                ("status", "=", "failed"),
                ("next_retry_at", "!=", False),
                ("next_retry_at", "<=", now),
            ],
            order="next_retry_at asc, priority desc, create_date asc",
            limit=int(batch_limit),
        )
        for job in due:
            if job.retry_count >= job.max_retries:
                continue
            job.write(
                {
                    "status": "pending",
                    "next_retry_at": False,
                    "agent_id": False,
                    "lease_uuid": False,
                    "leased_at": False,
                    "leased_until": False,
                    "acked_at": False,
                }
            )
            Log.create({"job_id": job.id, "timestamp": now, "status": "retry", "message": "Retry released to pending queue."})

        expired = Job.search(
            [
                ("status", "=", "assigned"),
                ("leased_until", "!=", False),
                ("leased_until", "<", now),
            ],
            order="leased_until asc",
            limit=int(batch_limit),
        )
        for job in expired:
            job.write(
                {
                    "status": "pending",
                    "agent_id": False,
                    "lease_uuid": False,
                    "leased_at": False,
                    "leased_until": False,
                    "acked_at": False,
                }
            )
            Log.create({"job_id": job.id, "timestamp": now, "status": "lease_expired", "message": "Lease expired; released to pending queue."})

        self.env["ll.print.queue.service"].sudo().retry_stuck_jobs(minutes=int(stuck_minutes))

        return True
