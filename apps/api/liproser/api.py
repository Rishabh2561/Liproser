from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .budget import BudgetExceededError, reconcile, reserve
from .config import Settings, get_settings
from .content_service import (
    audience_tags,
    canonical_tag,
    deterministic_primary_draft,
    deterministic_regeneration_draft,
    evaluate_revision_checks,
    generated_draft_is_traceable,
    user_edit_claims,
)
from .database import (
    BOOTSTRAP_WORKSPACE_ID,
    AiBudgetPeriod,
    CalendarSlot,
    ClaimAssessment,
    ContentCalendar,
    ContentIdea,
    EditDelta,
    Post,
    PostRevision,
    PostSchedule,
    PreferenceRule,
    Profile,
    ProfileAnalysis,
    ProfileImport,
    ProfileSuggestion,
    ProviderConfiguration,
    PublishAction,
    Review,
    RevisionCheck,
    RevisionRetrieval,
    SourceReference,
    TaxonomySnapshot,
    VoiceProfile,
    VoiceSample,
    get_db,
)
from .memory_service import (
    eligible_revisions,
    memory_checks,
    record_retrievals,
    retrieve_memory,
    structural_features,
    upsert_memory_status,
)
from .profile_service import (
    contains_template_placeholders,
    extract_pdf,
    provider_suggestion_is_safe,
    safe_suggestion,
    score_sections,
)
from .providers import (
    generate_primary_draft,
    generate_profile_rewrites,
    normalize_model,
    provider_failure_detail,
    provider_readiness,
    provider_secret_source,
)
from .runtime_secrets import clear_session_secret, set_session_secret
from .schedule_service import (
    add_outbox,
    build_calendar,
    create_publish_action,
    exact_approval_valid,
    record_feedback,
    resolve_local,
    synthesize_preferences,
)
from .schemas import (
    AnalysisOutput,
    CalendarCreate,
    CalendarOutput,
    CalendarSlotOutput,
    ClaimAssessmentOutput,
    ConfirmImportRequest,
    ContentIdeaCreate,
    ContentIdeaOutput,
    DecisionRequest,
    GeneratedDraft,
    GeneratedSuggestion,
    ImportResponse,
    ManualImportRequest,
    MemoryRevisionOutput,
    PostEditRequest,
    PreferenceOutput,
    PreferenceUpdate,
    PrimaryDraftOutput,
    ProfileSections,
    ProviderCheckRequest,
    ProviderCheckResponse,
    ProviderSecretRequest,
    PublishActionOutput,
    PublishConfirmation,
    PublishFailure,
    PublishNowRequest,
    RegenerationRequest,
    RetrievalReferenceOutput,
    ReviewDecisionRequest,
    ReviewOutput,
    ReviewSubmissionRequest,
    RevisionCheckOutput,
    ScheduleCreate,
    ScheduleOutput,
    SourceReferenceOutput,
    SuggestionOutput,
    TaxonomyOutput,
    VoiceProfileCreate,
    VoiceProfileOutput,
    VoiceSampleOutput,
)
from .storage import LocalStorage

router = APIRouter(prefix="/v1")


def calendar_output(db: Session, calendar: ContentCalendar) -> CalendarOutput:
    slots = db.scalars(select(CalendarSlot).where(CalendarSlot.calendar_id == calendar.id).order_by(CalendarSlot.position)).all()
    return CalendarOutput(id=calendar.id, start_date=calendar.start_date, weeks=calendar.weeks, cadence_per_week=calendar.cadence_per_week, timezone=calendar.timezone, quiet_days=calendar.quiet_days, slots=[CalendarSlotOutput(id=item.id, position=item.position, pillar=item.pillar, intended_local_at=item.intended_local_at, resolved_utc_at=item.resolved_utc_at, status=item.status) for item in slots], created_at=calendar.created_at)


def schedule_output(item: PostSchedule) -> ScheduleOutput:
    return ScheduleOutput(id=item.id, post_id=item.post_id, revision_id=item.revision_id, calendar_slot_id=item.calendar_slot_id, timezone=item.timezone, intended_local_at=item.intended_local_at, resolved_utc_at=item.resolved_utc_at, status=item.status, created_at=item.created_at)


def publish_action_output(item: PublishAction) -> PublishActionOutput:
    return PublishActionOutput(id=item.id, schedule_id=item.schedule_id, post_id=item.post_id, revision_id=item.revision_id, method=item.method, state=item.state, formatted_content=item.formatted_content, published_url=item.published_url, published_at=item.published_at, failure_reason=item.failure_reason)


def preference_output(item: PreferenceRule) -> PreferenceOutput:
    return PreferenceOutput(id=item.id, category=item.category, instruction=item.instruction, evidence_count=item.evidence_count, active=item.active, version=item.version, updated_at=item.updated_at)


def voice_profile_output(db: Session, profile: VoiceProfile) -> VoiceProfileOutput:
    samples = db.scalars(
        select(VoiceSample)
        .where(VoiceSample.voice_profile_id == profile.id)
        .order_by(VoiceSample.position)
    ).all()
    return VoiceProfileOutput(
        id=profile.id,
        version=profile.version,
        domain=profile.domain,
        target_audience=profile.target_audience,
        content_pillars=profile.content_pillars,
        tone_preferences=profile.tone_preferences,
        prohibited_phrases=profile.prohibited_phrases,
        samples_are_user_owned=profile.samples_are_user_owned,
        taxonomy_version=profile.taxonomy_version,
        samples=[
            VoiceSampleOutput(
                id=sample.id,
                position=sample.position,
                text=sample.text,
                source_type="USER_OWNED",
            )
            for sample in samples
        ],
        created_at=profile.created_at,
    )


