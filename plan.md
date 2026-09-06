# Liproser Product Plan

**Status:** reconciled implementation baseline

**Authoritative sequence:** [ROADMAP.md](ROADMAP.md)

**Technical design:** [architecture.md](architecture.md) · **Runtime agents:** [docs/ai-agents.md](docs/ai-agents.md)

## Product thesis

Liproser begins as the founder's private LinkedIn operating system, not a generalized SaaS. It improves a user-confirmed profile, turns expertise into domain-tagged original posts, preserves human approval, captures outcomes, and learns from the user's own approved/published history. Only workflows proven through at least eight weeks and 24 planned posts are candidates for productization.

Principles:

1. Useful without LinkedIn API approval: manual/PDF/CSV paths are permanent capabilities.
2. Human authority: generation, scores, and predictions are proposals; approval and publication are explicit user actions.
3. Truth before engagement: preserve evidence, distinguish facts/opinions, and never invent professional claims.
4. First-party learning: prior eligible user posts provide voice and pattern memory; public research provides evidence only.
5. Originality and diversity: detect repetition across hooks, structures, pillars, formats, and prior revisions.
6. Explainability: profile scores, claims, recommendations, and predictions expose reasons, confidence, and limitations.
7. Lean sequencing: infrastructure appears only when a release needs it.

## Initial user and jobs

The initial user is one professional managing one LinkedIn presence. They need to understand what weakens their profile, approve exact evidence-preserving improvements, produce consistent posts in their own voice, review every revision, remember what they have already said, publish manually, and later compare performance with their own baseline.

The personal release excludes public signup, teams, billing, cross-customer intelligence, third-party post ingestion, scraping, browser automation, and unofficial LinkedIn APIs.

## Release outcomes

| Release | User outcome | Key dependency | Exit evidence |
|---|---|---|---|
| `v0.1` | Import manual/PDF profile, confirm extraction, score, decide on rewrites, re-score | Next.js, FastAPI, PostgreSQL, private filesystem, configured model | Complete journey; fact/schema/budget gates |
| `v0.2` | Onboard voice, create/review one tagged draft, reuse eligible own history | pgvector and evidence ledger | Approval integrity; traceable retrieval; originality |
| `v0.3` | Plan a calendar, schedule reminders, learn from edits | Redis, Arq, worker/outbox | No duplicate reminders; reversible preferences |
| `v0.4` | Import metrics and receive calibrated prediction explanations | CSV/manual analytics, versioned feature pipeline | Honest cold start; measured calibration |
| `v1` | Operate the complete personal workflow reliably | Eight weeks and 24 planned posts | Baseline comparison and workflow evidence |
| `SaaS MVP` | Onboard design partners without founder intervention | Productization/security/operations | Activation, retention, deletion, support, economics |

## Requirements by capability

### Profile optimization (`v0.1`)

- Accept Headline, About, Experience, Skills, and Featured through manual input or PDF.
- Retain the private raw PDF until explicit deletion; expose source status, provenance, hash, download, and delete controls.
- Require user confirmation when extraction is uncertain or material.
- Score with an immutable role/domain rubric covering clarity, hook, search relevance, specificity, evidence, and readability.
- Show confidence and criterion-level reasons, plus exact before/after suggestions.
- Mark preserved, removed, and proposed claims. Numeric or biographical additions require user-supplied evidence.
- Allow accept, edit-and-accept, and reject; preserve audit history and re-score using the same rubric version.

### Content and review (`v0.2`)

- Onboard domain, audience, pillars, tone, prohibited phrases, and three-to-five user-owned samples.
- Generate one idea and one primary draft; alternatives change only a requested dimension.
- Support text, image concept, carousel outline, and poll metadata; visual assets are not part of this release.
- Maintain a claim/evidence ledger with freshness dates and source conflict states.
- Show a LinkedIn-style preview with readability, accessibility, originality, and diversity feedback.
- Enforce immutable revisions and `DRAFT → IN_REVIEW → CHANGES_REQUESTED/REJECTED/APPROVED`.
- Tag every revision with canonical domain/pillar/topic/audience/format/hook data; unknown tags require user confirmation.

### First-party pattern learning (`v0.2+`)

- Analyze only the user's eligible tagged revisions, never third-party post corpora.
- Keep published immutable revisions eligible even after newer drafts exist.
- Keep an approved unpublished revision eligible only while that exact approval remains valid.
- Exclude rejected, deleted, disabled, and superseded-unpublished revisions.
- Record reference revision IDs, taxonomy/embedding versions, and similarity scores on every generated draft.
- Surface structural patterns and repetition risks without encouraging close reuse of prior prose.

### Calendar, reminders, and feedback (`v0.3`)

- Balance cadence across pillars, formats, hooks, narratives, CTAs, time zone, and quiet days.
- Schedule only the exact approved revision. Editing invalidates approval and schedule eligibility.
- Use copy-formatted-post and reminder flows; the user confirms publication and may record the URL.
- Capture edit deltas, regeneration feedback, and rejection reasons as structured signals.
- Promote durable voice preferences only after repeated evidence or explicit confirmation; make versions inspectable, reversible, and resettable.

