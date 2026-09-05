# Liproser Product Plan

**Status:** implementation baseline

**Primary audience:** founders, product, design, engineering, ML, security, and legal reviewers

**First user:** the founder/operator using Liproser for their own LinkedIn workflow

**Later customer:** solo professionals with the same validated workflow needs
**Related documents:** [README](README.md) · [Stepwise roadmap](ROADMAP.md) · [Technical architecture](architecture.md) · [AI agent design](AGENTS.md)

## 1. Product thesis

Liproser begins as a personal LinkedIn operating system for its founder. It helps turn experience and ideas into a consistent LinkedIn practice through profile optimization, voice-aware content planning, mandatory human review, publishing assistance, and an evidence-driven learning loop. Only workflows proven useful through sustained personal use are generalized into SaaS capabilities.

The product wins by improving a user's own baseline—not by promising virality. It should reduce the effort between an idea and an approved post while preserving the user's judgment, factual responsibility, and distinct voice.

### Product principles

1. **The user is the publisher.** Nothing is published or scheduled without an explicit approval action.
2. **Explain every recommendation.** Profile scores, draft critiques, and predictions expose their contributing factors and confidence.
3. **Prefer evidence over confident prose.** Time-sensitive or quantitative claims carry sources, dates, and review status.
4. **Learn privately.** Feedback improves the user's voice profile; it is not used for cross-customer training without separate consent.
5. **Inspire structurally, never imitate.** Swipe-file patterns may guide format and narrative shape, but source language is excluded from generation context.
6. **Optimize against the user's baseline.** Success means better outcomes and less effort for that user, not vanity comparisons with celebrity accounts.
7. **Use official interfaces only.** No LinkedIn scraping, DOM automation, or unofficial publishing.

## 2. Target user and jobs to be done

### Stage 1 persona: founder/operator

The first version serves one known user: the product owner. It should optimize that person's real profile, content pillars, source library, writing preferences, schedule, and baseline. This stage is an instrumented product-discovery program, not a disguised multi-tenant launch.

### Stage 2 persona: solo professional

A consultant, operator, founder, engineer, or job seeker who has useful expertise but lacks time, confidence, or a repeatable content workflow. They manage one personal LinkedIn presence and approve their own content.

### Personal-first productization rule

A capability becomes a general SaaS feature only after it is used in the founder workflow, produces a measurable improvement or recurring time saving, survives failure/recovery testing, and can be expressed without hard-coded personal assumptions. Personal preferences remain data/configuration; they must not leak into general prompts, rubrics, defaults, or evaluation fixtures.

### Core jobs

- Diagnose why a profile is unclear or hard to find and apply evidence-preserving improvements.
- Turn expertise and timely sources into a balanced content calendar.
- Draft credible posts that sound like the user rather than a generic content model.
- Review, revise, schedule, and publish with full control.
- Learn which topics, formats, and times improve the user's own outcomes.

### Explicit non-goals for the MVP

- Autonomous publishing or engagement automation.
- Full LinkedIn profile ingestion through OAuth.
- Scraping public posts, profiles, feeds, or analytics.
- Team approvals, agency workspaces, white labeling, or multiple managed identities.
- Fine-tuning a model per user.
- Guaranteed impressions, follower growth, or virality.

### Additional non-goals for the personal build

- Billing, checkout, pricing enforcement, or subscription entitlements.
- Public signup, password recovery, team membership, or customer support tooling.
- Production LinkedIn OAuth/API integration.
- Premature abstraction for hypothetical agency workflows.

## 3. Functional requirements

### 3.1 Profile Optimizer

**MVP**

- Accept section-by-section manual entry and LinkedIn PDF export upload.
- Extract Headline, About, Experience, Skills, and Featured content with confidence values; require confirmation when extraction is uncertain.
- Capture target role, domain, seniority, audience, geography, and desired outcomes before scoring.
- Score each section against a versioned rubric: clarity, specificity, relevant terminology, hook quality, evidence, readability, and completeness.
- Present each suggestion as original text, proposed text, explanation, preserved facts, changed claims, confidence, and accept/edit/reject controls.
- Never invent employers, dates, credentials, metrics, scope, or achievements. New claims are visibly marked for user confirmation.
- Re-score accepted edits against the same rubric version and retain score history.

