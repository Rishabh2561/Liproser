from liproser.database import (
    PostRevision,
    RevisionEmbedding,
    RevisionMemoryEligibility,
    RevisionRetrieval,
    Workspace,
    engine,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

VOICE = {
    "domain": "Software Engineering",
    "target_audience": "backend engineers",
    "content_pillars": ["API Design"],
    "tone_preferences": ["practical"],
    "prohibited_phrases": ["game changer"],
    "samples": [
        "I explain engineering trade-offs using concrete examples and direct takeaways.",
        "Reliable systems begin with explicit ownership and observable failure modes.",
        "Good technical leadership makes constraints visible before teams commit.",
    ],
    "samples_are_user_owned": True,
}


def idea(topic: str, angle: str) -> dict:
    return {
        "pillar": "API Design",
        "topic": topic,
        "angle": angle,
        "audience_intent": "Help backend engineers make safer design decisions.",
        "format": "TEXT",
        "evidence": [],
        "evidence_confirmed": True,
    }


def draft(client, payload: dict) -> dict:
    saved = client.post("/v1/content-ideas", json=payload).json()
    response = client.post(f"/v1/content-ideas/{saved['id']}/primary-draft")
    assert response.status_code == 201
    return response.json()


def approve(client, item: dict) -> dict:
    assert client.post(
        f"/v1/posts/{item['post_id']}/submit-review",
        json={"revision_id": item["revision_id"]},
    ).status_code == 200
    response = client.post(
        f"/v1/posts/{item['post_id']}/reviews",
        json={
            "revision_id": item["revision_id"],
            "action": "APPROVE",
            "claims_confirmed": True,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_only_valid_exact_approval_enters_and_leaves_memory(client):
    assert client.post("/v1/voice-profiles", json=VOICE).status_code == 201
    first = draft(client, idea("Retry ownership", "A retry contract should identify its owner."))
    assert client.get("/v1/memory/revisions").json() == []

    approved = approve(client, first)
    library = client.get("/v1/memory/revisions")
    assert library.status_code == 200
    assert [item["revision_id"] for item in library.json()] == [approved["revision_id"]]
    assert library.json()[0]["embedding_version"] == "hash-embedding@1"

    edited = client.post(
        f"/v1/posts/{first['post_id']}/edits",
        json={
            "revision_id": first["revision_id"],
            "hook": "Retry ownership must be explicit.",
            "body": first["body"],
            "cta": first["cta"],
            "claims_confirmed": True,
        },
    )
    assert edited.status_code == 201
    assert client.get("/v1/memory/revisions").json() == []
    with Session(engine) as db:
        status = db.get(RevisionMemoryEligibility, first["revision_id"])
        assert status.eligible is False
        assert status.reason == "SUPERSEDED_UNPUBLISHED"


def test_generation_records_traceable_retrieval_and_checks(client):
    assert client.post("/v1/voice-profiles", json=VOICE).status_code == 201
    first = approve(
        client,
        draft(client, idea("Retry ownership", "A retry contract should identify its owner.")),
    )
    second = draft(
        client,
        idea("Retry failure", "A retry contract should make terminal failure visible."),
    )
    assert second["retrieved_revision_ids"] == [first["revision_id"]]
    assert len(second["retrievals"]) == 1
    reference = second["retrievals"][0]
    assert reference["revision_id"] == first["revision_id"]
    assert reference["embedding_version"] == "hash-embedding@1"
    assert reference["taxonomy_version"] == second["taxonomy_version"]
    assert set(reference["features"]) == {
        "hook_style",
        "word_count",
        "paragraph_count",
        "cta_style",
    }
    assert {check["check_type"] for check in second["checks"]} >= {
        "ORIGINALITY",
        "DIVERSITY",
    }
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(RevisionEmbedding)) == 1
        assert db.scalar(select(func.count()).select_from(RevisionRetrieval)) == 1
        stored = db.scalar(
            select(PostRevision).where(PostRevision.id == second["revision_id"])
        )
        assert stored.retrieved_revision_ids == [first["revision_id"]]


def test_cross_workspace_status_is_never_retrieved(client):
    assert client.post("/v1/voice-profiles", json=VOICE).status_code == 201
    approved = approve(
        client,
        draft(client, idea("Retry ownership", "A retry contract should identify its owner.")),
    )
    with Session(engine) as db:
        db.add(Workspace(id="00000000-0000-0000-0000-000000000099", name="Other"))
        status = db.get(RevisionMemoryEligibility, approved["revision_id"])
        status.workspace_id = "00000000-0000-0000-0000-000000000099"
        db.commit()
    assert client.get("/v1/memory/revisions").json() == []
    unrelated = draft(
        client,
        idea("Retry failure", "A retry contract should make terminal failure visible."),
    )
    assert unrelated["retrievals"] == []


def test_duplicate_of_eligible_revision_fails_originality_gate(client):
    assert client.post("/v1/voice-profiles", json=VOICE).status_code == 201
    payload = idea("Retry ownership", "A retry contract should identify its owner.")
    first = draft(client, payload)
    duplicate = draft(client, payload)
    assert next(
        check for check in duplicate["checks"] if check["check_type"] == "ORIGINALITY"
    )["passed"] is True
    approve(client, first)
    submitted = client.post(
        f"/v1/posts/{duplicate['post_id']}/submit-review",
        json={"revision_id": duplicate["revision_id"]},
    )
    assert submitted.status_code == 200
    originality = next(
        check
        for check in submitted.json()["checks"]
        if check["check_type"] == "ORIGINALITY"
    )
    assert originality["severity"] == "BLOCKING"
    assert originality["passed"] is False
    assert originality["details"]["maximum_similarity"] == 1.0
    blocked = client.post(
        f"/v1/posts/{duplicate['post_id']}/reviews",
        json={
            "revision_id": duplicate["revision_id"],
            "action": "APPROVE",
            "claims_confirmed": True,
        },
    )
    assert blocked.status_code == 409
