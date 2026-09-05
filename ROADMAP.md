# Liproser Stepwise Implementation Roadmap

**Rule:** one vertical slice at a time. A step starts only when the previous step's automated checks and human acceptance gate pass.

**Related documents:** [README](README.md) · [Product plan](plan.md) · [Architecture](architecture.md) · [Agent rules](AGENTS.md)

## Delivery discipline

For every step:

1. Open or update a small issue/spec with the user-visible outcome and explicit non-goals.
2. Add or update tests/evaluation fixtures before or with the implementation.
3. Implement the smallest end-to-end path behind a feature flag when incomplete.
4. Run targeted tests, the full available suite, and `scripts/verify-repository.ps1`.
5. Review the diff for secrets, private profile content, migrations, approval bypasses, and scope creep.
6. Commit and push only after checks pass. Never commit `.env`, profile exports, post archives, metrics exports, provider keys, or OAuth tokens.
7. Record real personal use in the private `validation_journal` once that feature exists.

## Stage 0 — Foundation

### 0.1 Repository baseline

**Deliver:** README, roadmap, uppercase `AGENTS.md`, environment template, ignored local environment, synthetic evaluation fixtures, verification script, and read-only CI.

**Acceptance**

- Foundation script passes locally and in GitHub Actions.
- `.env` and private-data directories are ignored and untracked.
- Repository has no license by explicit owner choice.
- Documentation consistently prohibits scraping and autonomous publishing.

### 0.2 Decision records

**Deliver:** ADRs for the modular monolith, PostgreSQL/pgvector, immutable revisions, provider gateway, personal-first runtime, and compliant LinkedIn capability ladder.

**Acceptance**

- Each ADR records context, decision, consequences, and reversal trigger.
- No ADR requires Redis, object storage, or a managed cloud before the feature that needs it.

## Stage 1 — Runnable personal shell

### 1.1 Monorepo and local runtime

**Deliver:** Next.js web shell, FastAPI health/config API, typed OpenAPI client generation, PostgreSQL migration tooling, and one bootstrap owner/workspace.

**Do not build:** public signup, billing, LinkedIn login, workers, content generation, analytics, or deployment automation.

**Acceptance**

- One documented command starts web, API, and PostgreSQL locally.
- Personal mode binds to loopback and refuses production configuration.
- Health checks confirm database connectivity and migration version.
- Unit, API, and smoke tests run in CI.

### 1.2 Provider gateway and budget ledger

**Deliver:** a typed `ModelGateway`, adapters for Ollama/OpenAI/Claude, fake provider for tests, task-based model selection, usage records, and monthly budget enforcement.

**Behavior**

- Ollama is default and needs no API key.
- Selecting OpenAI or Claude without the required key/model fails at startup with a safe configuration error.
- Every paid request reserves estimated cost transactionally, records actual usage/cost, then releases the difference.
- At 80% of USD 10, show a warning. At 100%, reject new paid calls before sending them. In-flight calls may cause a small documented overshoot.
- Provider prices are versioned configuration with effective dates, never hard-coded as timeless constants.

**Acceptance**

- Contract tests run the same structured-output fixture across fake adapters.
- Budget race tests prove concurrent requests cannot intentionally exceed the available reservation.
- Keys and prompt bodies never appear in logs or exceptions.
- Ollama unavailability has a clear setup/retry message.

## Stage 2 — First vertical slice: profile optimization

### 2.1 Manual profile entry

**Deliver:** forms and APIs for Headline, About, Experience, Skills, Featured, target role/domain, and confirmed facts.

**Do not build:** PDF parsing, LinkedIn login, post import, or profile analytics.

**Acceptance**

- Draft/save/confirm works for the bootstrap workspace.
- Every record is workspace-scoped and exportable.
- User-entered content is excluded from telemetry and logs.

### 2.2 Deterministic rubric

**Deliver:** immutable rubric v1, per-section scoring, explanations, completeness checks, and baseline history without an LLM dependency.

**Acceptance**

- Frozen fixtures always produce the same scores.
- Missing sections lower completeness without inventing content.
- Re-scoring against the same rubric is comparable.

### 2.3 Profile Analyst

**Deliver:** structured suggestions with before/after text, rationale, preserved/removed facts, proposed claims, confidence, and safe fallback.

**Acceptance**

- All critical fact-preservation fixtures pass.
- Numeric achievements not present in confirmed facts are flagged as questions/placeholders.
- Invalid provider output gets one repair attempt and never persists partially.

### 2.4 Human decisions and re-score

**Deliver:** accept, edit-and-accept, reject, immutable suggestion decisions, audit records, and score comparison.

**Acceptance**

- The user can complete the entire first vertical slice without database edits.
- Accepted wording and user edits remain distinguishable.
- At least three real founder sessions are recorded before expanding scope.

## Stage 3 — User-authorized profile import

### 3.1 PDF and data-export import

