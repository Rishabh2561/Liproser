from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, SecretStr, field_validator


class ProfileSections(BaseModel):
    headline: str = ""
    about: str = ""
    experience: str = ""
    skills: str = ""
    featured: str = ""


class ManualImportRequest(BaseModel):
    kind: Literal["MANUAL"] = "MANUAL"
    sections: ProfileSections


class ImportResponse(BaseModel):
    id: str
    kind: str
    status: str
    sections: ProfileSections
    confidence: dict[str, float]
    source_retained: bool
    source_name: str | None = None


class ConfirmImportRequest(BaseModel):
    sections: ProfileSections
    target_role: str = ""
    domain: str = ""


class DecisionRequest(BaseModel):
    action: Literal["ACCEPT", "EDIT_AND_ACCEPT", "REJECT"]
    edited_text: str | None = None
    reason: str | None = None


class SuggestionOutput(BaseModel):
    id: str
    section: str
    before: str
    after: str
    rationale: str
    preserved_facts: list[str]
    proposed_claims: list[str]
    confidence: float
    decision: str | None = None


class GeneratedSuggestion(BaseModel):
    section: Literal["headline", "about", "experience", "skills", "featured"]
    after: str = Field(min_length=1, max_length=10_000)
    rationale: str = Field(min_length=1, max_length=2_000)
    preserved_facts: list[str] = Field(max_length=100)
    proposed_claims: list[str] = Field(max_length=100)
    confidence: float = Field(ge=0, le=1)


class AnalysisOutput(BaseModel):
    id: str
    profile_id: str
    rubric_version: str
    total_score: float
    criteria: dict[str, Any]
    suggestions: list[SuggestionOutput]
    generation_provider: str = "deterministic"
    generation_model: str = "profile-safe@1"
    generation_mode: Literal["provider", "deterministic_fallback"] = "deterministic_fallback"
    generation_warning: str | None = None


class ProviderCheckRequest(BaseModel):
    provider: Literal["ollama", "openai", "anthropic", "fake"]
    model: str = Field(min_length=1, max_length=200)


class ProviderCheckResponse(BaseModel):
    ready: bool
    provider: str
    model: str
    detail: str


class ProviderSecretRequest(BaseModel):
    provider: Literal["openai", "anthropic"]
    api_key: SecretStr = Field(min_length=10, max_length=500)


