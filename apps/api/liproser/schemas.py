from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr


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