def content_idea_output(db: Session, idea: ContentIdea) -> ContentIdeaOutput:
    evidence = db.scalars(
        select(SourceReference)
        .where(SourceReference.content_idea_id == idea.id)
        .order_by(SourceReference.created_at, SourceReference.id)
    ).all()
    return ContentIdeaOutput(
        id=idea.id,
        voice_profile_id=idea.voice_profile_id,
        taxonomy_version=idea.taxonomy_version,
        pillar=idea.pillar,
        topic=idea.topic,
        angle=idea.angle,
        audience_intent=idea.audience_intent,
        format="TEXT",
        evidence=[
            SourceReferenceOutput(
                id=item.id,
                statement=item.statement,
                source_url=item.source_url,
                freshness_date=item.freshness_date,
                source_type="USER_CONFIRMED",
            )
            for item in evidence
        ],
        created_at=idea.created_at,
    )


def primary_draft_output(db: Session, post: Post, revision: PostRevision) -> PrimaryDraftOutput:
    idea = db.get(ContentIdea, post.content_idea_id)
    claims = db.scalars(
        select(ClaimAssessment).where(ClaimAssessment.post_revision_id == revision.id)
    ).all()
    checks = db.scalars(
        select(RevisionCheck)
        .where(RevisionCheck.post_revision_id == revision.id)
        .order_by(RevisionCheck.created_at, RevisionCheck.id)
    ).all()
    reviews = db.scalars(
        select(Review).where(Review.post_id == post.id).order_by(Review.created_at, Review.id)
    ).all()
    retrieval_rows = db.scalars(
        select(RevisionRetrieval)
        .where(RevisionRetrieval.generated_revision_id == revision.id)
        .order_by(RevisionRetrieval.rank)
    ).all()
    retrievals = []
    for row in retrieval_rows:
        reference = db.get(PostRevision, row.reference_revision_id)
        reference_post = db.get(Post, reference.post_id) if reference else None
        reference_idea = db.get(ContentIdea, reference_post.content_idea_id) if reference_post else None
        if reference and reference_post and reference_idea:
            retrievals.append(
                RetrievalReferenceOutput(
                    revision_id=reference.id,
                    post_id=reference_post.id,
                    pillar=reference_idea.pillar,
                    topic=reference_idea.topic,
                    similarity_score=row.similarity_score,
                    embedding_version=row.embedding_version,
                    taxonomy_version=row.taxonomy_version,
                    features=structural_features(reference),
                )
            )
    revision_numbers = dict(
        db.execute(
            select(PostRevision.id, PostRevision.revision_number).where(
                PostRevision.post_id == post.id
            )
        ).all()
    )
    return PrimaryDraftOutput(
        post_id=post.id,
        revision_id=revision.id,
        state=post.state,
        revision_number=revision.revision_number,
        hook=revision.hook,
        body=revision.body,
        cta=revision.cta,
        content=revision.content,
        pillar=idea.pillar,
        topic=idea.topic,
        format="TEXT",
        taxonomy_version=revision.taxonomy_version,
        generation_provider=revision.generation_provider,
        generation_model=revision.generation_model,
        generation_mode=revision.generation_mode,
        generation_warning=revision.generation_warning,
        prompt_version=revision.prompt_version,
        retrieved_revision_ids=revision.retrieved_revision_ids,
        retrievals=retrievals,
        claims=[
            ClaimAssessmentOutput(
                id=claim.id,
                claim_text=claim.claim_text,
                kind=claim.kind,
                source_reference_ids=claim.source_reference_ids,
            )
            for claim in claims
        ],
        checks=[
            RevisionCheckOutput(
                id=check.id,
                check_type=check.check_type,
                severity=check.severity,
                passed=check.passed,
                message=check.message,
                details=check.details,
            )
            for check in checks
        ],
        reviews=[
            ReviewOutput(
                id=review.id,
                revision_id=review.revision_id,
                revision_number=revision_numbers[review.revision_id],
                action=review.action,
                reason=review.reason,
                categories=review.categories,
                claims_confirmed=review.claims_confirmed,
                actor="LOCAL_OWNER",
                created_at=review.created_at,
            )
            for review in reviews
        ],
        created_at=revision.created_at,
    )


def current_revision(db: Session, post: Post) -> PostRevision:
    revision = db.scalars(
        select(PostRevision)
        .where(PostRevision.post_id == post.id)
        .order_by(PostRevision.revision_number.desc())
        .limit(1)
    ).first()
    if not revision:
        raise HTTPException(409, "Post has no revision")
    return revision


def require_current_revision(db: Session, post: Post, revision_id: str) -> PostRevision:
    revision = current_revision(db, post)
    if revision.id != revision_id:
        raise HTTPException(409, "The requested revision is stale; review the current revision")
    return revision


def revision_context(db: Session, post: Post):
    idea = db.get(ContentIdea, post.content_idea_id)
    voice = db.get(VoiceProfile, idea.voice_profile_id)
    evidence = db.scalars(
        select(SourceReference)
        .where(SourceReference.content_idea_id == idea.id)
        .order_by(SourceReference.created_at, SourceReference.id)
    ).all()
    allowed_context = "\n".join(
        (
            voice.domain,
            voice.target_audience,
            idea.pillar,
            idea.topic,
            idea.angle,
            idea.audience_intent,
        )
    )
    return idea, voice, evidence, allowed_context


def persist_revision_checks(
    db: Session,
    revision: PostRevision,
    claims: list[dict],
    allowed_context: str,
    evidence: list[SourceReference],
    prohibited_phrases: list[str],
    memory_references: list[dict] | None = None,
) -> None:
    findings = evaluate_revision_checks(
        revision.content,
        claims,
        allowed_context,
        [item.statement for item in evidence],
        prohibited_phrases,
    )
    findings.extend(memory_checks(revision.content, revision.hook, memory_references or [], db))
    for finding in findings:
        db.add(
            RevisionCheck(
                id=str(uuid4()),
                post_revision_id=revision.id,
                check_type=finding["check_type"],
                severity=finding["severity"],
                passed=finding["passed"],
                message=finding["message"],
                details=finding["details"],
            )
        )