### Analytics and prediction (`v0.4`)

- Import metrics manually or from CSV with source and observation window; deduplicate snapshots.
- Compare pillars, formats, times, and trends with the user's pre-product/historical baseline.
- Capture experiment tags and vary one element by default to support interpretation.
- Start with domain priors, blend as personal sample size grows, and expose the data basis.
- Show a calibrated bucket/interval, top three contributing factors, one feasible edit, and limitations.
- Track calibration and prediction error over time; never promise reach or causality.

### Official LinkedIn capabilities (parallel track)

Login cannot promise a full profile, post history, or analytics. `v0.1` uses manual/PDF input. OIDC, if added, is limited identity linking. Automatic publishing or analytics sync is enabled only for approved/granted capabilities behind runtime flags. Full About, Experience, Skills, and Featured remain user-supplied unless an official capability explicitly provides them. Missing access never triggers scraping or browser automation.

## User experience

Navigation grows with releases: Setup and Profile in `v0.1`; Create, Review, and Library in `v0.2`; Calendar in `v0.3`; Analytics in `v0.4`. Library is one view for eligible own posts, voice samples, and approved evidence. Personal settings expose provider readiness, usage budget, local data controls, and optional LinkedIn capabilities. Billing controls appear only in SaaS mode.

Critical journeys:

1. Upload PDF → inspect extraction confidence → correct/confirm → analyze → decide section suggestions → re-score → optionally delete source.
2. Configure voice/taxonomy → approve idea → generate one evidence-aware draft → review/edit/regenerate/reject/approve.
3. Approve exact revision → schedule → receive idempotent reminder → copy/publish → confirm URL/time.
4. Import metric snapshot → validate observation window → compare baseline → view prediction basis and calibration.
5. Export or delete data → pending work is cancelled → late results cannot persist.

## AI providers and cost control

No provider is active by default. First-run setup checks one selected Ollama, OpenAI, or Claude model against the shared schema and records provider/model selection without secrets. Secrets stay in the ignored environment; CI uses a fake provider. OpenAI uses Responses structured output with `store=false`; Claude uses Messages with environment authentication; Ollama is optional and must pass the same contract.

The personal budget is USD 10 across OpenAI and Claude per UTC calendar month. Before dispatch, a transaction reserves estimated cost; an insufficient unreserved balance rejects the call. Usage reconciles after success/failure, warning begins at 80%, and API responses show actual/reserved/remaining/reset time. In-flight calls and price changes can cause a small overshoot; provider-side caps remain necessary. Ollama records tokens/latency at zero external API cost. Paid search has a separate, initially disabled budget.

## Success measures and gates

Personal validation measures profile rubric gain, protected-fact failures, approval-without-edit rate, median time from idea to approval, rejection/regeneration reasons, content-diversity drift, monthly cost and cost per approved post, post cadence, prediction calibration, and engagement-rate lift versus the user's own baseline.

Before `SaaS MVP`:

- At least eight weeks and 24 planned posts complete in personal use.
- Zero approval bypasses, cross-workspace retrievals, secret leaks, invented critical profile facts, and duplicate publications.
- At least five target-user interviews and consented design-partner fixtures cover varied domains and input quality.
- Design partners activate without direct database or prompt intervention; four-week retention and support burden are measured.
- Export/deletion, threat model, privacy/security review, model-provider terms, and applicable LinkedIn/legal gates pass.
- Unit economics support a pricing experiment.

Tier hypotheses—not commitments—are Free profile audit, Creator workflow, and later Team/Agency. Pricing follows measured value and cost.

## Risks and treatments

| Risk | Treatment |
|---|---|
| LinkedIn approval unavailable/changes | Complete manual paths; parallel capability flags; official interfaces only |
| Fabricated or stale claims | Confirmation, claim ledger, source freshness, blocking checks, frozen fixtures |
| Repetitive/homogeneous content | First-party similarity, diversity budgets, one bounded alternative |
| Cold-start prediction | Label domain prior; widen uncertainty; blend only after sufficient history |
| Founder overfitting | Immutable shared contracts, frozen multi-domain fixtures, design partners before SaaS |
| Cost overrun | Transactional reservations, reconciliation, warning/hard stop, provider-side caps |
| Private data in public Git/logs | Ignored roots, staged secret scan, redaction, synthetic fixtures only |
| Local personal mode exposed publicly | Loopback bind and startup refusal for public/production configuration |
| Provider lock-in | Typed gateway, shared schemas, versioned pricing, fake contract adapter |

## External launch gates

- Legal review of LinkedIn and content/data flows.
- LinkedIn developer approval for each automated capability actually shipped.
- Model-provider data terms and production privacy/security review.
- SaaS identity, storage, retention, incident response, and deletion validation.

References: [LinkedIn OIDC](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2), [LinkedIn API access](https://learn.microsoft.com/en-us/linkedin/marketing/increasing-access), [LinkedIn API Terms](https://www.linkedin.com/legal/l/api-terms-of-use), and [OpenAI Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create).
