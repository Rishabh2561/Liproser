from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import (
    BOOTSTRAP_WORKSPACE_ID,
    CalendarSlot,
    ContentCalendar,
    FeedbackSignal,
    JobRun,
    OutboxEvent,
    Post,
    PostRevision,
    PostSchedule,
    PreferenceRule,
    PublishAction,
    Review,
    VoiceProfile,
)

WEEKDAYS = ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY")
PREFERENCE_TEXT = {
    "HOOK": "Prefer a more direct opening hook.",
    "TONE": "Adjust tone using the recorded review context.",
    "CLARITY": "Prefer plain, explicit wording.",
    "CTA": "Use a more specific closing prompt.",
    "LENGTH": "Review post length before approval.",
    "EVIDENCE": "Strengthen or remove unsupported factual claims.",
    "EDIT_HOOK": "Expect manual refinement of opening hooks.",
    "EDIT_BODY": "Expect manual refinement of the post body.",
    "EDIT_CTA": "Expect manual refinement of closing prompts.",
    "REJECT": "Check topic fit before drafting.",
}


def resolve_local(value: datetime, timezone: str, fold: int | None = None) -> tuple[str, datetime]:
    if value.tzinfo is not None:
        raise ValueError("intended_local_at must not include an offset")
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Unknown IANA timezone") from exc
    variants = []
    for candidate_fold in (0, 1):
        aware = value.replace(tzinfo=zone, fold=candidate_fold)
        utc_value = aware.astimezone(UTC)
        if utc_value.astimezone(zone).replace(tzinfo=None) == value:
            variants.append((candidate_fold, aware.utcoffset(), utc_value))
    unique = {(offset, instant) for _, offset, instant in variants}
    if not variants:
        raise ValueError("Local time does not exist because of a daylight-saving transition")
    if len(unique) > 1 and fold is None:
        raise ValueError("Local time is ambiguous; choose dst_fold 0 or 1")
    selected = next((item for item in variants if item[0] == (fold or 0)), variants[0])
    return value.isoformat(timespec="minutes"), selected[2]


def add_outbox(db: Session, event_type: str, aggregate_id: str, dedupe_key: str, payload: dict, available_at: datetime | None = None) -> None:
    db.add(OutboxEvent(id=str(uuid4()), event_type=event_type, aggregate_id=aggregate_id, payload=payload, dedupe_key=dedupe_key, available_at=available_at or datetime.now(UTC)))


def build_calendar(db: Session, voice: VoiceProfile, start: date, weeks: int, cadence: int, timezone: str, quiet_days: list[str]) -> ContentCalendar:
    allowed = [index for index, name in enumerate(WEEKDAYS) if name not in quiet_days]
    if cadence > len(allowed):
        raise ValueError("Cadence exceeds available non-quiet days")
    calendar = ContentCalendar(id=str(uuid4()), voice_profile_id=voice.id, start_date=start.isoformat(), weeks=weeks, cadence_per_week=cadence, timezone=timezone, quiet_days=quiet_days)
    db.add(calendar)
    db.flush()
    position = 0
    for week in range(weeks):
        candidates = [start + timedelta(days=week * 7 + offset) for offset in range(7)]
        for slot_date in [item for item in candidates if item.weekday() in allowed][:cadence]:
            local_value = datetime.combine(slot_date, time(9, 0))
            local_text, utc_value = resolve_local(local_value, timezone, 0)
            db.add(CalendarSlot(id=str(uuid4()), calendar_id=calendar.id, position=position + 1, pillar=voice.content_pillars[position % len(voice.content_pillars)], intended_local_at=local_text, resolved_utc_at=utc_value))
            position += 1
    if position == 0:
        raise ValueError("No calendar slots could be created")
    add_outbox(db, "calendar.created", calendar.id, f"calendar:{calendar.id}", {"calendar_id": calendar.id})
    return calendar