def ensure_revision_checks(db: Session, post: Post, revision: PostRevision) -> None:
    # The eligible memory corpus can change between draft creation and approval.
    # Re-running every check at each review boundary prevents stale originality results.
    for check in db.scalars(
        select(RevisionCheck).where(RevisionCheck.post_revision_id == revision.id)
    ).all():
        db.delete(check)
    _, voice, evidence, allowed_context = revision_context(db, post)
    claims = db.scalars(
        select(ClaimAssessment).where(ClaimAssessment.post_revision_id == revision.id)
    ).all()
    persist_revision_checks(
        db,
        revision,
        [{"text": claim.claim_text, "kind": claim.kind} for claim in claims],
        allowed_context,
        evidence,
        voice.prohibited_phrases,
        retrieve_memory(
            db,
            query=revision.content,
            taxonomy_version=revision.taxonomy_version,
            exclude_post_id=post.id,
        ),
    )
    db.flush()


def generate_content_candidate(
    db: Session,
    settings: Settings,
    idea: ContentIdea,
    voice: VoiceProfile,
    evidence: list[SourceReference],
    feedback: dict | None = None,
    previous_revision: PostRevision | None = None,
    memory_references: list[dict] | None = None,
):
    samples = db.scalars(
        select(VoiceSample)
        .where(VoiceSample.voice_profile_id == voice.id)
        .order_by(VoiceSample.position)
    ).all()
    generated = (
        deterministic_regeneration_draft(
            idea.topic,
            idea.angle,
            feedback.get("categories", []),
            [item.statement for item in evidence],
        )
        if feedback
        else deterministic_primary_draft(idea.topic, idea.angle)
    )
    generation = {
        "provider": "deterministic",
        "model": "primary-draft-safe@1",
        "mode": "deterministic_fallback",
        "warning": (
            "No ready AI provider was available; a safe category-based regeneration was used. "
            "Free-form instructions may require a ready AI provider."
            if feedback
            else "No ready AI provider was available; a safe structured draft was used."
        ),
    }
    configured = db.get(ProviderConfiguration, 1)
    reservation = None
    if configured:
        generation.update(provider=configured.provider, model=configured.model)
    provider_ready = bool(configured and configured.ready)
    if configured and configured.provider in {"openai", "anthropic"}:
        provider_ready = (
            provider_ready
            and provider_secret_source(settings, configured.provider) != "missing"
        )
    if configured and provider_ready and configured.provider not in {"fake", "unconfigured"}:
        try:
            if configured.provider in {"openai", "anthropic"}:
                estimate = min(0.25, settings.ai_max_request_cost_usd)
                reservation = reserve(
                    db, configured.provider, estimate, settings.ai_monthly_budget_usd
                )
            idea_payload = {
                "pillar": idea.pillar,
                "topic": idea.topic,
                "angle": idea.angle,
                "audience_intent": idea.audience_intent,
                "format": idea.format,
                "first_party_patterns": [
                    {
                        "pillar": item["pillar"],
                        "topic": item["topic"],
                        "similarity_score": item["similarity_score"],
                        "features": item["features"],
                    }
                    for item in (memory_references or [])
                ],
            }
            if feedback:
                idea_payload["regeneration_feedback"] = feedback
            if previous_revision:
                idea_payload["previous_revision"] = {
                    "hook": previous_revision.hook,
                    "body": previous_revision.body,
                    "cta": previous_revision.cta,
                }
            raw, _usage = generate_primary_draft(
                settings,
                configured.provider,
                configured.model,
                {
                    "domain": voice.domain,
                    "target_audience": voice.target_audience,
                    "tone_preferences": voice.tone_preferences,
                    "prohibited_phrases": voice.prohibited_phrases,
                    "user_owned_samples": [sample.text for sample in samples],
                },
                idea_payload,
                [
                    {
                        "index": index,
                        "statement": item.statement,
                        "source_url": item.source_url,
                        "freshness_date": item.freshness_date,
                    }
                    for index, item in enumerate(evidence, start=1)
                ],
            )
            candidate = GeneratedDraft.model_validate(raw)
            candidate_data = candidate.model_dump()
            allowed_context = "\n".join(
                (
                    voice.domain,
                    voice.target_audience,
                    idea.pillar,
                    idea.topic,
                    idea.angle,
                    idea.audience_intent,
                )
            )
            content = "\n\n".join((candidate.hook, candidate.body, candidate.cta))
            prohibited = any(
                phrase.casefold() in content.casefold() for phrase in voice.prohibited_phrases
            )
            traceable = generated_draft_is_traceable(
                candidate.hook,
                candidate.body,
                candidate.cta,
                [claim.model_dump() for claim in candidate.claims],
                [item.statement for item in evidence],
                allowed_context,
            )
            if prohibited or not traceable:
                generation["warning"] = (
                    "The AI draft failed evidence or voice-boundary checks; a safe draft was used."
                )
            else:
                generated = candidate_data
                generation.update(mode="provider", warning=None)
            if reservation:
                reconcile(db, reservation.id, reservation.estimated_usd)
        except BudgetExceededError:
            generation["warning"] = "AI budget exhausted; a safe structured draft was used."
        except Exception as exc:
            if reservation and reservation.status == "RESERVED":
                reconcile(db, reservation.id, 0)
            generation["warning"] = provider_failure_detail(configured.provider, exc)
    elif configured and configured.provider == "fake":
        generation["warning"] = "The fake provider uses the safe deterministic draft."
    return generated, generation


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