**Deliver:** private upload, malware/type/size checks, text extraction, confidence values, source provenance, confirmation UI, expiry, export, and deletion.

**Acceptance**

- Low-confidence extraction requires confirmation.
- A malicious, oversized, encrypted, or malformed file fails safely.
- Raw imports never enter Git and can be fully deleted.

### 3.2 LinkedIn identity connection

**Deliver:** OIDC/PKCE account linking and a capability screen showing exactly what data is and is not available.

**Important:** identity linking does not claim to import the full profile.

**Acceptance**

- The user completes login on LinkedIn's page; Liproser never handles their password.
- State, PKCE, redirect, subject binding, revocation, and token encryption tests pass.
- Missing API capabilities direct the user to PDF/data-export import.

### 3.3 Official profile/post/analytics import — gated

**Start only when:** LinkedIn has approved the required product/scopes and a legal/security review accepts the data flow.

**Deliver:** capability-specific adapters for data actually granted, selective storage tags, sync receipts, token revocation, and user-visible fallback.

**Acceptance**

- Contract tests use official fixtures/sandbox access.
- No unavailable scope is implied by the UI.
- Revocation stops sync and deletes or retains data strictly under the selected policy.
- Failure never activates scraping or DOM automation.

## Stage 4 — Content creation and review

### 4.1 Voice onboarding

**Deliver:** audience, domain, content pillars, tone, prohibited phrases, three-to-five user-owned samples, and voice-profile v1.

**Acceptance:** samples carry ownership/source attestations; derived preferences are inspectable and resettable.

### 4.2 One idea and one draft

**Deliver:** one tagged idea, optional compliant research, one draft, claim ledger, and deterministic readability checks.

**Do not build:** a full calendar, multiple automatic variants, scheduling, or publishing.

**Acceptance:** sources support factual claims; no invented personal experience; cost and latency remain inside configured ceilings.

### 4.3 Review workflow

**Deliver:** immutable revisions and `DRAFT → IN_REVIEW → CHANGES_REQUESTED/REJECTED/APPROVED` transitions.

**Acceptance:** property tests prove only a user action can approve the exact immutable revision; editing invalidates approval.

### 4.4 First-party content memory

**Deliver:** domain/pillar/topic/audience/format/hook tags, tag confirmation, embeddings, eligibility, invalidation, and traceable retrieval.

**Acceptance:** only approved/published own posts are positive references; rejected/third-party/cross-workspace data never appears.

## Stage 5 — Calendar and manual publishing

### 5.1 Calendar

**Deliver:** cadence, time zone, quiet days, content-diversity controls, and one-at-a-time generation from approved ideas.

### 5.2 Scheduling and reminders

**Deliver:** approved-revision schedules, idempotent reminders, copy-formatted-post flow, and explicit user publication confirmation.

### 5.3 Feedback learning

**Deliver:** edit deltas, structured rejection reasons, candidate preferences, repeated-signal thresholds, and voice-profile version history.

**Stage acceptance**

- Founder uses the workflow for at least eight weeks and 24 planned posts.
- Median idea-to-approved time improves against the recorded baseline.
- Approval bypasses and duplicate reminders remain zero.
- Cost per approved post fits the future Creator-tier hypothesis.

## Stage 6 — Analytics and prediction

### 6.1 Manual/CSV metrics first

**Deliver:** validated metrics with observation windows, deduplication, baseline capture, and trend views.

### 6.2 Explainable prediction

**Deliver:** versioned features, domain priors, a simple calibrated model, confidence interval, top three factors, and one recommended edit.

### 6.3 Official analytics sync — gated

Add only when the approved LinkedIn capability exists. Manual import remains permanent fallback.

**Stage acceptance:** insufficient-data states are honest; domain-prior and personalized predictions are labelled; calibration is measured before user-facing precision increases.

## Stage 7 — Productization and SaaS beta

### 7.1 Generalization audit

Remove founder-specific assumptions from prompts, defaults, fixtures, source lists, and UI. Interview at least five target users and onboard design partners without direct database/prompt intervention.

### 7.2 SaaS controls

Add managed identity, tenant isolation assessment, public onboarding, privacy/terms flows, rate limits, support/admin recovery, managed storage/queues, backups, deletion manifests, and operational SLOs.

### 7.3 Billing experiment

Add checkout and entitlements only after value and unit economics are measured. The USD 10 personal AI budget is not a subscription price.

**SaaS beta gate:** activation, four-week retention, security, support load, deletion, and unit-economics targets in `plan.md` pass.

## Deferred until evidence justifies them

- Team/agency roles and multiple managed identities.
- Automated image/carousel asset generation.
- Cohort or per-user fine-tuning.
- Swipe-file expansion beyond deliberate user input.
- Cross-customer aggregate intelligence.
- Autonomous engagement or unofficial LinkedIn automation—these remain prohibited, not merely deferred.
