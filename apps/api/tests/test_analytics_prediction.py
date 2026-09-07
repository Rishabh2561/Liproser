import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from liproser.analytics_service import factor_explanations

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


def import_post(client, topic="Retry ownership", pillar="API Design"):
    response = client.post(
        "/v1/historical-posts",
        json={
            "pillar": pillar,
            "topic": topic,
            "hook": f"{topic} needs an explicit owner.",
            "body": "A reliable workflow names the failure boundary, retry policy, and operator before release. " * 5,
            "cta": "Which boundary does your team document first?",
            "published_at": (datetime.now(UTC) - timedelta(days=30)).isoformat(),
            "content_is_user_owned": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def metric_payload(revision_id, *, observed_at=None, baseline=False, window=168):
    return {
        "post_revision_id": revision_id,
        "observed_at": (observed_at or datetime.now(UTC)).isoformat(),
        "window_hours": window,
        "impressions": 1_000,
        "reactions": 20,
        "comments": 5,
        "reposts": 2,
        "follower_delta": 3,
        "clicks": 3,
        "baseline": baseline,
    }


def test_historical_post_requires_owned_content_and_controlled_taxonomy(client):
    client.post("/v1/voice-profiles", json=VOICE)
    payload = {
        "pillar": "Unknown pillar",
        "topic": "A historical post",
        "hook": "A real hook",
        "body": "A real historical body",
        "cta": "What did you learn?",
        "published_at": datetime.now(UTC).isoformat(),
        "content_is_user_owned": True,
    }
    assert client.post("/v1/historical-posts", json=payload).status_code == 422
    payload["pillar"] = "API Design"
    payload["content_is_user_owned"] = False
    assert client.post("/v1/historical-posts", json=payload).status_code == 422
    post = import_post(client)
    memory = client.get("/v1/memory/revisions").json()
    assert memory[0]["revision_id"] == post["revision_id"]


def test_manual_metrics_validate_and_deduplicate(client):
    client.post("/v1/voice-profiles", json=VOICE)
    post = import_post(client)
    assert client.post("/v1/metric-snapshots", json={
        "post_revision_id": post["revision_id"],
        "observed_at": datetime.now(UTC).isoformat(),
        "window_hours": 168,
    }).status_code == 422
    experiment = client.post(
        "/v1/experiments",
        json={"name": "Question CTA", "hypothesis": "A specific question increases meaningful replies.", "variable": "CTA"},
    ).json()
    payload = metric_payload(post["revision_id"], baseline=True)
    payload["experiment_id"] = experiment["id"]
    first = client.post("/v1/metric-snapshots", json=payload)
    duplicate = client.post("/v1/metric-snapshots", json=payload)
    assert first.status_code == duplicate.status_code == 201
    assert first.json()["id"] == duplicate.json()["id"]
    assert first.json()["engagement_rate"] == 3.0
    assert len(client.get("/v1/metric-snapshots").json()) == 1


def test_csv_import_is_bounded_row_isolated_and_idempotent(client):
    client.post("/v1/voice-profiles", json=VOICE)
    post = import_post(client)
    observed = datetime.now(UTC).isoformat()
    csv_text = (
        "post_revision_id,observed_at,window_hours,impressions,reactions,comments,reposts,follower_delta,clicks,baseline\n"
        f"{post['revision_id']},{observed},168,1000,20,5,2,3,3,true\n"
        f"{post['revision_id']},not-a-date,168,1000,20,5,2,3,3,false\n"
    )
    first = client.post("/v1/metric-snapshots/import-csv", files={"file": ("metrics.csv", csv_text, "text/csv")})
    assert first.status_code == 200
    assert first.json()["created"] == 1
    assert len(first.json()["errors"]) == 1
    second = client.post("/v1/metric-snapshots/import-csv", files={"file": ("metrics.csv", csv_text, "text/csv")})
    assert second.json()["duplicates"] == 1


def test_prediction_explains_cold_start_and_reconciles_actual(client):
    client.post("/v1/voice-profiles", json=VOICE)
    post = import_post(client)
    prediction = client.post(
        "/v1/predictions", json={"post_revision_id": post["revision_id"], "target_window_hours": 168}
    )
    assert prediction.status_code == 201
    body = prediction.json()
    assert body["basis"] == "DOMAIN_PRIOR"
    assert len(body["factors"]) == 3
    assert body["interval"][0] <= body["expected_engagement_rate"] <= body["interval"][1]
    assert any("not a guarantee" in limitation for limitation in body["limitations"])
    client.post("/v1/metric-snapshots", json=metric_payload(post["revision_id"]))
    evaluated = client.get("/v1/predictions").json()[0]
    assert evaluated["actual_engagement_rate"] == 3.0
    assert evaluated["absolute_error"] is not None
    summary = client.get("/v1/analytics/summary?window_hours=168").json()
    assert summary["calibration_count"] == 1


def test_prediction_basis_moves_from_blended_to_personalized(client):
    client.post("/v1/voice-profiles", json=VOICE)
    post = None
    for index in range(3):
        post = import_post(client, f"Comparable post {index + 1}")
        payload = metric_payload(post["revision_id"], observed_at=datetime.now(UTC) - timedelta(days=index + 1))
        assert client.post("/v1/metric-snapshots", json=payload).status_code == 201
    blended = client.post("/v1/predictions", json={"post_revision_id": post["revision_id"]}).json()
    assert blended["basis"] == "BLENDED"
    for index in range(3, 10):
        post = import_post(client, f"Comparable post {index + 1}")
        payload = metric_payload(post["revision_id"], observed_at=datetime.now(UTC) - timedelta(days=index + 1))
        client.post("/v1/metric-snapshots", json=payload)
    personalized = client.post("/v1/predictions", json={"post_revision_id": post["revision_id"]}).json()
    assert personalized["basis"] == "PERSONALIZED"


def test_summary_compares_only_matching_windows(client):
    client.post("/v1/voice-profiles", json=VOICE)
    baseline_post = import_post(client, "Baseline post")
    current_post = import_post(client, "Current post", "Reliability")
    client.post("/v1/metric-snapshots", json=metric_payload(baseline_post["revision_id"], baseline=True, window=24))
    client.post("/v1/metric-snapshots", json=metric_payload(current_post["revision_id"], baseline=False, window=168))
    summary = client.get("/v1/analytics/summary?window_hours=168").json()
    assert summary["baseline_engagement_rate"] is None
    assert summary["current_engagement_rate"] == 3.0
    assert summary["lift_percent"] is None
    assert summary["best_pillars"][0]["pillar"] == "Reliability"


def test_controlled_prediction_fixtures_preserve_factor_explanations():
    fixture = Path("evals/analytics_prediction_cases.jsonl")
    for line in fixture.read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        factors, recommendation, _score = factor_explanations(case["features"])
        assert [item["impact"] for item in factors] == case["expected_impacts"]
        assert bool(recommendation) is case["expects_recommendation"]