**Later**

- Compare profile analytics before and after an optimization cycle where approved LinkedIn access exists.
- Support role-specific rubric packs and controlled rubric experiments.

### 3.2 Domain-aware content engine

**MVP onboarding inputs**

- Domain/niche and professional positioning.
- Target audience and intended reader outcome.
- Three to five writing samples the user owns or is permitted to provide.
- Tone controls, prohibited phrases, spelling locale, and preferred post length.
- Three to six content pillars and optional user-curated sources.
- Posting cadence, quiet days, time zone, and reminder preferences.

**MVP generation behavior**

- Produce a calendar with a topic, pillar, audience intent, format, evidence needs, and proposed date for each slot.
- Generate one primary draft per idea; produce hook, tone, or format alternatives only on request.
- Support text posts, image concepts, carousel outlines, and polls. The MVP generates concepts/outlines, not final image or carousel assets.
- Balance pillars, formats, hook types, and audience intents; warn about recent repetition.
- Ground timely or quantitative claims in approved public-web sources. Each claim stores source URL, publisher, publication date, retrieval date, excerpt hash, and review status.
- Show a LinkedIn-style preview plus readability, accessibility, and originality feedback.
- Tag every idea and revision with a canonical domain, content pillar, topics, audience intent, format, hook type, and lifecycle status. Users can correct suggested tags before they become reusable metadata.
- Add approved and published posts to a private first-party content memory so future calendars can retrieve relevant examples, avoid repetition, and build on prior themes. Drafts and rejected posts are excluded from positive-reference retrieval.

### 3.3 Human approval workflow

- All generated posts enter `DRAFT`; opening review moves a revision to `IN_REVIEW`.
- The user may approve as-is, edit and approve, request regeneration with structured/free-text feedback, or reject with a reason.
- Store revision history, character/semantic edit deltas, approval action, rejection taxonomy, and user feedback.
- Approved content can be scheduled or prepared immediately. In the MVP, both paths use a copy-formatted-post action and a reminder; the user confirms publication and may add the LinkedIn post URL.
- Once official access is available, expose API publishing only when a capability check passes. Approval is still mandatory.
- Editing approved content creates a new draft revision and invalidates the previous approval.

### 3.4 Predictive performance layer

**V2, not MVP**

- Begin with an explainable rules-and-gradient-boosting ensemble over hook type, length, format, CTA, topic recency, scheduled time, audience history, and similar-post outcomes.
- For cold-start users, use clearly labelled domain priors; blend toward user-specific estimates as reliable history accumulates.
- Return an engagement bucket, calibrated confidence interval, top three factors, and the single editable change most likely to improve the estimate.
- Save the feature vector and model version used at prediction time.
- Evaluate calibration and error by sample size; never present predictions as guarantees.

### 3.5 Post-publish analytics

**V2**

- Start with manual entry and CSV import for impressions, reactions, comments, reposts, clicks, followers, observation time, and post URL.
- Add official analytics pulls only for accounts with approved scopes and valid authorization.
- Show per-post results, rolling trends, pillar/format/time analysis, and performance relative to the user's trailing baseline.
- Distinguish observation windows so a 24-hour post is not compared directly with a 30-day post.
- Feed outcomes into reporting and prediction training only after validation and deduplication.

### 3.6 Swipe file and pattern intelligence

**V3**

- Accept text or files deliberately supplied by the user. URL fields are attribution metadata, not instructions to scrape.
- Extract hook type, structure, emotional trigger, length, formatting, evidence pattern, CTA, audience context, and caveats.
- Default-delete raw third-party content after 30 days; retain derived features until account deletion or an earlier user request.
- Keep all raw and derived data private to the workspace. Do not aggregate raw language or expose it to another customer.
- Create trend reports from the user's derived patterns and compliant public-web research.
- Block generated text that is too similar to stored swipes or the user's recent posts.

