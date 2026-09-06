from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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


class AnalysisOutput(BaseModel):
    id: str
    profile_id: str
    rubric_version: str
    total_score: float
    criteria: dict[str, Any]
    suggestions: list[SuggestionOutput]


class ProviderCheckRequest(BaseModel):
    provider: Literal["ollama", "openai", "anthropic", "fake"]
    model: str = Field(min_length=1, max_length=200)


class ProviderCheckResponse(BaseModel):
    ready: bool
    provider: str
    model: str
    detail: str
