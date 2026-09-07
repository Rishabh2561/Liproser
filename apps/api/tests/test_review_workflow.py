from liproser.database import EditDelta, PostRevision, Review, RevisionCheck, engine
from sqlalchemy import func, select
from sqlalchemy.orm import Session

VOICE = {
    "domain": "Software Engineering",
    "target_audience": "backend engineers and engineering leaders",
    "content_pillars": ["API Design"],
    "tone_preferences": ["practical", "clear"],
    "prohibited_phrases": ["game changer"],
    "samples": [
        "I explain engineering trade-offs using concrete examples and direct takeaways.",
        "Reliable systems begin with explicit ownership and observable failure modes.",
        "Good technical leadership makes constraints visible before committing a team.",
    ],
    "samples_are_user_owned": True,
}

IDEA = {
    "pillar": "API Design",
    "topic": "Designing explicit retry contracts",
    "angle": "Retry behavior should name ownership and terminal failure states.",
    "audience_intent": "Help backend engineers review retry behavior before deployment.",
    "format": "TEXT",
    "evidence": [],
    "evidence_confirmed": True,
}


def create_draft(client):
    assert client.post("/v1/voice-profiles", json=VOICE).status_code == 201
    idea = client.post("/v1/content-ideas", json=IDEA).json()
    response = client.post(f"/v1/content-ideas/{idea['id']}/primary-draft")
    assert response.status_code == 201
    return response.json()


def submit(client, draft):
    return client.post(
        f"/v1/posts/{draft['post_id']}/submit-review",
        json={"revision_id": draft["revision_id"]},
    )


def test_approval_requires_exact_current_revision_and_human_confirmation(client):
    draft = create_draft(client)
    assert len(draft["checks"]) == 4
    approval = {
        "revision_id": draft["revision_id"],
        "action": "APPROVE",
        "claims_confirmed": True,
    }
    assert client.post(f"/v1/posts/{draft['post_id']}/reviews", json=approval).status_code == 409
    in_review = submit(client, draft)
    assert in_review.status_code == 200
    assert in_review.json()["state"] == "IN_REVIEW"
    unconfirmed = client.post(
        f"/v1/posts/{draft['post_id']}/reviews",
        json={**approval, "claims_confirmed": False},
    )
    assert unconfirmed.status_code == 422
    approved = client.post(f"/v1/posts/{draft['post_id']}/reviews", json=approval)
    assert approved.status_code == 200
    assert approved.json()["state"] == "APPROVED"
    assert [event["action"] for event in approved.json()["reviews"]] == ["SUBMIT", "APPROVE"]

    edited = client.post(
        f"/v1/posts/{draft['post_id']}/edits",
        json={
            "revision_id": draft["revision_id"],
            "hook": "Retry contracts need a named owner.",
            "body": draft["body"],
            "cta": draft["cta"],
            "claims_confirmed": True,
        },
    )
    assert edited.status_code == 201
    revised = edited.json()
    assert revised["state"] == "DRAFT"
    assert revised["revision_number"] == 2
    assert revised["generation_mode"] == "human_edit"
    assert client.post(f"/v1/posts/{draft['post_id']}/reviews", json=approval).status_code == 409


def test_blocking_check_prevents_approval_and_edit_delta_is_immutable(client):
    draft = create_draft(client)
    edited = client.post(
        f"/v1/posts/{draft['post_id']}/edits",
        json={
            "revision_id": draft["revision_id"],
            "hook": "A game changer for retry design.",
            "body": draft["body"],
            "cta": draft["cta"],
            "claims_confirmed": True,
        },
    ).json()
    blocked = next(check for check in edited["checks"] if check["check_type"] == "PROHIBITED_PHRASES")
    assert blocked["severity"] == "BLOCKING"
    assert blocked["passed"] is False
    assert submit(client, edited).status_code == 200
    response = client.post(
        f"/v1/posts/{draft['post_id']}/reviews",
        json={
            "revision_id": edited["revision_id"],
            "action": "APPROVE",
            "claims_confirmed": True,
        },
    )
    assert response.status_code == 409
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(EditDelta)) == 1
        assert db.scalar(select(func.count()).select_from(PostRevision)) == 2


def test_request_changes_and_regeneration_preserve_structured_feedback(client):
    draft = create_draft(client)
    assert submit(client, draft).status_code == 200
    requested = client.post(
        f"/v1/posts/{draft['post_id']}/reviews",
        json={
            "revision_id": draft["revision_id"],
            "action": "REQUEST_CHANGES",
            "reason": "Make the opening more direct.",
            "categories": ["HOOK", "CLARITY"],
        },
    )
    assert requested.status_code == 200
    assert requested.json()["state"] == "CHANGES_REQUESTED"
    regenerated = client.post(
        f"/v1/posts/{draft['post_id']}/regenerations",
        json={"revision_id": draft["revision_id"]},
    )
    assert regenerated.status_code == 201
    body = regenerated.json()
    assert body["state"] == "DRAFT"
    assert body["revision_number"] == 2
    assert body["hook"] == "Designing explicit retry contracts, stated plainly:"
    assert "category-based regeneration" in body["generation_warning"]
    actions = [event["action"] for event in body["reviews"]]
    assert actions == ["SUBMIT", "REQUEST_CHANGES", "REGENERATE"]
    regeneration = body["reviews"][-1]
    assert [event["revision_number"] for event in body["reviews"]] == [1, 1, 2]
    assert regeneration["categories"] == ["HOOK", "CLARITY"]
    assert regeneration["reason"] == "Make the opening more direct."
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Review)) == 3
        assert db.scalar(select(func.count()).select_from(EditDelta)) == 1


def test_rejection_requires_reason_and_is_terminal(client):
    draft = create_draft(client)
    assert submit(client, draft).status_code == 200
    missing_reason = client.post(
        f"/v1/posts/{draft['post_id']}/reviews",
        json={"revision_id": draft["revision_id"], "action": "REJECT"},
    )
    assert missing_reason.status_code == 422
    rejected = client.post(
        f"/v1/posts/{draft['post_id']}/reviews",
        json={
            "revision_id": draft["revision_id"],
            "action": "REJECT",
            "reason": "This topic is not useful for my audience.",
        },
    )
    assert rejected.status_code == 200
    assert rejected.json()["state"] == "REJECTED"
    edit = client.post(
        f"/v1/posts/{draft['post_id']}/edits",
        json={
            "revision_id": draft["revision_id"],
            "hook": "A different hook.",
            "body": draft["body"],
            "cta": draft["cta"],
            "claims_confirmed": True,
        },
    )
    assert edit.status_code == 409


def test_legacy_draft_checks_are_backfilled_before_review(client):
    draft = create_draft(client)
    with Session(engine) as db:
        checks = db.scalars(
            select(RevisionCheck).where(RevisionCheck.post_revision_id == draft["revision_id"])
        ).all()
        for check in checks:
            db.delete(check)
        db.commit()
    response = submit(client, draft)
    assert response.status_code == 200
    assert len(response.json()["checks"]) == 4