class VoiceProfileCreate(BaseModel):
    domain: str = Field(min_length=2, max_length=200)
    target_audience: str = Field(min_length=5, max_length=1_000)
    content_pillars: list[str] = Field(min_length=1, max_length=8)
    tone_preferences: list[str] = Field(min_length=1, max_length=8)
    prohibited_phrases: list[str] = Field(default_factory=list, max_length=20)
    samples: list[str] = Field(min_length=3, max_length=5)
    samples_are_user_owned: Literal[True]

    @field_validator("domain", "target_audience")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("content_pillars", "tone_preferences", "prohibited_phrases")
    @classmethod
    def normalize_short_lists(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = value.strip()
            if not item or len(item) > 100:
                raise ValueError("Entries must contain 1 to 100 characters")
            key = item.casefold()
            if key not in seen:
                seen.add(key)
                cleaned.append(item)
        return cleaned

    @field_validator("samples")
    @classmethod
    def validate_samples(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(len(value) < 20 or len(value) > 10_000 for value in cleaned):
            raise ValueError("Each sample must contain 20 to 10,000 characters")
        if len({value.casefold() for value in cleaned}) != len(cleaned):
            raise ValueError("Voice samples must be distinct")
        return cleaned


class VoiceSampleOutput(BaseModel):
    id: str
    position: int
    text: str
    source_type: Literal["USER_OWNED"]


class VoiceProfileOutput(BaseModel):
    id: str
    version: int
    domain: str
    target_audience: str
    content_pillars: list[str]
    tone_preferences: list[str]
    prohibited_phrases: list[str]
    samples_are_user_owned: bool
    taxonomy_version: str
    samples: list[VoiceSampleOutput]
    created_at: datetime


class TaxonomyOutput(BaseModel):
    version: str
    domain_tag: str
    pillar_tags: list[str]
    audience_tags: list[str]
    topic_tags: list[str]
    created_at: datetime


class EvidenceInput(BaseModel):
    statement: str = Field(min_length=10, max_length=2_000)
    source_url: str | None = Field(default=None, max_length=2_000)
    freshness_date: date | None = None

    @field_validator("statement")
    @classmethod
    def strip_statement(cls, value: str) -> str:
        return value.strip()

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        cleaned = value.strip()
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Source URL must use http or https")
        return cleaned


class ContentIdeaCreate(BaseModel):
    pillar: str = Field(min_length=2, max_length=100)
    topic: str = Field(min_length=5, max_length=300)
    angle: str = Field(min_length=10, max_length=2_000)
    audience_intent: str = Field(min_length=5, max_length=1_000)
    format: Literal["TEXT"] = "TEXT"
    evidence: list[EvidenceInput] = Field(default_factory=list, max_length=5)
    evidence_confirmed: Literal[True]

    @field_validator("pillar", "topic", "angle", "audience_intent")
    @classmethod
    def strip_idea_text(cls, value: str) -> str:
        return value.strip()


class SourceReferenceOutput(BaseModel):
    id: str
    statement: str
    source_url: str | None
    freshness_date: date | None
    source_type: Literal["USER_CONFIRMED"]


class ContentIdeaOutput(BaseModel):
    id: str
    voice_profile_id: str
    taxonomy_version: str
    pillar: str
    topic: str
    angle: str
    audience_intent: str
    format: Literal["TEXT"]
    evidence: list[SourceReferenceOutput]
    created_at: datetime


class GeneratedClaim(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)
    kind: Literal["SUPPORTED", "OPINION"]
    evidence_indices: list[int] = Field(default_factory=list, max_length=5)


class GeneratedDraft(BaseModel):
    hook: str = Field(min_length=1, max_length=600)
    body: str = Field(min_length=1, max_length=8_000)
    cta: str = Field(min_length=1, max_length=600)
    claims: list[GeneratedClaim] = Field(min_length=1, max_length=30)


class ClaimAssessmentOutput(BaseModel):
    id: str
    claim_text: str
    kind: Literal["SUPPORTED", "OPINION", "CONFIRMED_PERSONAL"]
    source_reference_ids: list[str]


class RevisionCheckOutput(BaseModel):
    id: str
    check_type: Literal["CLAIM_TRACEABILITY", "PROHIBITED_PHRASES", "READABILITY", "ACCESSIBILITY", "ORIGINALITY", "DIVERSITY"]
    severity: Literal["BLOCKING", "WARNING"]
    passed: bool
    message: str
    details: dict[str, Any]


class ReviewOutput(BaseModel):
    id: str
    revision_id: str
    revision_number: int
    action: Literal["SUBMIT", "EDIT", "REQUEST_CHANGES", "REGENERATE", "REJECT", "APPROVE"]
    reason: str | None
    categories: list[str]
    claims_confirmed: bool
    actor: Literal["LOCAL_OWNER"]
    created_at: datetime


class ReviewSubmissionRequest(BaseModel):
    revision_id: str


class ReviewDecisionRequest(BaseModel):
    revision_id: str
    action: Literal["APPROVE", "REJECT", "REQUEST_CHANGES"]
    reason: str | None = Field(default=None, max_length=2_000)
    categories: list[Literal["HOOK", "TONE", "CLARITY", "CTA", "LENGTH", "EVIDENCE"]] = Field(
        default_factory=list, max_length=6
    )
    claims_confirmed: bool = False

    @field_validator("reason")
    @classmethod
    def strip_review_reason(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class PostEditRequest(BaseModel):
    revision_id: str
    hook: str = Field(min_length=1, max_length=600)
    body: str = Field(min_length=1, max_length=8_000)
    cta: str = Field(min_length=1, max_length=600)
    claims_confirmed: Literal[True]

    @field_validator("hook", "body", "cta")
    @classmethod
    def strip_revision_text(cls, value: str) -> str:
        return value.strip()


class RegenerationRequest(BaseModel):
    revision_id: str


class RetrievalReferenceOutput(BaseModel):
    revision_id: str
    post_id: str
    pillar: str
    topic: str
    similarity_score: float
    embedding_version: str
    taxonomy_version: str
    features: dict[str, Any]


class MemoryRevisionOutput(BaseModel):
    revision_id: str
    post_id: str
    revision_number: int
    pillar: str
    topic: str
    taxonomy_version: str
    embedding_version: str
    features: dict[str, Any]
    approved_at: datetime


class PrimaryDraftOutput(BaseModel):
    post_id: str
    revision_id: str
    state: Literal["DRAFT", "IN_REVIEW", "CHANGES_REQUESTED", "REJECTED", "APPROVED", "SCHEDULED", "PUBLISH_ACTION_REQUIRED", "PUBLISHED", "FAILED"]
    revision_number: int
    hook: str
    body: str
    cta: str
    content: str
    pillar: str
    topic: str
    format: Literal["TEXT"]
    taxonomy_version: str
    generation_provider: str
    generation_model: str
    generation_mode: Literal["provider", "deterministic_fallback", "human_edit"]
    generation_warning: str | None
    prompt_version: str
    retrieved_revision_ids: list[str]
    retrievals: list[RetrievalReferenceOutput]
    claims: list[ClaimAssessmentOutput]
    checks: list[RevisionCheckOutput]
    reviews: list[ReviewOutput]
    created_at: datetime


Weekday = Literal["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]


class CalendarCreate(BaseModel):
    start_date: date
    weeks: int = Field(default=4, ge=1, le=8)
    cadence_per_week: int = Field(default=3, ge=1, le=7)
    timezone: str = Field(min_length=1, max_length=80)
    quiet_days: list[Weekday] = Field(default_factory=lambda: ["SATURDAY", "SUNDAY"], max_length=6)


class CalendarSlotOutput(BaseModel):
    id: str
    position: int
    pillar: str
    intended_local_at: str
    resolved_utc_at: datetime
    status: Literal["PLANNED", "ASSIGNED", "CANCELLED"]


class CalendarOutput(BaseModel):
    id: str
    start_date: date
    weeks: int
    cadence_per_week: int
    timezone: str
    quiet_days: list[Weekday]
    slots: list[CalendarSlotOutput]
    created_at: datetime


class ScheduleCreate(BaseModel):
    revision_id: str
    intended_local_at: datetime
    timezone: str = Field(min_length=1, max_length=80)
    calendar_slot_id: str | None = None
    idempotency_key: str = Field(min_length=8, max_length=100)
    dst_fold: Literal[0, 1] | None = None


class ScheduleOutput(BaseModel):
    id: str
    post_id: str
    revision_id: str
    calendar_slot_id: str | None
    timezone: str
    intended_local_at: str
    resolved_utc_at: datetime
    status: Literal["ACTIVE", "REMINDER_DUE", "COMPLETED", "CANCELLED", "FAILED"]
    created_at: datetime


class PublishNowRequest(BaseModel):
    revision_id: str
    idempotency_key: str = Field(min_length=8, max_length=100)


class PublishActionOutput(BaseModel):
    id: str
    schedule_id: str
    post_id: str
    revision_id: str
    method: Literal["COPY_REMINDER"]
    state: Literal["ACTION_REQUIRED", "PUBLISHED", "FAILED"]
    formatted_content: str
    published_url: str | None
    published_at: datetime | None
    failure_reason: str | None


class PublishConfirmation(BaseModel):
    published_url: str | None = Field(default=None, max_length=2_000)
    published_at: datetime | None = None


class PublishFailure(BaseModel):
    reason: str = Field(min_length=3, max_length=2_000)


class PreferenceOutput(BaseModel):
    id: str
    category: str
    instruction: str
    evidence_count: int
    active: bool
    version: int
    updated_at: datetime


class PreferenceUpdate(BaseModel):
    active: bool
