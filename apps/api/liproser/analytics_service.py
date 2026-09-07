from __future__ import annotations

import csv
from datetime import UTC, datetime
from hashlib import sha256
from io import StringIO
from math import sqrt
from statistics import mean
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import (
    BOOTSTRAP_WORKSPACE_ID,
    ContentIdea,
    Experiment,
    FeatureSnapshot,
    MetricSnapshot,
    Post,
    PostRevision,
    Prediction,
)

FEATURE_VERSION = "post-features@1"
PREDICTION_VERSION = "heuristic-engagement@1"
DOMAIN_PRIOR_RATE = 2.0


def parse_csv_rows(content: bytes) -> tuple[list[dict], list[str]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must use UTF-8 encoding") from exc
    reader = csv.DictReader(StringIO(text))
    required = {"post_revision_id", "observed_at", "window_hours"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise ValueError("CSV requires post_revision_id, observed_at, and window_hours headers")
    rows, errors = [], []
    for position, row in enumerate(reader, start=2):
        if position > 501:
            errors.append("CSV is limited to 500 data rows")
            break
        try:
            rows.append(
                {
                    "post_revision_id": row["post_revision_id"].strip(),
                    "observed_at": datetime.fromisoformat(row["observed_at"].strip().replace("Z", "+00:00")),
                    "window_hours": int(row["window_hours"]),
                    "impressions": _optional_int(row.get("impressions")),
                    "reactions": _optional_int(row.get("reactions")),
                    "comments": _optional_int(row.get("comments")),
                    "reposts": _optional_int(row.get("reposts")),
                    "follower_delta": _optional_int(row.get("follower_delta")),
                    "clicks": _optional_int(row.get("clicks")),
                    "baseline": (row.get("baseline") or "").strip().lower() in {"1", "true", "yes"},
                    "experiment_id": (row.get("experiment_id") or "").strip() or None,
                }
            )
        except (TypeError, ValueError) as exc:
            errors.append(f"Row {position}: {exc}")
    return rows, errors


def engagement_rate(snapshot: MetricSnapshot) -> float | None:
    if not snapshot.impressions:
        return None
    engagements = sum(value or 0 for value in (snapshot.reactions, snapshot.comments, snapshot.reposts, snapshot.clicks))
    return round(engagements / snapshot.impressions * 100, 4)


def snapshot_dedupe_key(revision_id: str, observed_at: datetime, window_hours: int) -> str:
    instant = observed_at.astimezone(UTC).isoformat(timespec="seconds")
    return sha256(f"{revision_id}|{instant}|{window_hours}".encode()).hexdigest()


def validate_snapshot(db: Session, data: dict, source: str) -> tuple[PostRevision, Experiment | None]:
    revision = db.get(PostRevision, data["post_revision_id"])
    if not revision or revision.workspace_id != BOOTSTRAP_WORKSPACE_ID:
        raise ValueError("Post revision not found")
    post = db.get(Post, revision.post_id)
    if not post or post.state != "PUBLISHED":
        raise ValueError("Metrics can only be attached to a published revision")
    if data["observed_at"].tzinfo is None:
        raise ValueError("observed_at must include a timezone")
    published_at = post.published_at
    if published_at:
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)
        if data["observed_at"].astimezone(UTC) < published_at.astimezone(UTC):
            raise ValueError("observed_at cannot be earlier than publication")
    metric_names = ("impressions", "reactions", "comments", "reposts", "follower_delta", "clicks")
    if all(data.get(name) is None for name in metric_names):
        raise ValueError("Provide at least one metric")
    if not 1 <= data["window_hours"] <= 8_760:
        raise ValueError("window_hours must be between 1 and 8760")
    if any((data.get(name) or 0) < 0 for name in ("impressions", "reactions", "comments", "reposts", "clicks")):
        raise ValueError("Post performance metrics cannot be negative")
    experiment = None
    if data.get("experiment_id"):
        experiment = db.get(Experiment, data["experiment_id"])
        if not experiment or experiment.workspace_id != BOOTSTRAP_WORKSPACE_ID:
            raise ValueError("Experiment not found")
    if source not in {"MANUAL", "CSV", "LINKEDIN_OFFICIAL_API"}:
        raise ValueError("Unsupported metric source")
    return revision, experiment


def add_metric_snapshot(db: Session, data: dict, source: str) -> tuple[MetricSnapshot, bool]:
    validate_snapshot(db, data, source)
    key = snapshot_dedupe_key(data["post_revision_id"], data["observed_at"], data["window_hours"])
    existing = db.scalar(
        select(MetricSnapshot).where(
            MetricSnapshot.workspace_id == BOOTSTRAP_WORKSPACE_ID,
            MetricSnapshot.dedupe_key == key,
        )
    )
    if existing:
        return existing, False
    item = MetricSnapshot(id=str(uuid4()), source=source, dedupe_key=key, **data)
    db.add(item)
    db.flush()
    evaluate_predictions(db, item)
    return item, True


def evaluate_predictions(db: Session, snapshot: MetricSnapshot) -> None:
    actual = engagement_rate(snapshot)
    if actual is None:
        return
    predictions = db.scalars(
        select(Prediction).where(
            Prediction.workspace_id == BOOTSTRAP_WORKSPACE_ID,
            Prediction.post_revision_id == snapshot.post_revision_id,
            Prediction.target_window_hours == snapshot.window_hours,
            Prediction.actual_engagement_rate.is_(None),
        )
    ).all()
    for prediction in predictions:
        prediction.actual_engagement_rate = actual
        prediction.absolute_error = round(abs(prediction.expected_engagement_rate - actual), 4)
        prediction.evaluated_at = datetime.now(UTC)


def historical_rates(db: Session, window_hours: int) -> list[float]:
    snapshots = db.scalars(
        select(MetricSnapshot).where(
            MetricSnapshot.workspace_id == BOOTSTRAP_WORKSPACE_ID,
            MetricSnapshot.window_hours == window_hours,
            MetricSnapshot.baseline.is_(False),
        )
    ).all()
    return [rate for item in _latest_by_revision(snapshots) if (rate := engagement_rate(item)) is not None]


def post_features(revision: PostRevision) -> dict:
    text = revision.content.strip()
    words = text.split()
    first_line = revision.hook.strip().splitlines()[0] if revision.hook.strip() else ""
    return {
        "character_count": len(text),
        "word_count": len(words),
        "hook_character_count": len(first_line),
        "hook_is_question": first_line.endswith("?"),
        "cta_present": bool(revision.cta.strip()),
        "cta_is_question": revision.cta.strip().endswith("?"),
        "paragraph_count": len([part for part in text.split("\n\n") if part.strip()]),
    }


def factor_explanations(features: dict) -> tuple[list[dict], str | None, float]:
    score = 0.0
    hook_length = features["hook_character_count"]
    if 25 <= hook_length <= 140:
        hook = {"feature": "HOOK", "impact": "POSITIVE", "explanation": "The opening is concise enough to scan while still carrying a clear idea."}
        score += 0.35
    else:
        hook = {"feature": "HOOK", "impact": "NEGATIVE", "explanation": "The opening is unusually short or long for a quickly scanned first line."}
        score -= 0.25
    characters = features["character_count"]
    if 400 <= characters <= 1_800:
        length = {"feature": "LENGTH", "impact": "POSITIVE", "explanation": "The draft has enough substance without becoming unusually long."}
        score += 0.25
    else:
        length = {"feature": "LENGTH", "impact": "NEGATIVE", "explanation": "The draft length sits outside the current readable heuristic range."}
        score -= 0.2
    if features["cta_is_question"]:
        cta = {"feature": "CTA", "impact": "POSITIVE", "explanation": "The closing question gives readers a specific way to respond."}
        score += 0.25
    elif features["cta_present"]:
        cta = {"feature": "CTA", "impact": "NEUTRAL", "explanation": "A call to action is present, but it does not explicitly invite a response."}
    else:
        cta = {"feature": "CTA", "impact": "NEGATIVE", "explanation": "The draft has no explicit closing prompt for the reader."}
        score -= 0.15
    weakest = next((item for item in (hook, length, cta) if item["impact"] == "NEGATIVE"), None)
    recommendations = {
        "HOOK": "Rewrite the first line to make one specific promise or tension point in 25–140 characters.",
        "LENGTH": "Tighten or expand the draft into the 400–1,800 character heuristic range.",
        "CTA": "End with one concrete question your intended reader can answer from experience.",
    }
    return [hook, length, cta], recommendations.get(weakest["feature"]) if weakest else None, score


def create_prediction(db: Session, revision: PostRevision, target_window_hours: int) -> Prediction:
    features = post_features(revision)
    rates = historical_rates(db, target_window_hours)
    count = len(rates)
    if count < 3:
        basis, center, width = "DOMAIN_PRIOR", DOMAIN_PRIOR_RATE, 1.75
        limitations = ["Fewer than three comparable personal outcomes exist.", "The domain prior is a broad heuristic, not a guarantee or causal estimate."]
    else:
        personal = mean(rates)
        if count < 10:
            weight = min(count / 10, 0.8)
            basis = "BLENDED"
            center = DOMAIN_PRIOR_RATE * (1 - weight) + personal * weight
            width = max(1.0, _standard_deviation(rates) * 1.5)
            limitations = ["The estimate blends a broad prior with limited personal history.", "Performance depends on audience, distribution, and timing beyond draft structure."]
        else:
            basis, center = "PERSONALIZED", personal
            width = max(0.6, _standard_deviation(rates) * 1.25)
            limitations = ["Personal history improves relevance but does not establish causality.", "Unexpected distribution changes can move results outside this interval."]
    factors, recommendation, adjustment = factor_explanations(features)
    expected = round(max(0.05, center + adjustment), 3)
    low, high = round(max(0.0, expected - width), 3), round(expected + width, 3)
    bucket = "LOW" if expected < 1.5 else "HIGH" if expected >= 3.5 else "MEDIUM"
    feature_snapshot = FeatureSnapshot(id=str(uuid4()), post_revision_id=revision.id, feature_version=FEATURE_VERSION, features=features)
    db.add(feature_snapshot)
    db.flush()
    prediction = Prediction(
        id=str(uuid4()),
        post_revision_id=revision.id,
        feature_snapshot_id=feature_snapshot.id,
        target_window_hours=target_window_hours,
        basis=basis,
        bucket=bucket,
        expected_engagement_rate=expected,
        interval_low=low,
        interval_high=high,
        factors=factors,
        recommended_change=recommendation,
        limitations=limitations,
        model_version=PREDICTION_VERSION,
    )
    db.add(prediction)
    return prediction


def analytics_summary(db: Session, window_hours: int) -> dict:
    all_snapshots = db.scalars(
        select(MetricSnapshot).where(
            MetricSnapshot.workspace_id == BOOTSTRAP_WORKSPACE_ID,
            MetricSnapshot.window_hours == window_hours,
        )
    ).all()
    snapshots = _latest_by_revision(all_snapshots)
    baseline_rates = [rate for item in snapshots if item.baseline and (rate := engagement_rate(item)) is not None]
    current_rates = [rate for item in snapshots if not item.baseline and (rate := engagement_rate(item)) is not None]
    baseline = mean(baseline_rates) if baseline_rates else None
    current = mean(current_rates) if current_rates else None
    lift = ((current - baseline) / baseline * 100) if baseline and current is not None else None
    pillars: dict[str, list[float]] = {}
    for snapshot in snapshots:
        rate = engagement_rate(snapshot)
        revision = db.get(PostRevision, snapshot.post_revision_id)
        post = db.get(Post, revision.post_id) if revision else None
        idea = db.get(ContentIdea, post.content_idea_id) if post else None
        if rate is not None and idea:
            pillars.setdefault(idea.pillar, []).append(rate)
    predictions = db.scalars(
        select(Prediction).where(
            Prediction.workspace_id == BOOTSTRAP_WORKSPACE_ID,
            Prediction.target_window_hours == window_hours,
            Prediction.absolute_error.is_not(None),
        )
    ).all()
    errors = [item.absolute_error for item in predictions if item.absolute_error is not None]
    return {
        "snapshot_count": len(snapshots),
        "comparable_post_count": len(baseline_rates) + len(current_rates),
        "baseline_engagement_rate": _rounded(baseline),
        "current_engagement_rate": _rounded(current),
        "lift_percent": _rounded(lift),
        "best_pillars": sorted(({"pillar": key, "engagement_rate": round(mean(values), 3), "post_count": len(values)} for key, values in pillars.items()), key=lambda item: item["engagement_rate"], reverse=True),
        "calibration_count": len(errors),
        "mean_absolute_error": _rounded(mean(errors) if errors else None),
    }


def _standard_deviation(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    average = mean(values)
    return sqrt(sum((value - average) ** 2 for value in values) / len(values))


def _rounded(value: float | None) -> float | None:
    return round(value, 3) if value is not None else None


def _latest_by_revision(snapshots: list[MetricSnapshot]) -> list[MetricSnapshot]:
    latest: dict[str, MetricSnapshot] = {}
    for snapshot in snapshots:
        current = latest.get(snapshot.post_revision_id)
        current_time = current.observed_at if current else None
        if current_time is not None and current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        snapshot_time = snapshot.observed_at
        if snapshot_time.tzinfo is None:
            snapshot_time = snapshot_time.replace(tzinfo=UTC)
        if current is None or snapshot_time > current_time:
            latest[snapshot.post_revision_id] = snapshot
    return list(latest.values())


def _optional_int(value: str | None) -> int | None:
    return int(value) if value is not None and value.strip() else None
