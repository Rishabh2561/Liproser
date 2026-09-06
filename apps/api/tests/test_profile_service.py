from liproser.profile_service import (
    provider_suggestion_is_safe,
    safe_suggestion,
    score_sections,
)
from liproser.schemas import ProfileSections


def test_empty_sections_do_not_invent_claims():
    sections = ProfileSections()
    score, criteria = score_sections(sections)
    assert score == 0
    assert all(item["score"] == 0 for item in criteria.values())
    after, _, preserved, proposed, confidence = safe_suggestion("experience", "")
    assert "[Role]" in after
    assert "[Verified result or scale]" in after
    assert preserved == []
    assert proposed == []
    assert confidence < 0.5


def test_headline_rewrite_preserves_every_term():
    before = "Backend Engineer | Python | FastAPI"
    after, _, preserved, proposed, _ = safe_suggestion("headline", before)
    for term in ["Backend Engineer", "Python", "FastAPI"]:
        assert term in after
    assert preserved == [before]
    assert proposed == []


def test_provider_guard_rejects_new_or_removed_protected_facts():
    before = "Implemented an API at ExampleCo in 2024 using FastAPI."
    assert provider_suggestion_is_safe(
        before, "At ExampleCo in 2024, implemented an API using FastAPI.", []
    )
    assert not provider_suggestion_is_safe(
        before, "At MegaCorp in 2024, implemented an API using FastAPI.", []
    )
    assert not provider_suggestion_is_safe(
        before, "At ExampleCo, implemented an API using FastAPI.", []
    )
    assert not provider_suggestion_is_safe(before, before, ["Unverified achievement"])
