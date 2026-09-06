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
from .profile_service import extract_pdf, safe_suggestion, score_sections
from .providers import provider_readiness
from .schemas import (
    AnalysisOutput,
    ConfirmImportRequest,
    DecisionRequest,
    ImportResponse,
    ManualImportRequest,
    ProfileSections,
    ProviderCheckRequest,
    ProviderCheckResponse,
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
    return {
        "personal_mode": settings.personal_mode,
        "provider": provider,
        "model": model,
        "provider_configured": bool(configured and configured.ready),
        "secrets_exposed": False,
    }


@router.post("/setup/provider-check", response_model=ProviderCheckResponse)
def provider_check(
    body: ProviderCheckRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    reservation = None
    try:
        if body.provider in {"openai", "anthropic"}:
            reservation = reserve(db, body.provider, 0.01, settings.ai_monthly_budget_usd)
        ready, detail = provider_readiness(settings, body.provider, body.model)
        if reservation:
            reconcile(db, reservation.id, 0.01 if ready else 0)
        if ready:
            configured = db.get(ProviderConfiguration, 1)
            if configured is None:
                configured = ProviderConfiguration(
                    id=1, provider=body.provider, model=body.model, ready=True
                )
                db.add(configured)
            else:
                configured.provider = body.provider
                configured.model = body.model
                configured.ready = True
                configured.checked_at = datetime.now(UTC)
            db.commit()
    except BudgetExceededError as exc:
        raise HTTPException(402, str(exc)) from exc
    except (OSError, ValueError) as exc:
        if reservation:
            reconcile(db, reservation.id, 0)
        ready, detail = False, f"Provider check failed: {type(exc).__name__}"
    except Exception as exc:
        if reservation:
            reconcile(db, reservation.id, 0)
        ready, detail = (
            False,
            f"Provider check failed with status {getattr(exc, 'response', None).status_code if getattr(exc, 'response', None) else 'unavailable'}",
        )
    return ProviderCheckResponse(
        ready=ready, provider=body.provider, model=body.model, detail=detail
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
    return AnalysisOutput(
        id=analysis.id,
        profile_id=analysis.profile_id,
        rubric_version=analysis.rubric_version,
        total_score=analysis.total_score,
        criteria=analysis.criteria,
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
    )


@router.post("/profiles/{profile_id}/analyses", response_model=AnalysisOutput, status_code=201)
def analyze(profile_id: str, db: Session = Depends(get_db)):
    profile = db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    sections = ProfileSections(**profile.sections)
    total, criteria = score_sections(sections)
    analysis = ProfileAnalysis(
        id=str(uuid4()), profile_id=profile_id, total_score=total, criteria=criteria
    )
    db.add(analysis)
    for section, before in sections.model_dump().items():
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
def rescore(profile_id: str, db: Session = Depends(get_db)):
    return analyze(profile_id, db)


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
