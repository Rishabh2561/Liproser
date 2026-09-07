import asyncio
from datetime import UTC, datetime, timedelta

from liproser.database import DeadLetter, JobRun, OutboxEvent, PostSchedule, PublishAction, engine
from liproser.schedule_service import mark_reminder_due
from liproser.worker import dispatch_outbox
from sqlalchemy import func, select
from sqlalchemy.orm import Session

VOICE = {
    "domain": "Software Engineering",
    "target_audience": "backend engineers",
    "content_pillars": ["API Design", "Reliability"],
    "tone_preferences": ["practical"],
    "prohibited_phrases": ["game changer"],
    "samples": [
        "I explain engineering trade-offs using concrete examples and direct takeaways.",
        "Reliable systems begin with explicit ownership and observable failure modes.",
        "Good technical leadership makes constraints visible before teams commit.",
    ],
    "samples_are_user_owned": True,
}


def make_draft(client, topic: str):
    idea = client.post(
        "/v1/content-ideas",
        json={
            "pillar": "API Design",
            "topic": topic,
            "angle": f"{topic} should make ownership explicit.",
            "audience_intent": "Help backend engineers make safer decisions.",
            "format": "TEXT",
            "evidence": [],
            "evidence_confirmed": True,
        },
    ).json()
    return client.post(f"/v1/content-ideas/{idea['id']}/primary-draft").json()


def approve(client, draft):
    assert client.post(
        f"/v1/posts/{draft['post_id']}/submit-review",
        json={"revision_id": draft["revision_id"]},
    ).status_code == 200
    response = client.post(
        f"/v1/posts/{draft['post_id']}/reviews",
        json={"revision_id": draft["revision_id"], "action": "APPROVE", "claims_confirmed": True},
    )
    assert response.status_code == 200
    return response.json()


def schedule(client, draft, key="schedule-test-0001"):
    local = (datetime.now(UTC) + timedelta(days=2)).replace(tzinfo=None, second=0, microsecond=0)
    return client.post(
        f"/v1/posts/{draft['post_id']}/schedules",
        json={"revision_id": draft["revision_id"], "intended_local_at": local.isoformat(), "timezone": "UTC", "idempotency_key": key},
    )


