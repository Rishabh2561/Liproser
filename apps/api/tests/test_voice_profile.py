from liproser.database import VoiceProfile, VoiceSample, engine
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def voice_payload(**overrides):
    payload = {
        "domain": "Software Engineering",
        "target_audience": "backend engineers and engineering leaders",
        "content_pillars": ["API Design", "Career Growth", "API Design"],
        "tone_preferences": ["practical", "clear"],
        "prohibited_phrases": ["game changer"],
        "samples": [
            "I learned that reliable APIs begin with explicit failure contracts.",
            "A small test suite can create confidence when it protects the right boundaries.",
            "Engineering leadership works best when trade-offs are visible to the team.",
        ],
        "samples_are_user_owned": True,
    }
    payload.update(overrides)
    return payload


def test_voice_onboarding_versions_private_samples_and_builds_taxonomy(client):
    assert client.get("/v1/voice-profiles/current").status_code == 404
    created = client.post("/v1/voice-profiles", json=voice_payload())
    assert created.status_code == 201
    body = created.json()
    assert body["version"] == 1
    assert body["content_pillars"] == ["API Design", "Career Growth"]
    assert len(body["samples"]) == 3
    assert {sample["source_type"] for sample in body["samples"]} == {"USER_OWNED"}

    taxonomy = client.get("/v1/taxonomy/current").json()
    assert taxonomy["version"] == "taxonomy@1"
    assert taxonomy["domain_tag"] == "software-engineering"
    assert taxonomy["pillar_tags"] == ["api-design", "career-growth"]
    assert taxonomy["topic_tags"] == []
    assert all("reliable APIs" not in value for value in taxonomy.values() if isinstance(value, str))

    revised = client.post(
        "/v1/voice-profiles", json=voice_payload(domain="Developer Productivity")
    )
    assert revised.status_code == 201
    assert revised.json()["version"] == 2
    assert client.get("/v1/voice-profiles/current").json()["domain"] == "Developer Productivity"
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(VoiceProfile)) == 2
        assert db.scalar(select(func.count()).select_from(VoiceSample)) == 6


def test_voice_onboarding_requires_three_owned_distinct_substantive_samples(client):
    too_few = client.post(
        "/v1/voice-profiles", json=voice_payload(samples=voice_payload()["samples"][:2])
    )
    assert too_few.status_code == 422
    unowned = client.post(
        "/v1/voice-profiles", json=voice_payload(samples_are_user_owned=False)
    )
    assert unowned.status_code == 422
    duplicate = voice_payload()["samples"][0]
    repeated = client.post(
        "/v1/voice-profiles", json=voice_payload(samples=[duplicate, duplicate, duplicate])
    )
    assert repeated.status_code == 422
