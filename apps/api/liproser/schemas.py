from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

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
