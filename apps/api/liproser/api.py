from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .budget import BudgetExceededError, reconcile, reserve
from .config import Settings, get_settings
from .database import (
    AiBudgetPeriod,
    Profile,
    ProfileAnalysis,
    ProfileImport,
    ProfileSuggestion,
    ProviderConfiguration,
    get_db,
)
from .profile_service import (
    contains_template_placeholders,
    extract_pdf,
    provider_suggestion_is_safe,
    safe_suggestion,
    score_sections,
)
from .providers import (
    generate_profile_rewrites,
    normalize_model,
    provider_failure_detail,
    provider_readiness,
    provider_secret_source,
)
from .runtime_secrets import clear_session_secret, set_session_secret
from .schemas import (
    AnalysisOutput,
    ConfirmImportRequest,
    DecisionRequest,
    GeneratedSuggestion,
    ImportResponse,
    ManualImportRequest,
    ProfileSections,
    ProviderCheckRequest,
    ProviderCheckResponse,
    ProviderSecretRequest,
    SuggestionOutput,
)
from .storage import LocalStorage

router = APIRouter(prefix="/v1")


def import_output(item: ProfileImport) -> ImportResponse:
    return ImportResponse(
        id=item.id,
        kind=item.kind,
        status=item.status,
        sections=ProfileSections(**item.sections),
        confidence=item.confidence,
        source_retained=bool(item.source_path and not item.source_deleted_at),
        source_name=item.source_name,
    )


@router.get("/setup")
def setup(settings: Settings = Depends(get_settings), db: Session = Depends(get_db)):
    configured = db.get(ProviderConfiguration, 1)
    provider = configured.provider if configured else settings.ai_provider
    model = {
        "ollama": settings.ollama_model,
        "openai": settings.openai_model,
        "anthropic": settings.anthropic_model,
    }.get(provider, "")
    if configured:
        model = configured.model
    provider_ready = bool(configured and configured.ready)
    if provider in {"openai", "anthropic"} and provider_secret_source(settings, provider) == "missing":
        provider_ready = False
    return {
        "personal_mode": settings.personal_mode,
        "provider": provider,
        "model": model,
        "provider_configured": provider_ready,
        "credential_sources": {
            name: provider_secret_source(settings, name) for name in ("openai", "anthropic")
        },
        "secrets_exposed": False,
    }


@router.post("/setup/provider-secret")
def set_provider_secret(body: ProviderSecretRequest, settings: Settings = Depends(get_settings)):
    if not settings.personal_mode:
        raise HTTPException(403, "Session credentials are available only in personal mode")
    set_session_secret(body.provider, body.api_key.get_secret_value())
    return {
        "provider": body.provider,
        "configured": True,
        "source": "session",
        "persisted": False,
        "secrets_exposed": False,
    }


@router.delete("/setup/provider-secret/{provider}")
def delete_provider_secret(
    provider: str, settings: Settings = Depends(get_settings), db: Session = Depends(get_db)
):
    if provider not in {"openai", "anthropic"}:
        raise HTTPException(422, "Only hosted-provider session keys can be cleared")
    if not settings.personal_mode:
        raise HTTPException(403, "Session credentials are available only in personal mode")
    cleared = clear_session_secret(provider)
    configured = db.get(ProviderConfiguration, 1)
    if configured and configured.provider == provider and provider_secret_source(settings, provider) == "missing":
        configured.ready = False
        db.commit()
    return {"provider": provider, "session_key_cleared": cleared, "secrets_exposed": False}