## 4. Added product capabilities

### Evidence ledger

Each draft has a claim panel. Claims are classified as opinion, personal experience, stable fact, quantitative claim, or time-sensitive claim. Non-personal factual claims can be `SUPPORTED`, `STALE`, `CONFLICTING`, `UNSUPPORTED`, or `USER_CONFIRMED`. Publishing is allowed with unresolved claims only after an explicit user acknowledgement recorded in the audit log.

### Distinctiveness and content fatigue

Liproser compares a draft with the user's recent posts and active swipe items using embeddings plus lexical overlap. It reports similarity without exposing third-party source text. Calendar generation enforces configurable diversity across pillars, formats, hooks, narrative structures, and CTAs.

### First-party content memory

Each Liproser-created post is classified using a versioned taxonomy. Required tags are domain, pillar, topics, audience intent, format, hook type, evidence status, and publication lifecycle. The user can edit tags; user-confirmed tags override model suggestions while retaining classification history.

Only approved and published revisions are eligible as positive voice/content references. Rejected revisions contribute structured negative feedback but are never retrieved as examples to imitate. Future generation retrieves a small, diverse set of the user's own relevant posts using metadata filters plus semantic similarity, and receives summaries/structural features rather than unrestricted history. Retrieval must cite the internal post IDs used and run a repetition check on the resulting draft.

### Baselines and experiments

Onboarding captures recent post metrics when available. Each planned post may carry one experiment tag such as `hook_style`, `format`, `posting_time`, or `cta`. Reports treat observations as directional unless sample size and controls justify a stronger conclusion.

### Cost and latency controls

- Reuse versioned prompt prefixes and cached research summaries.
- Batch embedding work and deduplicate uploads by content hash.
- Use smaller models for classification/extraction and stronger models for rewriting or final drafting.
- Set per-plan monthly budgets, per-workflow token ceilings, timeouts, and visible retry behavior.
- Record cost and latency per workflow without logging private prompt bodies.

## 5. User experience

### Primary navigation

- **Today:** scheduled work, reminders, outstanding reviews, and next recommended action.
- **Profile:** imported sections, rubric scores, suggestions, and score history.
- **Calendar:** monthly/weekly ideas and status-aware scheduling.
- **Review:** Kanban/list queue with revision comparison and claim panel.
- **Library:** approved sources, voice samples, past posts, and later swipe patterns.
- **Library:** filterable first-party posts by domain/pillar/topic/status, approved sources, voice samples, and later swipe patterns.
- **Insights:** baseline, results, experiments, and later predictions.
- **Settings:** voice controls, data/consent, integrations, billing, export, and deletion.

### Golden personal journey

1. User signs in, accepts data terms, and sets locale/time zone.
2. User uploads a PDF or pastes profile sections, confirms extraction, and selects a target role.
3. Liproser scores the profile and offers evidence-preserving diffs.
4. User supplies voice samples, audience, pillars, cadence, and sources.
5. Liproser proposes a calendar; user adjusts and generates a draft.
6. User reviews claims and originality, then edits or approves.
7. Scheduler sends a reminder; user copies the formatted post to LinkedIn and confirms publication.
8. User optionally records the post URL and metrics for future insights.

### Personal validation journal

Every real use records the task, time spent, AI cost, accepted/rejected result, material edits, confidence, publication outcome, and a short usefulness note. A weekly review identifies repeated friction, missing capabilities, and features that appeared valuable but were not used. This journal is product evidence and must exclude secrets or unnecessary copied third-party content.

## 6. Metrics and instrumentation

### North-star outcome

**Approved, published posts per active user per month that pass evidence and originality checks.** This joins useful output, quality, and actual follow-through.

### Product metrics