def exact_approval_valid(db: Session, post: Post, revision: PostRevision) -> bool:
    latest = db.scalar(select(func.max(PostRevision.revision_number)).where(PostRevision.post_id == post.id))
    approval = db.scalar(select(Review.id).where(Review.revision_id == revision.id, Review.action == "APPROVE"))
    return post.state == "APPROVED" and revision.revision_number == latest and bool(approval)


def create_publish_action(db: Session, schedule: PostSchedule, idempotency_key: str) -> PublishAction:
    schedule_action = db.scalar(select(PublishAction).where(PublishAction.schedule_id == schedule.id))
    if schedule_action:
        return schedule_action
    existing = db.scalar(select(PublishAction).where(PublishAction.workspace_id == BOOTSTRAP_WORKSPACE_ID, PublishAction.idempotency_key == idempotency_key))
    if existing:
        if existing.schedule_id != schedule.id:
            raise ValueError("Idempotency key belongs to another publication action")
        return existing
    post, revision = db.get(Post, schedule.post_id), db.get(PostRevision, schedule.revision_id)
    if not post or not revision or post.state != "SCHEDULED":
        raise ValueError("The exact approved revision is no longer publishable")
    action = PublishAction(id=str(uuid4()), schedule_id=schedule.id, post_id=post.id, revision_id=revision.id, formatted_content=revision.content, idempotency_key=idempotency_key)
    db.add(action)
    post.state = "PUBLISH_ACTION_REQUIRED"
    schedule.status = "REMINDER_DUE"
    add_outbox(db, "publish.reminder_due", schedule.id, f"reminder:{schedule.id}", {"schedule_id": schedule.id, "revision_id": revision.id})
    return action


def mark_reminder_due(db: Session, schedule_id: str, idempotency_key: str, now: datetime | None = None) -> PublishAction | None:
    prior = db.scalar(select(JobRun).where(JobRun.workspace_id == BOOTSTRAP_WORKSPACE_ID, JobRun.idempotency_key == idempotency_key))
    if prior:
        return db.scalar(select(PublishAction).where(PublishAction.schedule_id == schedule_id))
    schedule = db.get(PostSchedule, schedule_id)
    if not schedule or schedule.workspace_id != BOOTSTRAP_WORKSPACE_ID or schedule.status != "ACTIVE":
        return None
    instant = now or datetime.now(UTC)
    due = schedule.resolved_utc_at
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    if instant < due:
        return None
    action = create_publish_action(db, schedule, f"schedule:{schedule.id}:reminder")
    db.add(JobRun(id=str(uuid4()), job_type="publish.reminder_due", aggregate_id=schedule.id, idempotency_key=idempotency_key, status="SUCCEEDED"))
    return action


def record_feedback(db: Session, post_id: str, revision_id: str, categories: list[str], detail: str) -> None:
    for category in categories:
        db.add(FeedbackSignal(id=str(uuid4()), post_id=post_id, revision_id=revision_id, category=category, detail=detail))
    add_outbox(db, "feedback.recorded", post_id, f"feedback:{uuid4()}", {"post_id": post_id, "revision_id": revision_id, "categories": categories})


def synthesize_preferences(db: Session) -> list[PreferenceRule]:
    counts = db.execute(select(FeedbackSignal.category, func.count(FeedbackSignal.id)).where(FeedbackSignal.workspace_id == BOOTSTRAP_WORKSPACE_ID).group_by(FeedbackSignal.category)).all()
    for category, count in counts:
        if count < 2:
            continue
        rule = db.scalar(select(PreferenceRule).where(PreferenceRule.workspace_id == BOOTSTRAP_WORKSPACE_ID, PreferenceRule.category == category))
        if rule is None:
            db.add(PreferenceRule(id=str(uuid4()), category=category, instruction=PREFERENCE_TEXT.get(category, "Review this repeated preference."), evidence_count=count, active=True))
        elif rule.evidence_count != count:
            rule.evidence_count = count
            rule.version += 1
            rule.updated_at = datetime.now(UTC)
    db.flush()
    return list(db.scalars(select(PreferenceRule).where(PreferenceRule.workspace_id == BOOTSTRAP_WORKSPACE_ID).order_by(PreferenceRule.category)).all())