@router.post("/setup/provider-check", response_model=ProviderCheckResponse)
def provider_check(
    body: ProviderCheckRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    reservation = None
    model = normalize_model(body.provider, body.model)
    try:
        if body.provider in {"openai", "anthropic"}:
            reservation = reserve(db, body.provider, 0.01, settings.ai_monthly_budget_usd)
        ready, detail = provider_readiness(settings, body.provider, model)
        if reservation:
            reconcile(db, reservation.id, 0.01 if ready else 0)
        if ready:
            configured = db.get(ProviderConfiguration, 1)
            if configured is None:
                configured = ProviderConfiguration(
                    id=1, provider=body.provider, model=model, ready=True
                )
                db.add(configured)
            else:
                configured.provider = body.provider
                configured.model = model
                configured.ready = True
                configured.checked_at = datetime.now(UTC)
            db.commit()
    except BudgetExceededError as exc:
        raise HTTPException(402, str(exc)) from exc
    except Exception as exc:
        if reservation:
            reconcile(db, reservation.id, 0)
        ready, detail = False, provider_failure_detail(body.provider, exc)
    return ProviderCheckResponse(
        ready=ready, provider=body.provider, model=model, detail=detail
    )


@router.post("/profile-imports", response_model=ImportResponse, status_code=201)
async def create_profile_import(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
):
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        body = ManualImportRequest.model_validate(await request.json())
        item = ProfileImport(
            id=str(uuid4()),
            kind="MANUAL",
            sections=body.sections.model_dump(),
            confidence={
                key: 1.0 if value.strip() else 0.0
                for key, value in body.sections.model_dump().items()
            },
        )
        db.add(item)
        db.commit()
        return import_output(item)
    form = await request.form()
    file = form.get("file")
    if not file or not hasattr(file, "read"):
        raise HTTPException(422, "Provide MANUAL JSON or a multipart PDF file")
    content = await file.read(settings.max_pdf_bytes + 1)
    if len(content) > settings.max_pdf_bytes:
        raise HTTPException(413, "PDF exceeds configured size limit")
    try:
        sections, confidence = extract_pdf(content)
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc
    storage = LocalStorage(settings.private_storage_root)
    stored_path, digest = storage.put_pdf(content)
    item = ProfileImport(
        id=str(uuid4()),
        kind="PDF",
        sections=sections.model_dump(),
        confidence=confidence,
        source_path=stored_path,
        source_hash=digest,
        source_name=Path(file.filename or "profile.pdf").name,
        source_size=len(content),
    )
    db.add(item)
    db.commit()
    return import_output(item)


@router.get("/profile-imports/{import_id}", response_model=ImportResponse)
def get_import(import_id: str, db: Session = Depends(get_db)):
    item = db.get(ProfileImport, import_id)
    if not item:
        raise HTTPException(404, "Profile import not found")
    return import_output(item)


@router.post("/profile-imports/{import_id}/confirm")
def confirm_import(import_id: str, body: ConfirmImportRequest, db: Session = Depends(get_db)):
    item = db.get(ProfileImport, import_id)
    if not item:
        raise HTTPException(404, "Profile import not found")
    item.sections = body.sections.model_dump()
    item.status = "CONFIRMED"
    profile = db.scalar(select(Profile).where(Profile.import_id == import_id))
    if profile is None:
        profile = Profile(
            id=str(uuid4()),
            import_id=import_id,
            sections=item.sections,
            target_role=body.target_role,
            domain=body.domain,
        )
        db.add(profile)
    else:
        profile.sections = item.sections
        profile.target_role = body.target_role
        profile.domain = body.domain
    db.commit()
    return {"profile_id": profile.id, "status": "CONFIRMED"}


@router.delete("/profile-imports/{import_id}/source")
def delete_source(
    import_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
):
    item = db.get(ProfileImport, import_id)
    if not item:
        raise HTTPException(404, "Profile import not found")
    if item.source_path:
        LocalStorage(settings.private_storage_root).delete(item.source_path)
    item.source_deleted_at = datetime.now(UTC)
    item.source_path = None
    db.commit()
    return {"deleted": True, "import_id": import_id, "confirmed_sections_retained": True}


@router.get("/profile-imports/{import_id}/source")
def download_source(import_id: str, db: Session = Depends(get_db)):
    item = db.get(ProfileImport, import_id)
    if not item or not item.source_path or item.source_deleted_at:
        raise HTTPException(404, "Retained source not found")
    return FileResponse(item.source_path, media_type="application/pdf", filename=item.source_name)


def analysis_output(db: Session, analysis: ProfileAnalysis) -> AnalysisOutput:
    items = db.scalars(
        select(ProfileSuggestion).where(ProfileSuggestion.analysis_id == analysis.id)
    ).all()
    generation = analysis.criteria.get("_generation", {})
    criteria = {key: value for key, value in analysis.criteria.items() if key != "_generation"}
    return AnalysisOutput(
        id=analysis.id,
        profile_id=analysis.profile_id,
        rubric_version=analysis.rubric_version,
        total_score=analysis.total_score,
        criteria=criteria,
        suggestions=[
            SuggestionOutput.model_validate(
                {
                    "id": x.id,
                    "section": x.section,
                    "before": x.before,
                    "after": x.after,
                    "rationale": x.rationale,
                    "preserved_facts": x.preserved_facts,
                    "proposed_claims": x.proposed_claims,
                    "confidence": x.confidence,
                    "decision": x.decision,
                }
            )
            for x in items
        ],
        generation_provider=generation.get("provider", "deterministic"),
        generation_model=generation.get("model", "profile-safe@1"),
        generation_mode=generation.get("mode", "deterministic_fallback"),
        generation_warning=generation.get("warning"),
    )


@router.post("/profiles/{profile_id}/analyses", response_model=AnalysisOutput, status_code=201)
def analyze(
    profile_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    profile = db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    sections = ProfileSections(**profile.sections)
    total, criteria = score_sections(sections)
    configured = db.get(ProviderConfiguration, 1)
    generated: dict[str, GeneratedSuggestion] = {}
    generation = {
        "provider": "deterministic",
        "model": "profile-safe@1",
        "mode": "deterministic_fallback",
        "warning": None,
    }
    reservation = None
    if (
        configured
        and configured.ready
        and configured.provider not in {"fake", "unconfigured"}
        and (
            configured.provider not in {"openai", "anthropic"}
            or provider_secret_source(settings, configured.provider) != "missing"
        )
    ):
        generation.update(provider=configured.provider, model=configured.model)
        try:
            if configured.provider in {"openai", "anthropic"}:
                estimate = min(0.10, settings.ai_max_request_cost_usd)
                reservation = reserve(
                    db, configured.provider, estimate, settings.ai_monthly_budget_usd
                )
            raw, _usage = generate_profile_rewrites(
                settings,
                configured.provider,
                configured.model,
                sections,
                profile.target_role,
                profile.domain,
            )
            parsed = [GeneratedSuggestion.model_validate(item) for item in raw]
            if len(parsed) != len(ProfileSections.model_fields):
                raise ValueError("Provider did not return all profile sections")
            generated = {item.section: item for item in parsed}
            if set(generated) != set(ProfileSections.model_fields):
                raise ValueError("Provider returned duplicate or unknown profile sections")
            generation["mode"] = "provider"
            if reservation:
                reconcile(db, reservation.id, reservation.estimated_usd)
        except BudgetExceededError:
            generation["warning"] = "AI budget exhausted; deterministic suggestions were used."
        except Exception as exc:
            if reservation and reservation.status == "RESERVED":
                reconcile(db, reservation.id, 0)
            status = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f" (provider status {status})" if status else ""
            generation["warning"] = f"AI provider unavailable; deterministic suggestions were used{suffix}."
    elif configured and configured.provider in {"openai", "anthropic"}:
        generation.update(
            provider=configured.provider,
            model=configured.model,
            warning="The hosted provider key is missing; deterministic suggestions were used.",
        )
    criteria["_generation"] = generation
    analysis = ProfileAnalysis(
        id=str(uuid4()), profile_id=profile_id, total_score=total, criteria=criteria
    )
    db.add(analysis)
    unsafe_sections: list[str] = []
    for section, before in sections.model_dump().items():
        candidate = generated.get(section)
        if candidate and before.strip() and provider_suggestion_is_safe(
            before, candidate.after, candidate.proposed_claims
        ):
            after = candidate.after
            rationale = candidate.rationale
            preserved = candidate.preserved_facts
            proposed = candidate.proposed_claims
            confidence = candidate.confidence
        else:
            if candidate and before.strip():
                unsafe_sections.append(section)
            after, rationale, preserved, proposed, confidence = safe_suggestion(section, before)
        db.add(
            ProfileSuggestion(
                id=str(uuid4()),
                analysis_id=analysis.id,
                section=section,
                before=before,
                after=after,
                rationale=rationale,
                preserved_facts=preserved,
                proposed_claims=proposed,
                confidence=confidence,
            )
        )
    if unsafe_sections:
        generation["warning"] = (
            "Some AI rewrites failed fact-preservation checks and used deterministic fallbacks: "
            + ", ".join(unsafe_sections)
            + "."
        )
        analysis.criteria = criteria
    db.commit()
    return analysis_output(db, analysis)


@router.post("/profile-suggestions/{suggestion_id}/decisions")
def decide(suggestion_id: str, body: DecisionRequest, db: Session = Depends(get_db)):
    suggestion = db.get(ProfileSuggestion, suggestion_id)
    if not suggestion:
        raise HTTPException(404, "Suggestion not found")
    if suggestion.decision:
        raise HTTPException(409, "Suggestion already decided")
    if body.action == "EDIT_AND_ACCEPT" and not body.edited_text:
        raise HTTPException(422, "edited_text is required")
    if not suggestion.before.strip() and body.action == "ACCEPT":
        raise HTTPException(422, "Fill the template with verified details before accepting it")
    if (
        not suggestion.before.strip()
        and body.action == "EDIT_AND_ACCEPT"
        and contains_template_placeholders(body.edited_text or "")
    ):
        raise HTTPException(422, "Replace every bracketed prompt with verified details")
    suggestion.decision = body.action
    suggestion.decided_text = (
        body.edited_text
        if body.action == "EDIT_AND_ACCEPT"
        else (suggestion.after if body.action == "ACCEPT" else None)
    )
    suggestion.decision_reason = body.reason
    suggestion.decided_at = datetime.now(UTC)
    if suggestion.decided_text:
        analysis = db.get(ProfileAnalysis, suggestion.analysis_id)
        profile = db.get(Profile, analysis.profile_id)
        updated = dict(profile.sections)
        updated[suggestion.section] = suggestion.decided_text
        profile.sections = updated
    db.commit()
    return {
        "id": suggestion.id,
        "decision": suggestion.decision,
        "decided_text": suggestion.decided_text,
    }


@router.post("/profiles/{profile_id}/rescore", response_model=AnalysisOutput)
def rescore(
    profile_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return analyze(profile_id, db, settings)


@router.get("/usage/ai-budget")
def ai_budget(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    now = datetime.now(UTC)
    period_id = now.strftime("%Y-%m")
    period = db.get(AiBudgetPeriod, period_id)
    if not period:
        period = AiBudgetPeriod(
            period=period_id, limit_usd=settings.ai_monthly_budget_usd, actual_usd=0, reserved_usd=0
        )
        db.add(period)
        db.commit()
    remaining = max(period.limit_usd - period.actual_usd - period.reserved_usd, 0)
    if now.month == 12:
        reset = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        reset = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    return {
        "period": period.period,
        "limit_usd": period.limit_usd,
        "actual_usd": period.actual_usd,
        "reserved_usd": period.reserved_usd,
        "remaining_usd": remaining,
        "warning": period.actual_usd + period.reserved_usd
        >= period.limit_usd * settings.ai_budget_warning_percent / 100,
        "reset_at": reset,
    }