@router.post("/voice-profiles", response_model=VoiceProfileOutput, status_code=201)
def create_voice_profile(body: VoiceProfileCreate, db: Session = Depends(get_db)):
    current_version = db.scalar(
        select(func.max(VoiceProfile.version)).where(
            VoiceProfile.workspace_id == BOOTSTRAP_WORKSPACE_ID
        )
    )
    version = int(current_version or 0) + 1
    taxonomy_version = f"taxonomy@{version}"
    profile = VoiceProfile(
        id=str(uuid4()),
        version=version,
        domain=body.domain,
        target_audience=body.target_audience,
        content_pillars=body.content_pillars,
        tone_preferences=body.tone_preferences,
        prohibited_phrases=body.prohibited_phrases,
        samples_are_user_owned=True,
        taxonomy_version=taxonomy_version,
    )
    db.add(profile)
    db.flush()
    for position, text in enumerate(body.samples, start=1):
        db.add(
            VoiceSample(
                id=str(uuid4()),
                voice_profile_id=profile.id,
                position=position,
                text=text,
                source_type="USER_OWNED",
            )
        )
    db.add(
        TaxonomySnapshot(
            id=str(uuid4()),
            version=taxonomy_version,
            domain_tag=canonical_tag(body.domain),
            pillar_tags=[canonical_tag(item) for item in body.content_pillars],
            audience_tags=audience_tags(body.target_audience),
            topic_tags=[],
        )
    )
    db.commit()
    db.refresh(profile)
    return voice_profile_output(db, profile)


@router.get("/voice-profiles/current", response_model=VoiceProfileOutput)
def current_voice_profile(db: Session = Depends(get_db)):
    profile = db.scalars(
        select(VoiceProfile)
        .where(VoiceProfile.workspace_id == BOOTSTRAP_WORKSPACE_ID)
        .order_by(VoiceProfile.version.desc())
        .limit(1)
    ).first()
    if not profile:
        raise HTTPException(404, "Voice profile has not been configured")
    return voice_profile_output(db, profile)


@router.get("/taxonomy/current", response_model=TaxonomyOutput)
def current_taxonomy(db: Session = Depends(get_db)):
    profile = db.scalars(
        select(VoiceProfile)
        .where(VoiceProfile.workspace_id == BOOTSTRAP_WORKSPACE_ID)
        .order_by(VoiceProfile.version.desc())
        .limit(1)
    ).first()
    taxonomy = (
        db.scalars(
            select(TaxonomySnapshot).where(
                TaxonomySnapshot.workspace_id == BOOTSTRAP_WORKSPACE_ID,
                TaxonomySnapshot.version == profile.taxonomy_version,
            )
        ).first()
        if profile
        else None
    )
    if not taxonomy:
        raise HTTPException(404, "Taxonomy has not been configured")
    return TaxonomyOutput(
        version=taxonomy.version,
        domain_tag=taxonomy.domain_tag,
        pillar_tags=taxonomy.pillar_tags,
        audience_tags=taxonomy.audience_tags,
        topic_tags=taxonomy.topic_tags,
        created_at=taxonomy.created_at,
    )


@router.get("/memory/revisions", response_model=list[MemoryRevisionOutput])
def list_memory_revisions(db: Session = Depends(get_db)):
    items = []
    for revision, post, idea, embedding in eligible_revisions(db):
        approval = db.scalars(
            select(Review)
            .where(Review.revision_id == revision.id, Review.action == "APPROVE")
            .order_by(Review.created_at.desc())
            .limit(1)
        ).first()
        if approval is None:
            continue
        items.append(
            MemoryRevisionOutput(
                revision_id=revision.id,
                post_id=post.id,
                revision_number=revision.revision_number,
                pillar=idea.pillar,
                topic=idea.topic,
                taxonomy_version=revision.taxonomy_version,
                embedding_version=embedding.embedding_version,
                features=structural_features(revision),
                approved_at=approval.created_at,
            )
        )
    return items


@router.post("/calendars", response_model=CalendarOutput, status_code=201)
def create_calendar(body: CalendarCreate, db: Session = Depends(get_db)):
    voice = db.scalars(select(VoiceProfile).where(VoiceProfile.workspace_id == BOOTSTRAP_WORKSPACE_ID).order_by(VoiceProfile.version.desc()).limit(1)).first()
    if not voice:
        raise HTTPException(409, "Configure a voice profile before planning a calendar")
    try:
        calendar = build_calendar(db, voice, body.start_date, body.weeks, body.cadence_per_week, body.timezone, list(body.quiet_days))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    db.refresh(calendar)
    return calendar_output(db, calendar)


@router.get("/calendars/current", response_model=CalendarOutput)
def current_calendar(db: Session = Depends(get_db)):
    calendar = db.scalars(select(ContentCalendar).where(ContentCalendar.workspace_id == BOOTSTRAP_WORKSPACE_ID).order_by(ContentCalendar.created_at.desc(), ContentCalendar.id.desc()).limit(1)).first()
    if not calendar:
        raise HTTPException(404, "No content calendar has been planned")
    return calendar_output(db, calendar)