| Area | Metric | Definition |
|---|---|---|
| Activation | First-value completion | Profile suggestion accepted or first post approved within 24 hours of onboarding |
| Generation quality | Approval without material edit | Approved revisions with semantic edit distance below the configured threshold |
| Workflow | Median time to approval | Time from first draft ready to approved revision, excluding user-configured quiet hours |
| Follow-through | Scheduled-to-confirmed publish rate | Confirmed manual/API publications divided by due scheduled posts |
| Retention | Four-week creator retention | User publishes at least once in each of four consecutive weeks |
| Outcome | Engagement-rate lift | User's normalized engagement rate versus their pre-Liproser/trailing baseline |
| Trust | Claim issue escape rate | Published posts later marked with an unsupported or incorrect generated claim |
| Distinctiveness | Similarity block rate | Drafts blocked or revised due to excess source/recent-post similarity |
| Reuse quality | Memory-assisted approval lift | Approval/edit difference for drafts using first-party memory versus the user's prior baseline |
| Prediction | Calibration/error | Bucket calibration and MAE/MAPE where statistically meaningful |
| Efficiency | Cost per approved post | Model, search, embedding, storage, and worker cost divided by approved posts |

Metrics are segmented by cohort, domain, format, tenure, and data completeness. They must never leak one customer's content or small-cohort outcomes.

During the personal stage, report a compact founder scorecard instead: weekly approved/published posts, median minutes from idea to approved draft, approval/edit rate, unsupported-claim count, cost per approved post, schedule adherence, and engagement versus the founder's captured baseline. Cohort segmentation begins only after SaaS launch.

## 7. Productization and monetization hypotheses

Do not implement billing during the personal stage. Before public beta, interview comparable professionals and validate that the personally proven workflow generalizes. Pricing remains an experiment, not a launch promise.

| Tier | Intended value | Candidate limits |
|---|---|---|
| Free profile audit | Demonstrate immediate value | One profile import, limited suggestions, no calendar automation |
| Creator | Full solo workflow | Monthly generation budget, scheduling/reminders, voice learning, evidence checks |
| Pro creator | Higher cadence and insights | Higher budgets, advanced experiments, analytics, official integrations when eligible |
| Team/agency (later) | Manage multiple identities | Seats, workspaces, roles, approval policies, consolidated billing |

Test willingness to pay against approved posts, hours saved, and retention. Do not price predictions as guaranteed performance.

## 8. Delivery roadmap and gates

| Phase | Deliverable | Exit gate |
|---|---|---|
| 0. Personal foundation | Local/private runtime, data inventory, rubric prototype, model evaluations, no-scraping policy | Own profile/data complete one safe end-to-end dry run |
| 1. Personal operating system | Profile workflow, voice profile, tagged content memory, calendar, drafts, review, reminders, manual publish confirmation, validation journal | Used for at least 8 weeks and 24 planned posts; tags corrected/confirmed; zero approval bypasses; quality/cost targets met |
| 2. Productization | Remove personal assumptions, add onboarding, managed identity, tenant isolation verification, privacy controls, support/admin basics | Five design partners complete the golden journey without operator intervention |
| 3. SaaS beta | Managed deployment, public signup, quotas, billing experiment, operational SLOs | Activation, four-week retention, support load, security, and unit-economics gates met |
| 4. Official publishing | LinkedIn capability discovery and posting behind feature flags | Developer access, technical sign-off, token security review, failure recovery tested |
| 5. Prediction and analytics | Manual/CSV metrics, baselines, explainable model, later official pulls | Observation-window integrity and calibration gates met; insufficient-data UX tested |
| 6. Pattern intelligence | Derived-first swipe analysis and trend reports | Retention deletion verified; similarity leakage tests pass; legal review renewed |
| 7. Team/agency | Multi-profile workspaces, roles, approval policies | Tenant isolation and delegated authorization independently assessed |
| 8. Model adaptation | Cohort tuning or preference optimization | Explicit consent, sufficient samples, holdout gains, rollback and deletion strategy |

### Productization gate checklist

