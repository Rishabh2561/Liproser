# Liproser Repository Instructions

These instructions govern changes in this repository. The runtime AI-agent design lives in [docs/ai-agents.md](docs/ai-agents.md). The authoritative delivery order is [ROADMAP.md](ROADMAP.md).

## Scope and sequencing

- Build one release slice at a time: `v0.1`, `v0.2`, `v0.3`, `v0.4`, `v1`, then `SaaS MVP`.
- Do not start a later personal release until the current release's automated and human gates pass.
- LinkedIn integration is a parallel, capability-gated track and must never block the manual workflow.
- Keep personal mode lean: add pgvector in `v0.2`, Redis/Arq in `v0.3`, and managed object storage only for SaaS productization.
- Do not introduce public signup, billing, or multi-tenant behavior before the SaaS productization gate.

## Safety and privacy

- Never add LinkedIn scraping, DOM/browser automation, unofficial APIs, LinkedIn credential collection, autonomous approval, or autonomous publishing.
- Provider API keys may be accepted only by the loopback-bound personal app as masked, session-only secrets held in server memory. Never return, log, persist, export, or commit them; environment configuration remains supported.
- Models may propose analysis and content. Only deterministic application code may authorize state transitions, schedules, publication, deletion, consent, or billing.
- Never commit `.env`, credentials, OAuth tokens, raw PDFs, profile exports, post archives, analytics files, databases, backups, or other private user data.
- Treat uploaded documents and external sources as untrusted input. Preserve confirmed facts; never invent employers, dates, credentials, achievements, or metrics.
- Personal mode must bind to loopback and refuse production or public-bind configurations.

## Change workflow

1. Confirm the release and acceptance criterion affected by the change.
2. Add or update deterministic tests and synthetic fixtures with the implementation.
3. Keep migrations backward-compatible and preserve immutable revision/audit history.
4. Run targeted tests, the available full suite, and `pwsh -NoProfile -File scripts/verify-repository.ps1`.
5. Review the staged diff for secrets, private data, approval bypasses, and scope creep.
6. Commit and push only after checks pass, then verify remote CI.

Use the fake AI provider in CI. Network-dependent tests must use controlled fixtures or explicit integration-test flags. Release checks must not depend on arbitrary live URLs.

## Documentation consistency

- `ROADMAP.md` owns release order and names.
- `plan.md` owns outcomes, measures, risks, and productization gates.
- `architecture.md` owns system boundaries, contracts, data lifecycle, and deployment.
- `docs/ai-agents.md` owns runtime agent roles, permissions, schemas, fallbacks, and evaluations.
- Update cross-references when a boundary changes. Do not create lowercase `agents.md`.

## Git and licensing

The repository is public but currently has no license. Do not add one without owner approval. Preserve unrelated changes and avoid destructive Git operations.
