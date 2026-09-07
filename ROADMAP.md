# Liproser Stepwise Implementation Roadmap

This file is the authoritative implementation sequence. Personal releases are sequential; the LinkedIn integration track is parallel and never blocks them.

**Related:** [README](README.md) · [Product plan](plan.md) · [Architecture](architecture.md) · [Repository rules](AGENTS.md) · [Runtime agents](docs/ai-agents.md)

## Delivery discipline

For each vertical slice: define the user outcome and non-goals; add deterministic tests/synthetic fixtures; implement the smallest end-to-end behavior; run targeted and repository checks; inspect staged changes for private data, secrets, approval bypasses, and scope creep; commit and push only after checks pass; verify remote CI; then record personal-use evidence privately.

## Status vocabulary and current checkpoint

- **Implemented** means the slice exists end to end and its automated, migration, browser, repository, and remote-CI checks passed.
- **Personally validated** means the founder has used it with real private data and recorded the release evidence outside Git.
- **Product validated** means the eight-week, 24-planned-post `v1` gate and later design-partner gates passed.

Current checkpoint: Foundation and `v0.1`, `v0.2A`, `v0.2B`, `v0.2C`, and `v0.2D` are implemented. Personal validation is still accumulating. `v0.3` is next; later releases remain unstarted.

## Foundation — specification and runnable shell

The documentation reconciliation, environment template, ignored private-data paths, synthetic fixtures, repository verifier, and read-only CI must pass first. Then create the Next.js web shell, FastAPI application API, migration tooling, PostgreSQL, filesystem storage adapter, and one bootstrap owner/workspace.

Acceptance:

- One documented command starts web, API, and PostgreSQL locally.
- `PERSONAL_MODE=true` binds only to loopback and is rejected with production mode or a public bind.
- The private storage root is ignored; raw PDFs are downloadable/deletable and retained until explicit deletion.
- No public signup, billing, worker, Redis, pgvector, or object-storage service is required.

## `v0.1` — profile optimizer

Deliver in order:

1. First-run setup and a provider gateway for Ollama, OpenAI, Claude, and a fake CI provider. No provider is active until configured and checked. Hosted keys may be environment-based or session-only in personal mode; they are never persisted by the application.
2. Transactional hosted-cost reservation and reconciliation across OpenAI plus Claude: USD 10 per UTC calendar month, warning at 80%, hard pre-dispatch rejection when unreserved balance is insufficient. Ollama records usage at zero external API cost.
3. Manual and PDF profile imports for Headline, About, Experience, Skills, and Featured. Store source provenance, hash, extraction state/confidence, and retained-file location.
4. Confirmation/correction of uncertain extraction; safe handling of encrypted, malformed, malicious, and oversized PDFs.
5. Immutable rubric scoring; Profile Analyst before/after suggestions with preserved/removed/proposed claim classification.
6. Human accept, edit-and-accept, or reject decisions; re-score with the same rubric version.

`v0.1` application API:

| Method and route | Purpose |
|---|---|
| `GET /v1/setup` | Provider/configuration readiness without secrets |
| `POST /v1/setup/provider-check` | Test selected provider/model contract |
| `POST /v1/profile-imports` | Create `MANUAL` or `PDF` import |
| `GET /v1/profile-imports/{id}` | Read extraction state and confidence |
| `POST /v1/profile-imports/{id}/confirm` | Confirm or correct sections |
| `DELETE /v1/profile-imports/{id}/source` | Explicitly delete retained raw source |
| `POST /v1/profiles/{id}/analyses` | Score confirmed sections |
| `POST /v1/profile-suggestions/{id}/decisions` | Accept, edit-and-accept, or reject |
| `POST /v1/profiles/{id}/rescore` | Compare using the same rubric |
| `GET /v1/usage/ai-budget` | Actual, reserved, remaining, reset time |

Release gate:

- Manual and PDF journeys pass end to end, including uncertain extraction and source deletion.
- Critical frozen fixtures have 100% schema validity and protected-fact preservation, with zero invented employers, dates, credentials, achievements, or numbers.
- Concurrent reservations, warning, rejection, reconciliation, failure, and UTC reset tests pass.
- All adapters pass one shared structured-output contract; CI uses the fake provider.

## `v0.2` — content, review, and first-party memory

Add voice onboarding, controlled domain/pillar/topic taxonomy, one idea and one primary draft, evidence/claim ledger, LinkedIn-style preview, readability/accessibility/originality checks, and the human review state path:

Deliver as separate slices:

1. `v0.2A` — immutable voice onboarding with domain, audience, pillars, tones, prohibited phrases, three-to-five user-owned samples, and a deterministic taxonomy snapshot.
2. `v0.2B` — one tagged idea and one primary evidence-aware draft; no alternatives until requested.
3. `v0.2C` — immutable revisions, preview/checks, and the human review state machine.
4. `v0.2D` — eligible first-party retrieval with pgvector, recorded retrieval provenance, originality, and diversity checks.

`DRAFT → IN_REVIEW → CHANGES_REQUESTED | REJECTED | APPROVED`

Add pgvector only here, after deterministic metadata filters. Eligible memory is limited to the user's published immutable revisions and still-valid exact approved unpublished revisions. Exclude rejected, deleted, disabled, and superseded-unpublished revisions. Every draft records retrieved revision IDs, taxonomy/embedding versions, and similarity scores. Public sources are evidence, never voice examples.

Release gate: property tests prove only a human action can approve an exact revision; editing invalidates approval; cross-workspace/ineligible retrieval is zero; every factual claim is classified; first-party similarity and diversity checks pass.

## `v0.3` — calendar, reminders, and feedback learning

Add balanced calendar planning, cadence/time zone/quiet days, approved-revision scheduling, copy-formatted-post and reminder flow, explicit user publication confirmation, edit deltas, reason taxonomy, repeated-signal preference learning, and immutable voice-profile versions.

Add Redis, Arq, and a worker only at this release. Use outbox delivery, idempotency keys, retries with dead-letter handling, and timezone-aware scheduling.

State extension:

`APPROVED → SCHEDULED → PUBLISH_ACTION_REQUIRED → PUBLISHED | FAILED`

Release gate: no approval bypass or duplicate reminder; late/deleted-workspace jobs cannot persist; preferences remain inspectable/reversible.

## `v0.4` — analytics and explainable prediction

Add manual entry and CSV import for observation-windowed impressions, reactions, comments, reposts, follower growth, and link clicks when available. Capture a pre-product baseline and experiment tags. Begin prediction with versioned structured features and honest domain priors, then blend toward personalized history. Show calibrated interval/bucket, basis, top three factors, and one feasible edit—never a guarantee.

Release gate: imports deduplicate; observation windows match; cold-start/personalized states are explicit; controlled fixtures test calibration and explanation fidelity.

## `v1` — validated personal operating system

The personal product reaches `v1` only after at least eight weeks of use and 24 planned posts. Evaluate approval-without-edit rate, time to approved post, profile rubric gain, content diversity, budget/cost per approved post, prediction calibration, and engagement lift versus the user's baseline. Record failures and manual workarounds before productization.

## Parallel LinkedIn integration track — capability gated

This work may proceed alongside personal releases but cannot be on their critical path:

1. Apply for applicable LinkedIn developer products/scopes and complete legal/security review.
2. Add optional OIDC/PKCE identity linking; show that it supplies limited identity, not full profile ingestion.
3. Add only capabilities actually approved and granted—for example official publishing or analytics sync—behind verified runtime capability flags.
4. Full About, Experience, Skills, and Featured remain user supplied unless an official capability explicitly provides them.

Revocation, encrypted tokens, selective storage/deletion, idempotency, and official fixtures are mandatory. Missing access always falls back to manual/PDF/CSV workflows, never scraping or browser automation.

## `SaaS MVP` — productization after validation

First remove founder-specific assumptions and validate with at least five interviews and consented design partners. Then add managed OIDC, assessed tenant isolation, public onboarding, S3-compatible storage, managed services, backups, deletion manifests, rate limits, support/admin recovery, privacy/terms, SLOs, and security review. Billing is a later experiment with Free audit, Creator, and Team/Agency hypotheses; the personal USD 10 AI cap is not subscription pricing.

The SaaS release requires activation, four-week retention, support-load, deletion, security, and unit-economics gates from [plan.md](plan.md).

## Explicitly excluded

- Third-party post ingestion or competitive-post corpora.
- LinkedIn scraping, browser/DOM automation, unofficial APIs, and autonomous engagement.
- Autonomous approval or publishing.
- Cross-customer training without separate explicit consent.
- Fine-tuning before `v1` evaluation and governance requirements pass.