- At least eight consecutive weeks of founder use and 24 planned posts, including both accepted and rejected drafts.
- Median idea-to-approved time is materially lower than the founder's recorded manual baseline.
- Profile and post workflows show repeat use without direct database or prompt editing.
- Costs fit the candidate Creator-tier unit economics with headroom for support and infrastructure.
- Five target-user interviews confirm the same jobs and terminology; no private founder-specific assumptions are treated as defaults.
- Data export/deletion, tenant isolation, authentication, abuse controls, and support recovery are complete before external accounts are accepted.

## 9. Risks and mitigations

| Risk | Impact | Mitigation / launch gate |
|---|---|---|
| LinkedIn permission denial or change | Publishing/analytics unavailable | Manual workflow is complete; feature flags and capability discovery; version monitoring |
| Scraping or content-rights violation | Account, legal, and reputation harm | No scraping/DOM extension; user-supplied inputs; derived-first retention; counsel review |
| Hallucinated claim | User reputation harm | Evidence ledger, claim classifier, explicit acknowledgement, traceable prompt/model versions |
| Generic or homogenized content | Low trust and weak outcomes | Voice conditioning, diversity budgets, similarity checks, alternatives on demand |
| Cross-tenant leakage | Severe privacy incident | Tenant-scoped queries, object prefixes, authorization tests, encrypted secrets, redacted logs |
| Weak cold-start prediction | Misleading advice | Domain priors clearly labelled; confidence intervals; minimum-data thresholds |
| Feedback-loop bias | Narrow, repetitive output | Negative feedback taxonomy, exploration budget, diverse evaluation set, user-reset controls |
| Stale or self-reinforcing content memory | Repetitive, outdated posts | Lifecycle/freshness filters, diverse retrieval, user tag controls, repetition gate, memory reset |
| Cost spikes | Poor unit economics | Plan budgets, model routing, caching, batching, quotas, alerts, graceful limits |
| Reminder fatigue | Churn | User-controlled channels/quiet hours, digest mode, idempotent notifications |
| Overfitting to the founder | Poor market fit | Personal validation journal, explicit configuration, design-partner tests, productization gate |
| Premature SaaS infrastructure | Delayed learning | Local/private stage omits billing/public signup while preserving migration-compatible boundaries |

## 10. Compliance assumptions and launch gates

- LinkedIn OIDC supplies limited identity information and is not a full profile-import mechanism: [Sign In with LinkedIn using OIDC](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2).
- Posting and member analytics are capability-gated; analytics permissions require approved Community Management access: [LinkedIn API access](https://learn.microsoft.com/en-us/linkedin/marketing/increasing-access) and [Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api).
- Liproser will not scrape or automate LinkedIn pages: [LinkedIn User Agreement](https://www.linkedin.com/legal/user-agreement) and [Prohibited software and extensions](https://www.linkedin.com/help/linkedin/answer/a1341387/prohibited-software-and-extensions).
- LinkedIn-sourced API data must remain selectively deletable and follow the applicable storage, consent, and deletion terms: [LinkedIn API Terms of Use](https://www.linkedin.com/legal/l/api-terms-of-use).
- Before production: obtain legal review, model-provider data-term approval, a privacy/security assessment, and any necessary LinkedIn developer approval.

## 11. Acceptance criteria for this plan

- Every original module maps to a delivery phase and architecture subsystem.
- The personal operating system is useful without public signup, billing, or LinkedIn API approval.
- SaaS productization has measurable gates rather than a calendar-only handoff.
- Generated posts are consistently tagged and approved/published revisions can be found and reused through private, traceable first-party retrieval.
- Every AI output has an owner, version, trace, fallback, and human decision point.
- Manual publishing delivers complete MVP value without LinkedIn API approval.
- State transitions cannot bypass approval, including retries and scheduled work.
- Tenant export and deletion cover relational data, vectors, objects, tokens, cached prompts, and derived swipe patterns.
- `architecture.md` uses the same statuses, resources, retention rules, and phase boundaries.
- `AGENTS.md` gives agents no authority over publishing, approval, billing, or tenant access.
