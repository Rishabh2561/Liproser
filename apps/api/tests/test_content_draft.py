from liproser.database import ProviderConfiguration, engine
from liproser.runtime_secrets import set_session_secret
from sqlalchemy.orm import Session

VOICE = {
    "domain": "Software Engineering",
    "target_audience": "backend engineers and engineering leaders",
    "content_pillars": ["API Design", "Career Growth"],
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
    "evidence": [
        {
            "statement": "A 2024 internal review found 25% fewer incidents after retry ownership was documented.",
            "source_url": "https://example.com/retry-review",
            "freshness_date": "2024-12-31",
        }
    ],
    "evidence_confirmed": True,
}


def configure_voice(client):
    response = client.post("/v1/voice-profiles", json=VOICE)
    assert response.status_code == 201


def test_content_idea_requires_voice_and_controlled_pillar(client):
    assert client.post("/v1/content-ideas", json=IDEA).status_code == 409
    configure_voice(client)
    invalid = client.post("/v1/content-ideas", json={**IDEA, "pillar": "Unapproved Pillar"})
    assert invalid.status_code == 422
    created = client.post("/v1/content-ideas", json=IDEA)
    assert created.status_code == 201
    body = created.json()
    assert body["taxonomy_version"] == "taxonomy@1"
    assert body["pillar"] == "API Design"
    assert body["evidence"][0]["source_type"] == "USER_CONFIRMED"
    assert client.get(f"/v1/content-ideas/{body['id']}").json() == body


def test_one_provider_primary_draft_records_claim_provenance(client, monkeypatch):
    configure_voice(client)
    idea = client.post("/v1/content-ideas", json=IDEA).json()
    set_session_secret("openai", "synthetic-provider-value-for-tests")
    with Session(engine) as db:
        db.add(
            ProviderConfiguration(
                id=1, provider="openai", model="gpt-5.6-luna", ready=True
            )
        )
        db.commit()

    evidence_claim = IDEA["evidence"][0]["statement"]

    def generated(*_args, **_kwargs):
        return (
            {
                "hook": "Reliable APIs need explicit failure contracts.",
                "body": evidence_claim,
                "cta": "Which retry contract does your team make explicit?",
                "claims": [
                    {
                        "text": "Reliable APIs need explicit failure contracts.",
                        "kind": "OPINION",
                        "evidence_indices": [],
                    },
                    {
                        "text": evidence_claim,
                        "kind": "SUPPORTED",
                        "evidence_indices": [1],
                    },
                ],
            },
            {"input_tokens": 200, "output_tokens": 100},
        )

    monkeypatch.setattr("liproser.api.generate_primary_draft", generated)
    response = client.post(f"/v1/content-ideas/{idea['id']}/primary-draft")
    assert response.status_code == 201
    draft = response.json()
    assert draft["state"] == "DRAFT"
    assert draft["revision_number"] == 1
    assert draft["generation_mode"] == "provider"
    assert draft["retrieved_revision_ids"] == []
    supported = next(claim for claim in draft["claims"] if claim["kind"] == "SUPPORTED")
    assert supported["source_reference_ids"] == [idea["evidence"][0]["id"]]
    assert client.get(f"/v1/posts/{draft['post_id']}").json() == draft
    assert client.post(f"/v1/content-ideas/{idea['id']}/primary-draft").status_code == 409


def test_untraceable_provider_number_falls_back_safely(client, monkeypatch):
    configure_voice(client)
    idea = client.post("/v1/content-ideas", json=IDEA).json()
    set_session_secret("openai", "synthetic-provider-value-for-tests")
    with Session(engine) as db:
        db.add(
            ProviderConfiguration(
                id=1, provider="openai", model="gpt-5.6-luna", ready=True
            )
        )
        db.commit()

    monkeypatch.setattr(
        "liproser.api.generate_primary_draft",
        lambda *_args, **_kwargs: (
            {
                "hook": "Teams improve delivery by 90% with this retry pattern.",
                "body": IDEA["angle"],
                "cta": "What has worked for you?",
                "claims": [
                    {
                        "text": "Teams improve delivery by 90% with this retry pattern.",
                        "kind": "OPINION",
                        "evidence_indices": [],
                    }
                ],
            },
            {"input_tokens": 100, "output_tokens": 50},
        ),
    )
    draft = client.post(f"/v1/content-ideas/{idea['id']}/primary-draft").json()
    assert draft["generation_mode"] == "deterministic_fallback"
    assert "90%" not in draft["content"]
    assert "failed evidence" in draft["generation_warning"]


def test_supported_claim_must_match_confirmed_evidence(client, monkeypatch):
    configure_voice(client)
    idea = client.post("/v1/content-ideas", json=IDEA).json()
    set_session_secret("openai", "synthetic-provider-value-for-tests")
    with Session(engine) as db:
        db.add(
            ProviderConfiguration(
                id=1, provider="openai", model="gpt-5.6-luna", ready=True
            )
        )
        db.commit()

    monkeypatch.setattr(
        "liproser.api.generate_primary_draft",
        lambda *_args, **_kwargs: (
            {
                "hook": "Reliable APIs need explicit failure contracts.",
                "body": "A 2024 review found 25% faster deployments.",
                "cta": "What has worked for you?",
                "claims": [
                    {
                        "text": "A 2024 review found 25% faster deployments.",
                        "kind": "SUPPORTED",
                        "evidence_indices": [1],
                    }
                ],
            },
            {"input_tokens": 100, "output_tokens": 50},
        ),
    )
    draft = client.post(f"/v1/content-ideas/{idea['id']}/primary-draft").json()
    assert draft["generation_mode"] == "deterministic_fallback"
    assert "faster deployments" not in draft["content"]
    assert "failed evidence" in draft["generation_warning"]
