from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import select

from .config import get_settings
from .database import DeadLetter, OutboxEvent, SessionLocal
from .schedule_service import mark_reminder_due


async def dispatch_outbox(ctx: dict) -> int:
    dispatched = 0
    with SessionLocal() as db:
        events = db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.delivered_at.is_(None))
            .order_by(OutboxEvent.available_at, OutboxEvent.id)
            .limit(100)
        ).all()
        for event in events:
            try:
                if event.event_type == "post.scheduled":
                    await ctx["redis"].enqueue_job(
                        "reminder_due",
                        event.payload["schedule_id"],
                        f"job:{event.dedupe_key}",
                        _defer_until=event.available_at,
                        _job_id=event.dedupe_key,
                    )
                event.delivered_at = datetime.now(UTC)
                event.attempts += 1
                dispatched += 1
            except Exception as exc:
                event.attempts += 1
                event.last_error = str(exc)[:500]
                if event.attempts >= 5:
                    db.add(
                        DeadLetter(
                            id=str(uuid4()),
                            job_type=event.event_type,
                            aggregate_id=event.aggregate_id,
                            payload=event.payload,
                            error=event.last_error,
                        )
                    )
                    event.delivered_at = datetime.now(UTC)
            db.commit()
    return dispatched


async def reminder_due(_ctx: dict, schedule_id: str, idempotency_key: str) -> str:
    with SessionLocal() as db:
        action = mark_reminder_due(db, schedule_id, idempotency_key)
        db.commit()
        return action.id if action else "SKIPPED"


class WorkerSettings:
    functions = [dispatch_outbox, reminder_due]
    cron_jobs = [cron(dispatch_outbox, second={0, 10, 20, 30, 40, 50})]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 5
    job_timeout = 30