@router.post("/posts/{post_id}/schedules", response_model=ScheduleOutput, status_code=201)
def create_schedule(post_id: str, body: ScheduleCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(PostSchedule).where(PostSchedule.workspace_id == BOOTSTRAP_WORKSPACE_ID, PostSchedule.idempotency_key == body.idempotency_key))
    if existing:
        expected_local = body.intended_local_at.isoformat(timespec="minutes")
        if (
            existing.post_id != post_id
            or existing.revision_id != body.revision_id
            or existing.calendar_slot_id != body.calendar_slot_id
            or existing.timezone != body.timezone
            or existing.intended_local_at != expected_local
        ):
            raise HTTPException(409, "Idempotency key belongs to a different schedule request")
        return schedule_output(existing)
    post, revision = db.get(Post, post_id), db.get(PostRevision, body.revision_id)
    if not post or not revision or revision.post_id != post_id or not exact_approval_valid(db, post, revision):
        raise HTTPException(409, "Only the exact currently approved revision can be scheduled")
    try:
        local_text, utc_value = resolve_local(body.intended_local_at, body.timezone, body.dst_fold)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if utc_value <= datetime.now(UTC):
        raise HTTPException(422, "Schedule time must be in the future")
    slot = db.get(CalendarSlot, body.calendar_slot_id) if body.calendar_slot_id else None
    if body.calendar_slot_id and (not slot or slot.workspace_id != BOOTSTRAP_WORKSPACE_ID or slot.status != "PLANNED"):
        raise HTTPException(409, "Calendar slot is unavailable")
    if slot:
        slot_utc = slot.resolved_utc_at.replace(tzinfo=UTC) if slot.resolved_utc_at.tzinfo is None else slot.resolved_utc_at
        if slot_utc != utc_value or body.timezone != db.get(ContentCalendar, slot.calendar_id).timezone:
            raise HTTPException(422, "Schedule must match the selected calendar slot")
        slot.status = "ASSIGNED"
    schedule = PostSchedule(id=str(uuid4()), post_id=post.id, revision_id=revision.id, calendar_slot_id=body.calendar_slot_id, timezone=body.timezone, intended_local_at=local_text, resolved_utc_at=utc_value, status="ACTIVE", idempotency_key=body.idempotency_key)
    db.add(schedule)
    post.state = "SCHEDULED"
    add_outbox(db, "post.scheduled", schedule.id, f"schedule:{schedule.id}", {"schedule_id": schedule.id, "revision_id": revision.id}, utc_value)
    db.commit()
    db.refresh(schedule)
    return schedule_output(schedule)


@router.get("/schedules", response_model=list[ScheduleOutput])
def list_schedules(db: Session = Depends(get_db)):
    return [schedule_output(item) for item in db.scalars(select(PostSchedule).where(PostSchedule.workspace_id == BOOTSTRAP_WORKSPACE_ID).order_by(PostSchedule.resolved_utc_at)).all()]


@router.post("/schedules/{schedule_id}/publish-now", response_model=PublishActionOutput)
def publish_now(schedule_id: str, body: PublishNowRequest, db: Session = Depends(get_db)):
    schedule = db.get(PostSchedule, schedule_id)
    if not schedule or schedule.workspace_id != BOOTSTRAP_WORKSPACE_ID:
        raise HTTPException(404, "Schedule not found")
    if schedule.revision_id != body.revision_id or schedule.status not in {"ACTIVE", "REMINDER_DUE"}:
        raise HTTPException(409, "The scheduled exact revision is no longer actionable")
    try:
        action = create_publish_action(db, schedule, body.idempotency_key)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    db.commit()
    db.refresh(action)
    return publish_action_output(action)


@router.get("/publish-actions/{action_id}", response_model=PublishActionOutput)
def get_publish_action(action_id: str, db: Session = Depends(get_db)):
    action = db.get(PublishAction, action_id)
    if not action or action.workspace_id != BOOTSTRAP_WORKSPACE_ID:
        raise HTTPException(404, "Publish action not found")
    return publish_action_output(action)


@router.get("/publish-actions", response_model=list[PublishActionOutput])
def list_publish_actions(db: Session = Depends(get_db)):
    return [publish_action_output(item) for item in db.scalars(select(PublishAction).where(PublishAction.workspace_id == BOOTSTRAP_WORKSPACE_ID).order_by(PublishAction.created_at.desc())).all()]


@router.post("/publish-actions/{action_id}/confirm", response_model=PublishActionOutput)
def confirm_publish(action_id: str, body: PublishConfirmation, db: Session = Depends(get_db)):
    action = db.get(PublishAction, action_id)
    if not action or action.workspace_id != BOOTSTRAP_WORKSPACE_ID:
        raise HTTPException(404, "Publish action not found")
    if action.state == "PUBLISHED":
        if body.published_url and body.published_url != action.published_url:
            raise HTTPException(409, "Publication was already confirmed with different details")
        return publish_action_output(action)
    if action.state != "ACTION_REQUIRED":
        raise HTTPException(409, "Publication action is no longer confirmable")
    if body.published_url and not body.published_url.startswith(("https://", "http://")):
        raise HTTPException(422, "published_url must be an HTTP URL")
    action.state = "PUBLISHED"
    action.published_url = body.published_url
    action.published_at = body.published_at or datetime.now(UTC)
    schedule, post = db.get(PostSchedule, action.schedule_id), db.get(Post, action.post_id)
    schedule.status, post.state = "COMPLETED", "PUBLISHED"
    revision = db.get(PostRevision, action.revision_id)
    upsert_memory_status(db, revision, eligible=True, reason="PUBLISHED_REVISION")
    add_outbox(db, "post.published", post.id, f"published:{action.id}", {"post_id": post.id, "revision_id": action.revision_id, "publish_action_id": action.id})
    db.commit()
    db.refresh(action)
    return publish_action_output(action)


@router.post("/publish-actions/{action_id}/fail", response_model=PublishActionOutput)
def fail_publish(action_id: str, body: PublishFailure, db: Session = Depends(get_db)):
    action = db.get(PublishAction, action_id)
    if not action or action.workspace_id != BOOTSTRAP_WORKSPACE_ID:
        raise HTTPException(404, "Publish action not found")
    if action.state != "ACTION_REQUIRED":
        raise HTTPException(409, "Publication action is no longer active")
    action.state = "FAILED"
    action.failure_reason = body.reason
    schedule, post = db.get(PostSchedule, action.schedule_id), db.get(Post, action.post_id)
    schedule.status, post.state = "FAILED", "FAILED"
    add_outbox(db, "publish.failed", action.id, f"publish-failed:{action.id}", {"publish_action_id": action.id})
    db.commit()
    db.refresh(action)
    return publish_action_output(action)