def test_calendar_balances_pillars_and_respects_quiet_days(client):
    assert client.post("/v1/voice-profiles", json=VOICE).status_code == 201
    start = (datetime.now(UTC) + timedelta(days=1)).date()
    response = client.post(
        "/v1/calendars",
        json={"start_date": start.isoformat(), "weeks": 2, "cadence_per_week": 3, "timezone": "UTC", "quiet_days": ["SATURDAY", "SUNDAY"]},
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["slots"]) == 6
    assert [item["pillar"] for item in body["slots"][:4]] == ["API Design", "Reliability", "API Design", "Reliability"]
    assert all(datetime.fromisoformat(item["intended_local_at"]).strftime("%A").upper() not in body["quiet_days"] for item in body["slots"])
    assert client.get("/v1/calendars/current").json()["id"] == body["id"]
    invalid = client.post(
        "/v1/calendars",
        json={"start_date": start.isoformat(), "weeks": 1, "cadence_per_week": 2, "timezone": "UTC", "quiet_days": ["TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]},
    )
    assert invalid.status_code == 422


def test_only_exact_approval_schedules_and_edit_cancels_it(client):
    client.post("/v1/voice-profiles", json=VOICE)
    draft = make_draft(client, "Retry contracts")
    assert schedule(client, draft).status_code == 409
    approved = approve(client, draft)
    created = schedule(client, approved)
    assert created.status_code == 201
    assert created.json()["status"] == "ACTIVE"
    duplicate = schedule(client, approved)
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == created.json()["id"]
    changed_payload = {
        "revision_id": approved["revision_id"],
        "intended_local_at": (datetime.now(UTC) + timedelta(days=3)).replace(tzinfo=None, second=0, microsecond=0).isoformat(),
        "timezone": "UTC",
        "idempotency_key": "schedule-test-0001",
    }
    assert client.post(f"/v1/posts/{approved['post_id']}/schedules", json=changed_payload).status_code == 409
    edited = client.post(
        f"/v1/posts/{draft['post_id']}/edits",
        json={"revision_id": draft["revision_id"], "hook": "Retry ownership must be named.", "body": draft["body"], "cta": draft["cta"], "claims_confirmed": True},
    )
    assert edited.status_code == 201
    assert client.get("/v1/schedules").json()[0]["status"] == "CANCELLED"
    with Session(engine) as db:
        assert mark_reminder_due(db, created.json()["id"], "cancelled-schedule-job") is None
        db.commit()
        assert db.scalar(select(func.count()).select_from(JobRun)) == 0


def test_copy_publish_requires_explicit_confirmation_and_is_idempotent(client):
    client.post("/v1/voice-profiles", json=VOICE)
    approved = approve(client, make_draft(client, "Terminal failures"))
    scheduled = schedule(client, approved, "schedule-test-0002").json()
    action_response = client.post(
        f"/v1/schedules/{scheduled['id']}/publish-now",
        json={"revision_id": approved["revision_id"], "idempotency_key": "publish-test-0002"},
    )
    assert action_response.status_code == 200
    action = action_response.json()
    assert action["state"] == "ACTION_REQUIRED"
    assert action["formatted_content"] == approved["content"]
    replay = client.post(
        f"/v1/schedules/{scheduled['id']}/publish-now",
        json={"revision_id": approved["revision_id"], "idempotency_key": "a-different-action-key"},
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == action["id"]
    confirmed = client.post(
        f"/v1/publish-actions/{action['id']}/confirm",
        json={"published_url": "https://www.linkedin.com/feed/update/example"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["state"] == "PUBLISHED"
    assert client.post(f"/v1/publish-actions/{action['id']}/confirm", json={}).json()["id"] == action["id"]
    assert client.get("/v1/memory/revisions").json()[0]["revision_id"] == approved["revision_id"]
    edited = client.post(
        f"/v1/posts/{approved['post_id']}/edits",
        json={"revision_id": approved["revision_id"], "hook": "A new follow-up to terminal failures.", "body": approved["body"], "cta": approved["cta"], "claims_confirmed": True},
    )
    assert edited.status_code == 201
    assert client.get("/v1/memory/revisions").json()[0]["revision_id"] == approved["revision_id"]


def test_edit_invalidates_unconfirmed_publish_action(client):
    client.post("/v1/voice-profiles", json=VOICE)
    approved = approve(client, make_draft(client, "Stale publication"))
    scheduled = schedule(client, approved, "schedule-test-stale").json()
    action = client.post(
        f"/v1/schedules/{scheduled['id']}/publish-now",
        json={"revision_id": approved["revision_id"], "idempotency_key": "publish-test-stale"},
    ).json()
    edited = client.post(
        f"/v1/posts/{approved['post_id']}/edits",
        json={"revision_id": approved["revision_id"], "hook": "This revision changed before publishing.", "body": approved["body"], "cta": approved["cta"], "claims_confirmed": True},
    )
    assert edited.status_code == 201
    assert client.get(f"/v1/publish-actions/{action['id']}").json()["state"] == "FAILED"
    assert client.post(f"/v1/publish-actions/{action['id']}/confirm", json={}).status_code == 409


def test_publish_failure_keeps_reason_out_of_event_payload(client):
    client.post("/v1/voice-profiles", json=VOICE)
    approved = approve(client, make_draft(client, "Manual publication failure"))
    scheduled = schedule(client, approved, "schedule-test-failure").json()
    action = client.post(
        f"/v1/schedules/{scheduled['id']}/publish-now",
        json={"revision_id": approved["revision_id"], "idempotency_key": "publish-test-failure"},
    ).json()
    reason = "LinkedIn rejected the manual post"
    failed = client.post(f"/v1/publish-actions/{action['id']}/fail", json={"reason": reason})
    assert failed.status_code == 200
    assert failed.json()["failure_reason"] == reason
    with Session(engine) as db:
        event = db.scalar(select(OutboxEvent).where(OutboxEvent.event_type == "publish.failed"))
        assert event.payload == {"publish_action_id": action["id"]}


def test_reminder_job_is_idempotent(client):
    client.post("/v1/voice-profiles", json=VOICE)
    approved = approve(client, make_draft(client, "Timeout ownership"))
    scheduled = schedule(client, approved, "schedule-test-0003").json()
    with Session(engine) as db:
        item = db.get(PostSchedule, scheduled["id"])
        item.resolved_utc_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
        first = mark_reminder_due(db, item.id, "job-reminder-0003")
        db.commit()
        second = mark_reminder_due(db, item.id, "job-reminder-0003")
        assert first.id == second.id
        assert db.scalar(select(func.count()).select_from(PublishAction)) == 1
        assert db.scalar(select(func.count()).select_from(JobRun)) == 1


def test_outbox_dispatch_is_idempotent_and_dead_letters_after_bounded_retries(client):
    class FakeRedis:
        def __init__(self, fails=False):
            self.fails = fails
            self.calls = []

        async def enqueue_job(self, *args, **kwargs):
            if self.fails:
                raise ConnectionError("controlled queue failure")
            self.calls.append((args, kwargs))

    client.post("/v1/voice-profiles", json=VOICE)
    approved = approve(client, make_draft(client, "Queue ownership"))
    schedule(client, approved, "schedule-test-0004")
    queue = FakeRedis()
    assert asyncio.run(dispatch_outbox({"redis": queue})) >= 1
    assert len(queue.calls) == 1
    assert asyncio.run(dispatch_outbox({"redis": queue})) == 0

    with Session(engine) as db:
        event = db.scalar(select(OutboxEvent).where(OutboxEvent.event_type == "post.scheduled"))
        event.delivered_at = None
        event.attempts = 0
        db.commit()
    failing_queue = FakeRedis(fails=True)
    for _ in range(5):
        asyncio.run(dispatch_outbox({"redis": failing_queue}))
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(DeadLetter)) == 1
        assert db.scalar(select(OutboxEvent).where(OutboxEvent.event_type == "post.scheduled")).delivered_at is not None


def test_missing_or_late_schedule_job_persists_nothing(client):
    with Session(engine) as db:
        assert mark_reminder_due(db, "missing-schedule", "missing-job") is None
        db.commit()
        assert db.scalar(select(func.count()).select_from(JobRun)) == 0


def test_repeated_feedback_creates_reversible_preference(client):
    client.post("/v1/voice-profiles", json=VOICE)
    for index in range(2):
        draft = make_draft(client, f"Feedback topic {index}")
        client.post(f"/v1/posts/{draft['post_id']}/submit-review", json={"revision_id": draft["revision_id"]})
        response = client.post(
            f"/v1/posts/{draft['post_id']}/reviews",
            json={"revision_id": draft["revision_id"], "action": "REQUEST_CHANGES", "reason": "Make the opening direct.", "categories": ["HOOK"]},
        )
        assert response.status_code == 200
    preferences = client.get("/v1/feedback/preferences").json()
    assert len(preferences) == 1
    assert preferences[0]["evidence_count"] == 2
    disabled = client.patch(f"/v1/feedback/preferences/{preferences[0]['id']}", json={"active": False})
    assert disabled.status_code == 200
    assert disabled.json()["active"] is False
