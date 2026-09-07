from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings

BOOTSTRAP_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


EMBEDDING_DIMENSIONS = 64


class EmbeddingVector(TypeDecorator):
    """Use pgvector in PostgreSQL and JSON in the local SQLite test adapter."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(VECTOR(EMBEDDING_DIMENSIONS))
        return dialect.type_descriptor(JSON())


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProfileImport(Base):
    __tablename__ = "profile_imports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), default="PENDING_CONFIRMATION")
    sections: Mapped[dict[str, Any]] = mapped_column(JSON)
    confidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProviderConfiguration(Base):
    __tablename__ = "provider_configurations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    provider: Mapped[str] = mapped_column(String(24))
    model: Mapped[str] = mapped_column(String(200))
    ready: Mapped[bool] = mapped_column(default=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    import_id: Mapped[str] = mapped_column(ForeignKey("profile_imports.id"), unique=True)
    sections: Mapped[dict[str, Any]] = mapped_column(JSON)
    target_role: Mapped[str] = mapped_column(Text, default="")
    domain: Mapped[str] = mapped_column(Text, default="")
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProfileAnalysis(Base):
    __tablename__ = "profile_analyses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id"))
    rubric_version: Mapped[str] = mapped_column(String(32), default="profile-rubric@1")
    total_score: Mapped[float] = mapped_column(Float)
    criteria: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProfileSuggestion(Base):
    __tablename__ = "profile_suggestions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    analysis_id: Mapped[str] = mapped_column(ForeignKey("profile_analyses.id"))
    section: Mapped[str] = mapped_column(String(32))
    before: Mapped[str] = mapped_column(Text)
    after: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    preserved_facts: Mapped[list[str]] = mapped_column(JSON)
    proposed_claims: Mapped[list[str]] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decided_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VoiceProfile(Base):
    __tablename__ = "voice_profiles"
    __table_args__ = (UniqueConstraint("workspace_id", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    version: Mapped[int] = mapped_column(Integer)
    domain: Mapped[str] = mapped_column(String(200))
    target_audience: Mapped[str] = mapped_column(Text)
    content_pillars: Mapped[list[str]] = mapped_column(JSON)
    tone_preferences: Mapped[list[str]] = mapped_column(JSON)
    prohibited_phrases: Mapped[list[str]] = mapped_column(JSON)
    samples_are_user_owned: Mapped[bool] = mapped_column(Boolean, default=True)
    taxonomy_version: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VoiceSample(Base):
    __tablename__ = "voice_samples"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    voice_profile_id: Mapped[str] = mapped_column(ForeignKey("voice_profiles.id"))
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(24), default="USER_OWNED")


class TaxonomySnapshot(Base):
    __tablename__ = "taxonomy_snapshots"
    __table_args__ = (UniqueConstraint("workspace_id", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    version: Mapped[str] = mapped_column(String(40))
    domain_tag: Mapped[str] = mapped_column(String(200))
    pillar_tags: Mapped[list[str]] = mapped_column(JSON)
    audience_tags: Mapped[list[str]] = mapped_column(JSON)
    topic_tags: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ContentIdea(Base):
    __tablename__ = "content_ideas"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    voice_profile_id: Mapped[str] = mapped_column(ForeignKey("voice_profiles.id"))
    taxonomy_version: Mapped[str] = mapped_column(String(40))
    pillar: Mapped[str] = mapped_column(String(100))
    topic: Mapped[str] = mapped_column(String(300))
    angle: Mapped[str] = mapped_column(Text)
    audience_intent: Mapped[str] = mapped_column(Text)
    format: Mapped[str] = mapped_column(String(24), default="TEXT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourceReference(Base):
    __tablename__ = "source_references"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    content_idea_id: Mapped[str] = mapped_column(ForeignKey("content_ideas.id"))
    statement: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    freshness_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), default="USER_CONFIRMED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    content_idea_id: Mapped[str] = mapped_column(ForeignKey("content_ideas.id"), unique=True)
    state: Mapped[str] = mapped_column(String(32), default="DRAFT")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PostRevision(Base):
    __tablename__ = "post_revisions"
    __table_args__ = (UniqueConstraint("post_id", "revision_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"))
    revision_number: Mapped[int] = mapped_column(Integer, default=1)
    hook: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    cta: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    generation_provider: Mapped[str] = mapped_column(String(32))
    generation_model: Mapped[str] = mapped_column(String(200))
    generation_mode: Mapped[str] = mapped_column(String(32))
    generation_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(40), default="primary-draft@1")
    taxonomy_version: Mapped[str] = mapped_column(String(40))
    retrieved_revision_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ClaimAssessment(Base):
    __tablename__ = "claim_assessments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    post_revision_id: Mapped[str] = mapped_column(ForeignKey("post_revisions.id"))
    claim_text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(32))
    source_reference_ids: Mapped[list[str]] = mapped_column(JSON)


class RevisionCheck(Base):
    __tablename__ = "revision_checks"
    __table_args__ = (UniqueConstraint("post_revision_id", "check_type"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    post_revision_id: Mapped[str] = mapped_column(ForeignKey("post_revisions.id"))
    check_type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(20))
    passed: Mapped[bool] = mapped_column(Boolean)
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("revision_id", "action"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"))
    revision_id: Mapped[str] = mapped_column(ForeignKey("post_revisions.id"))
    action: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    claims_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    actor: Mapped[str] = mapped_column(String(80), default="LOCAL_OWNER")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EditDelta(Base):
    __tablename__ = "edit_deltas"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"))
    from_revision_id: Mapped[str] = mapped_column(ForeignKey("post_revisions.id"))
    to_revision_id: Mapped[str] = mapped_column(
        ForeignKey("post_revisions.id"), unique=True
    )
    operations: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RevisionMemoryEligibility(Base):
    __tablename__ = "revision_memory_eligibility"
    revision_id: Mapped[str] = mapped_column(
        ForeignKey("post_revisions.id"), primary_key=True
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID, index=True
    )
    eligible: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    reason: Mapped[str] = mapped_column(String(48))
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RevisionEmbedding(Base):
    __tablename__ = "revision_embeddings"
    revision_id: Mapped[str] = mapped_column(
        ForeignKey("post_revisions.id"), primary_key=True
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID, index=True
    )
    embedding_version: Mapped[str] = mapped_column(String(40))
    dimensions: Mapped[int] = mapped_column(Integer, default=EMBEDDING_DIMENSIONS)
    content_hash: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list[float]] = mapped_column(EmbeddingVector())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RevisionRetrieval(Base):
    __tablename__ = "revision_retrievals"
    __table_args__ = (UniqueConstraint("generated_revision_id", "reference_revision_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID, index=True
    )
    generated_revision_id: Mapped[str] = mapped_column(ForeignKey("post_revisions.id"))
    reference_revision_id: Mapped[str] = mapped_column(ForeignKey("post_revisions.id"))
    similarity_score: Mapped[float] = mapped_column(Float)
    embedding_version: Mapped[str] = mapped_column(String(40))
    taxonomy_version: Mapped[str] = mapped_column(String(40))
    rank: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ContentCalendar(Base):
    __tablename__ = "content_calendars"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID, index=True)
    voice_profile_id: Mapped[str] = mapped_column(ForeignKey("voice_profiles.id"))
    start_date: Mapped[str] = mapped_column(String(10))
    weeks: Mapped[int] = mapped_column(Integer)
    cadence_per_week: Mapped[int] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(80))
    quiet_days: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CalendarSlot(Base):
    __tablename__ = "calendar_slots"
    __table_args__ = (UniqueConstraint("calendar_id", "position"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID, index=True)
    calendar_id: Mapped[str] = mapped_column(ForeignKey("content_calendars.id"))
    position: Mapped[int] = mapped_column(Integer)
    pillar: Mapped[str] = mapped_column(String(100))
    intended_local_at: Mapped[str] = mapped_column(String(32))
    resolved_utc_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="PLANNED")


class PostSchedule(Base):
    __tablename__ = "post_schedules"
    __table_args__ = (UniqueConstraint("workspace_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID, index=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"))
    revision_id: Mapped[str] = mapped_column(ForeignKey("post_revisions.id"))
    calendar_slot_id: Mapped[str | None] = mapped_column(ForeignKey("calendar_slots.id"), nullable=True)
    timezone: Mapped[str] = mapped_column(String(80))
    intended_local_at: Mapped[str] = mapped_column(String(32))
    resolved_utc_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    idempotency_key: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PublishAction(Base):
    __tablename__ = "publish_actions"
    __table_args__ = (UniqueConstraint("workspace_id", "idempotency_key"), UniqueConstraint("schedule_id"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID, index=True)
    schedule_id: Mapped[str] = mapped_column(ForeignKey("post_schedules.id"))
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"))
    revision_id: Mapped[str] = mapped_column(ForeignKey("post_revisions.id"))
    method: Mapped[str] = mapped_column(String(32), default="COPY_REMINDER")
    state: Mapped[str] = mapped_column(String(32), default="ACTION_REQUIRED")
    formatted_content: Mapped[str] = mapped_column(Text)
    published_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (UniqueConstraint("workspace_id", "dedupe_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID, index=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    aggregate_id: Mapped[str] = mapped_column(String(36))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    dedupe_key: Mapped[str] = mapped_column(String(140))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class JobRun(Base):
    __tablename__ = "job_runs"
    __table_args__ = (UniqueConstraint("workspace_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID, index=True)
    job_type: Mapped[str] = mapped_column(String(60))
    aggregate_id: Mapped[str] = mapped_column(String(36))
    idempotency_key: Mapped[str] = mapped_column(String(140))
    status: Mapped[str] = mapped_column(String(24))
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DeadLetter(Base):
    __tablename__ = "dead_letters"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID, index=True)
    job_type: Mapped[str] = mapped_column(String(60))
    aggregate_id: Mapped[str] = mapped_column(String(36))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    error: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedbackSignal(Base):
    __tablename__ = "feedback_signals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID, index=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"))
    revision_id: Mapped[str] = mapped_column(ForeignKey("post_revisions.id"))
    category: Mapped[str] = mapped_column(String(40), index=True)
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PreferenceRule(Base):
    __tablename__ = "preference_rules"
    __table_args__ = (UniqueConstraint("workspace_id", "category"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID, index=True)
    category: Mapped[str] = mapped_column(String(40))
    instruction: Mapped[str] = mapped_column(Text)
    evidence_count: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID, index=True)
    name: Mapped[str] = mapped_column(String(120))
    hypothesis: Mapped[str] = mapped_column(Text)
    variable: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    __table_args__ = (UniqueConstraint("workspace_id", "dedupe_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID, index=True)
    post_revision_id: Mapped[str] = mapped_column(ForeignKey("post_revisions.id"), index=True)
    experiment_id: Mapped[str | None] = mapped_column(ForeignKey("experiments.id"), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_hours: Mapped[int] = mapped_column(Integer)
    impressions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reactions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reposts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    follower_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clicks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(32))
    dedupe_key: Mapped[str] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeatureSnapshot(Base):
    __tablename__ = "feature_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID, index=True)
    post_revision_id: Mapped[str] = mapped_column(ForeignKey("post_revisions.id"), index=True)
    feature_version: Mapped[str] = mapped_column(String(40))
    features: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID, index=True)
    post_revision_id: Mapped[str] = mapped_column(ForeignKey("post_revisions.id"), index=True)
    feature_snapshot_id: Mapped[str] = mapped_column(ForeignKey("feature_snapshots.id"))
    target_window_hours: Mapped[int] = mapped_column(Integer)
    basis: Mapped[str] = mapped_column(String(24))
    bucket: Mapped[str] = mapped_column(String(16))
    expected_engagement_rate: Mapped[float] = mapped_column(Float)
    interval_low: Mapped[float] = mapped_column(Float)
    interval_high: Mapped[float] = mapped_column(Float)
    factors: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    recommended_change: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitations: Mapped[list[str]] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String(40))
    actual_engagement_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    absolute_error: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AiBudgetPeriod(Base):
    __tablename__ = "ai_budget_periods"
    period: Mapped[str] = mapped_column(String(7), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    limit_usd: Mapped[float] = mapped_column(Float)
    actual_usd: Mapped[float] = mapped_column(Float, default=0)
    reserved_usd: Mapped[float] = mapped_column(Float, default=0)


class AiCostReservation(Base):
    __tablename__ = "ai_cost_reservations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    period: Mapped[str] = mapped_column(ForeignKey("ai_budget_periods.period"))
    provider: Mapped[str] = mapped_column(String(24))
    estimated_usd: Mapped[float] = mapped_column(Float)
    actual_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="RESERVED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def make_engine(database_url: str | None = None):
    url = database_url or get_settings().database_url
    if url == "sqlite:///:memory:":
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(url)


engine = make_engine()
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def create_schema() -> None:
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        if session.get(Workspace, BOOTSTRAP_WORKSPACE_ID) is None:
            session.add(
                Workspace(
                    id=BOOTSTRAP_WORKSPACE_ID,
                    name=get_settings().bootstrap_workspace_name,
                )
            )
            session.commit()