@router.get("/feedback/preferences", response_model=list[PreferenceOutput])
def list_preferences(db: Session = Depends(get_db)):
    return [preference_output(item) for item in db.scalars(select(PreferenceRule).where(PreferenceRule.workspace_id == BOOTSTRAP_WORKSPACE_ID).order_by(PreferenceRule.category)).all()]


@router.patch("/feedback/preferences/{preference_id}", response_model=PreferenceOutput)
def update_preference(preference_id: str, body: PreferenceUpdate, db: Session = Depends(get_db)):
    item = db.get(PreferenceRule, preference_id)
    if not item or item.workspace_id != BOOTSTRAP_WORKSPACE_ID:
        raise HTTPException(404, "Preference not found")
    item.active = body.active
    item.version += 1
    item.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(item)
    return preference_output(item)


@router.post("/content-ideas", response_model=ContentIdeaOutput, status_code=201)
def create_content_idea(body: ContentIdeaCreate, db: Session = Depends(get_db)):
    voice = db.scalars(
        select(VoiceProfile)
        .where(VoiceProfile.workspace_id == BOOTSTRAP_WORKSPACE_ID)
        .order_by(VoiceProfile.version.desc())
        .limit(1)
    ).first()
    if not voice:
        raise HTTPException(409, "Configure a voice profile before creating an idea")
    pillar = next(
        (item for item in voice.content_pillars if item.casefold() == body.pillar.casefold()),
        None,
    )
    if not pillar:
        raise HTTPException(422, "Choose a pillar from the current voice profile")
    idea = ContentIdea(
        id=str(uuid4()),
        voice_profile_id=voice.id,
        taxonomy_version=voice.taxonomy_version,
        pillar=pillar,
        topic=body.topic,
        angle=body.angle,
        audience_intent=body.audience_intent,
        format="TEXT",
    )
    db.add(idea)
    db.flush()
    for item in body.evidence:
        db.add(
            SourceReference(
                id=str(uuid4()),
                content_idea_id=idea.id,
                statement=item.statement,
                source_url=item.source_url,
                freshness_date=item.freshness_date.isoformat() if item.freshness_date else None,
                source_type="USER_CONFIRMED",
            )
        )
    db.commit()
    db.refresh(idea)
    return content_idea_output(db, idea)


@router.get("/content-ideas/{idea_id}", response_model=ContentIdeaOutput)
def get_content_idea(idea_id: str, db: Session = Depends(get_db)):
    idea = db.get(ContentIdea, idea_id)
    if not idea or idea.workspace_id != BOOTSTRAP_WORKSPACE_ID:
        raise HTTPException(404, "Content idea not found")
    return content_idea_output(db, idea)


@router.post(
    "/content-ideas/{idea_id}/primary-draft",
    response_model=PrimaryDraftOutput,
    status_code=201,
)
def create_primary_draft(
    idea_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    idea = db.get(ContentIdea, idea_id)
    if not idea or idea.workspace_id != BOOTSTRAP_WORKSPACE_ID:
        raise HTTPException(404, "Content idea not found")
    if db.scalar(select(Post.id).where(Post.content_idea_id == idea.id)):
        raise HTTPException(409, "This idea already has its one primary draft")
    voice = db.get(VoiceProfile, idea.voice_profile_id)
    evidence = db.scalars(
        select(SourceReference)
        .where(SourceReference.content_idea_id == idea.id)
        .order_by(SourceReference.created_at, SourceReference.id)
    ).all()
    memory_references = retrieve_memory(
        db,
        query="\n".join((idea.pillar, idea.topic, idea.angle, idea.audience_intent)),
        taxonomy_version=idea.taxonomy_version,
    )
    generated, generation = generate_content_candidate(
        db, settings, idea, voice, evidence, memory_references=memory_references
    )
    allowed_context = "\n".join(
        (
            voice.domain,
            voice.target_audience,
            idea.pillar,
            idea.topic,
            idea.angle,
            idea.audience_intent,
        )
    )

    post = Post(id=str(uuid4()), content_idea_id=idea.id, state="DRAFT")
    db.add(post)
    db.flush()
    content = "\n\n".join((generated["hook"], generated["body"], generated["cta"]))
    revision = PostRevision(
        id=str(uuid4()),
        post_id=post.id,
        revision_number=1,
        hook=generated["hook"],
        body=generated["body"],
        cta=generated["cta"],
        content=content,
        generation_provider=generation["provider"],
        generation_model=generation["model"],
        generation_mode=generation["mode"],
        generation_warning=generation["warning"],
        prompt_version="primary-draft@1",
        taxonomy_version=idea.taxonomy_version,
        retrieved_revision_ids=[item["revision_id"] for item in memory_references],
    )
    db.add(revision)
    db.flush()
    record_retrievals(db, revision, memory_references)
    for claim in generated["claims"]:
        source_ids = [
            evidence[index - 1].id
            for index in claim.get("evidence_indices", [])
            if 1 <= index <= len(evidence)
        ]
        db.add(
            ClaimAssessment(
                id=str(uuid4()),
                post_revision_id=revision.id,
                claim_text=claim["text"],
                kind=claim["kind"],
                source_reference_ids=source_ids,
            )
        )
    persist_revision_checks(
        db,
        revision,
        generated["claims"],
        allowed_context,
        evidence,
        voice.prohibited_phrases,
        memory_references,
    )
    db.commit()
    db.refresh(post)
    db.refresh(revision)
    return primary_draft_output(db, post, revision)


@router.get("/posts/{post_id}", response_model=PrimaryDraftOutput)
def get_post(post_id: str, db: Session = Depends(get_db)):
    post = db.get(Post, post_id)
    if not post or post.workspace_id != BOOTSTRAP_WORKSPACE_ID:
        raise HTTPException(404, "Post not found")
    revision = current_revision(db, post)
    return primary_draft_output(db, post, revision)


@router.post("/posts/{post_id}/submit-review", response_model=PrimaryDraftOutput)
def submit_post_review(
    post_id: str,
    body: ReviewSubmissionRequest,
    db: Session = Depends(get_db),
):
    post = db.get(Post, post_id)
    if not post or post.workspace_id != BOOTSTRAP_WORKSPACE_ID:
        raise HTTPException(404, "Post not found")
    revision = require_current_revision(db, post, body.revision_id)
    if post.state not in {"DRAFT", "CHANGES_REQUESTED"}:
        raise HTTPException(409, "Only a draft or changes-requested revision can enter review")
    if db.scalar(
        select(Review.id).where(Review.revision_id == revision.id, Review.action == "SUBMIT")
    ):
        raise HTTPException(409, "This exact revision was already submitted")
    ensure_revision_checks(db, post, revision)
    db.add(
        Review(
            id=str(uuid4()),
            post_id=post.id,
            revision_id=revision.id,
            action="SUBMIT",
            claims_confirmed=False,
        )
    )
    post.state = "IN_REVIEW"
    db.commit()
    db.refresh(post)
    return primary_draft_output(db, post, revision)


@router.post("/posts/{post_id}/reviews", response_model=PrimaryDraftOutput)
def decide_post_review(
    post_id: str,
    body: ReviewDecisionRequest,
    db: Session = Depends(get_db),
):
    post = db.get(Post, post_id)
    if not post or post.workspace_id != BOOTSTRAP_WORKSPACE_ID:
        raise HTTPException(404, "Post not found")
    revision = require_current_revision(db, post, body.revision_id)
    if post.state != "IN_REVIEW":
        raise HTTPException(409, "The current revision must be in review")
    if db.scalar(
        select(Review.id).where(
            Review.revision_id == revision.id, Review.action == body.action
        )
    ):
        raise HTTPException(409, "This decision was already recorded for the revision")
    if body.action == "APPROVE":
        if not body.claims_confirmed:
            raise HTTPException(422, "Confirm the exact revision and its claims before approval")
        ensure_revision_checks(db, post, revision)
        blocking_failure = db.scalar(
            select(RevisionCheck.id).where(
                RevisionCheck.post_revision_id == revision.id,
                RevisionCheck.severity == "BLOCKING",
                RevisionCheck.passed.is_(False),
            )
        )
        if blocking_failure:
            raise HTTPException(409, "Resolve blocking checks before approval")
        post.state = "APPROVED"
        upsert_memory_status(db, revision, eligible=True, reason="EXACT_APPROVAL_VALID")
        add_outbox(db, "post.approved", post.id, f"approved:{revision.id}", {"post_id": post.id, "revision_id": revision.id})
    elif body.action == "REJECT":
        if not body.reason:
            raise HTTPException(422, "A rejection reason is required")
        post.state = "REJECTED"
        upsert_memory_status(db, revision, eligible=False, reason="REJECTED")
    else:
        if not body.reason or not body.categories:
            raise HTTPException(422, "A reason and at least one feedback category are required")
        post.state = "CHANGES_REQUESTED"
    db.add(
        Review(
            id=str(uuid4()),
            post_id=post.id,
            revision_id=revision.id,
            action=body.action,
            reason=body.reason,
            categories=list(body.categories),
            claims_confirmed=body.claims_confirmed,
        )
    )
    if body.action in {"REQUEST_CHANGES", "REJECT"}:
        categories = list(body.categories) if body.categories else ["REJECT"]
        record_feedback(db, post.id, revision.id, categories, body.reason or body.action)
        synthesize_preferences(db)
    db.commit()
    db.refresh(post)
    return primary_draft_output(db, post, revision)


@router.post("/posts/{post_id}/edits", response_model=PrimaryDraftOutput, status_code=201)
def edit_post_revision(
    post_id: str,
    body: PostEditRequest,
    db: Session = Depends(get_db),
):
    post = db.get(Post, post_id)
    if not post or post.workspace_id != BOOTSTRAP_WORKSPACE_ID:
        raise HTTPException(404, "Post not found")
    previous = require_current_revision(db, post, body.revision_id)
    if post.state == "REJECTED":
        raise HTTPException(409, "A rejected post is terminal")
    was_published = post.state == "PUBLISHED"
    upsert_memory_status(db, previous, eligible=was_published, reason="PUBLISHED_REVISION" if was_published else "SUPERSEDED_UNPUBLISHED")
    values = {"hook": body.hook, "body": body.body, "cta": body.cta}
    operations = [
        {"field": field, "before": getattr(previous, field), "after": value}
        for field, value in values.items()
        if getattr(previous, field) != value
    ]
    if not operations:
        raise HTTPException(422, "Change at least one field before saving a new revision")
    active_schedules = db.scalars(select(PostSchedule).where(PostSchedule.post_id == post.id, PostSchedule.status.in_(["ACTIVE", "REMINDER_DUE"]))).all()
    for schedule in active_schedules:
        schedule.status = "CANCELLED"
        action = db.scalar(select(PublishAction).where(PublishAction.schedule_id == schedule.id, PublishAction.state == "ACTION_REQUIRED"))
        if action:
            action.state = "FAILED"
        if schedule.calendar_slot_id:
            slot = db.get(CalendarSlot, schedule.calendar_slot_id)
            if slot:
                slot.status = "PLANNED"
        add_outbox(db, "schedule.cancelled", schedule.id, f"schedule-cancelled:{schedule.id}", {"schedule_id": schedule.id, "revision_id": previous.id})
    idea, voice, evidence, allowed_context = revision_context(db, post)
    claims = user_edit_claims([body.hook, body.body, body.cta], [item.statement for item in evidence])
    memory_references = retrieve_memory(
        db,
        query="\n\n".join((body.hook, body.body, body.cta)),
        taxonomy_version=idea.taxonomy_version,
        exclude_post_id=post.id,
    )
    revision = PostRevision(
        id=str(uuid4()),
        post_id=post.id,
        revision_number=previous.revision_number + 1,
        hook=body.hook,
        body=body.body,
        cta=body.cta,
        content="\n\n".join((body.hook, body.body, body.cta)),
        generation_provider="human",
        generation_model="local-owner",
        generation_mode="human_edit",
        generation_warning=None,
        prompt_version="human-edit@1",
        taxonomy_version=idea.taxonomy_version,
        retrieved_revision_ids=[item["revision_id"] for item in memory_references],
    )
    db.add(revision)
    db.flush()
    record_retrievals(db, revision, memory_references)
    for claim in claims:
        source_ids = [
            evidence[index - 1].id
            for index in claim["evidence_indices"]
            if 1 <= index <= len(evidence)
        ]
        db.add(
            ClaimAssessment(
                id=str(uuid4()),
                post_revision_id=revision.id,
                claim_text=claim["text"],
                kind=claim["kind"],
                source_reference_ids=source_ids,
            )
        )
    persist_revision_checks(
        db,
        revision,
        claims,
        allowed_context,
        evidence,
        voice.prohibited_phrases,
        memory_references,
    )
    db.add(
        EditDelta(
            id=str(uuid4()),
            post_id=post.id,
            from_revision_id=previous.id,
            to_revision_id=revision.id,
            operations=operations,
        )
    )
    db.add(
        Review(
            id=str(uuid4()),
            post_id=post.id,
            revision_id=revision.id,
            action="EDIT",
            claims_confirmed=True,
        )
    )
    record_feedback(db, post.id, revision.id, [f"EDIT_{item['field'].upper()}" for item in operations], "Human edited the approved or draft revision")
    synthesize_preferences(db)
    post.state = "DRAFT"
    db.commit()
    db.refresh(post)
    db.refresh(revision)
    return primary_draft_output(db, post, revision)


@router.post(
    "/posts/{post_id}/regenerations", response_model=PrimaryDraftOutput, status_code=201
)
def regenerate_post_revision(
    post_id: str,
    body: RegenerationRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    post = db.get(Post, post_id)
    if not post or post.workspace_id != BOOTSTRAP_WORKSPACE_ID:
        raise HTTPException(404, "Post not found")
    previous = require_current_revision(db, post, body.revision_id)
    if post.state != "CHANGES_REQUESTED":
        raise HTTPException(409, "Request changes on the current revision before regenerating")
    feedback = db.scalars(
        select(Review)
        .where(
            Review.revision_id == previous.id,
            Review.action == "REQUEST_CHANGES",
        )
        .order_by(Review.created_at.desc())
        .limit(1)
    ).first()
    if not feedback:
        raise HTTPException(409, "Structured regeneration feedback is missing")
    idea, voice, evidence, allowed_context = revision_context(db, post)
    upsert_memory_status(db, previous, eligible=False, reason="SUPERSEDED_UNPUBLISHED")
    memory_references = retrieve_memory(
        db,
        query="\n".join((idea.pillar, idea.topic, idea.angle, idea.audience_intent)),
        taxonomy_version=idea.taxonomy_version,
        exclude_post_id=post.id,
    )
    generated, generation = generate_content_candidate(
        db,
        settings,
        idea,
        voice,
        evidence,
        feedback={"categories": feedback.categories, "instruction": feedback.reason},
        previous_revision=previous,
        memory_references=memory_references,
    )
    revision = PostRevision(
        id=str(uuid4()),
        post_id=post.id,
        revision_number=previous.revision_number + 1,
        hook=generated["hook"],
        body=generated["body"],
        cta=generated["cta"],
        content="\n\n".join((generated["hook"], generated["body"], generated["cta"])),
        generation_provider=generation["provider"],
        generation_model=generation["model"],
        generation_mode=generation["mode"],
        generation_warning=generation["warning"],
        prompt_version="regeneration@1",
        taxonomy_version=idea.taxonomy_version,
        retrieved_revision_ids=[item["revision_id"] for item in memory_references],
    )
    db.add(revision)
    db.flush()
    record_retrievals(db, revision, memory_references)
    for claim in generated["claims"]:
        source_ids = [
            evidence[index - 1].id
            for index in claim.get("evidence_indices", [])
            if 1 <= index <= len(evidence)
        ]
        db.add(
            ClaimAssessment(
                id=str(uuid4()),
                post_revision_id=revision.id,
                claim_text=claim["text"],
                kind=claim["kind"],
                source_reference_ids=source_ids,
            )
        )
    persist_revision_checks(
        db,
        revision,
        generated["claims"],
        allowed_context,
        evidence,
        voice.prohibited_phrases,
        memory_references,
    )
    operations = [
        {"field": field, "before": getattr(previous, field), "after": generated[field]}
        for field in ("hook", "body", "cta")
        if getattr(previous, field) != generated[field]
    ]
    db.add(
        EditDelta(
            id=str(uuid4()),
            post_id=post.id,
            from_revision_id=previous.id,
            to_revision_id=revision.id,
            operations=operations,
        )
    )
    db.add(
        Review(
            id=str(uuid4()),
            post_id=post.id,
            revision_id=revision.id,
            action="REGENERATE",
            reason=feedback.reason,
            categories=feedback.categories,
            claims_confirmed=False,
        )
    )
    post.state = "DRAFT"
    db.commit()
    db.refresh(post)
    db.refresh(revision)
    return primary_draft_output(db, post, revision)


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
