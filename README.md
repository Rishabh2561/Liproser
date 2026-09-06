# Liproser

Liproser is a personal-first AI system for improving a LinkedIn profile and building a repeatable, evidence-aware content workflow. It starts as the founder's private operating system; capabilities are generalized into SaaS features only after sustained personal use demonstrates value.

> **Current status:** `v0.1` profile optimizer implemented for local personal use. Content creation and later releases have not started.

## What Liproser will do

- Import profile data through user-authorized, compliant sources.
- Score profile sections and propose fact-preserving before/after edits.
- Learn a private voice profile from user-owned samples and review feedback.
- Plan domain-tagged content and generate one primary draft at a time.
- Require explicit human approval before scheduling or publishing.
- Store approved/published posts as private first-party content memory.
- Capture post metrics and later explain performance predictions against the user's baseline.

Liproser does not scrape LinkedIn, automate its website, fabricate professional claims, or auto-publish without approval.

## Personal-first strategy

The first implementation is for one founder workspace. It intentionally omits public signup, billing, teams, and production LinkedIn integration. The personal workflow must be used for at least eight weeks and 24 planned posts before the productization gate is evaluated.

See the [stepwise roadmap](ROADMAP.md) for the exact build order and exit criteria.

## LinkedIn data access

Signing in with LinkedIn does **not** automatically provide a complete profile, post history, or analytics. Liproser uses a capability ladder:

1. **User-supplied profile:** the user enters sections manually or uploads a LinkedIn PDF in `v0.1`.
2. **User-supplied history:** later releases accept deliberate post and analytics CSV/manual imports.
3. **Identity link:** optional LinkedIn OIDC supplies limited identity information; it is not profile ingestion.
4. **Official API:** only after Liproser is approved and the user grants specific scopes, capability-specific synchronization becomes available.
5. **Fallback:** unavailable data remains user-imported/manual; no scraper or browser automation is introduced.

The user signs in on the provider's authorization page. Liproser must never request a LinkedIn password in chat or in its own form. See [LinkedIn OIDC](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2), [API access](https://learn.microsoft.com/en-us/linkedin/marketing/increasing-access), and the [LinkedIn API Terms](https://www.linkedin.com/legal/l/api-terms-of-use).

## AI providers and budget

The model gateway supports three selectable providers:

| Provider | Configuration | Intended use |
|---|---|---|
| Ollama | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Optional local/private inference with no external API charge |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_MODEL` | Opt-in hosted structured generation through the Responses API |
| Claude | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Opt-in hosted generation through the Messages API |

No provider is active by default. First-run setup validates the selected adapter and stores only its provider/model choice; credentials remain in the ignored environment. The application-level OpenAI-plus-Claude budget is **USD 10 per UTC calendar month**. It reserves estimated cost before dispatch, warns at 80%, rejects calls with insufficient unreserved balance, and reconciles actual usage afterward. Concurrent in-flight calls and price drift can still cause a small overshoot, so provider-side limits remain necessary. Ollama usage is measured at zero external API cost.

The local budget is a safety control, not a provider billing guarantee. Configure provider-side limits/alerts independently. OpenAI requests should use `store=false` by default when the adapter supports it; the OpenAI Responses API exposes explicit storage behavior and token/tool ceilings in the [official API reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create). Claude reads `ANTHROPIC_API_KEY` through its SDK as documented in the [Claude authentication guide](https://platform.claude.com/docs/en/manage-claude/authentication). Ollama's local chat endpoint is documented in its [official API guide](https://docs.ollama.com/api/chat).

## Repository map

| File | Purpose |
|---|---|
| [plan.md](plan.md) | Product strategy, requirements, metrics, risks, and productization gates |
| [architecture.md](architecture.md) | System boundaries, data model, APIs, security, deployment, and tests |
| [AGENTS.md](AGENTS.md) | Concise repository working rules |
| [docs/ai-agents.md](docs/ai-agents.md) | Runtime AI-agent contracts, permissions, fallbacks, and evaluations |
| [ROADMAP.md](ROADMAP.md) | One-feature-at-a-time implementation sequence and acceptance gates |
| [evals/](evals/) | Synthetic evaluation fixtures and scoring instructions |
| [scripts/verify-repository.ps1](scripts/verify-repository.ps1) | Local/CI repository checks |

## Local setup

The committed template is `.env.example`; the working `.env` is ignored by Git.

```powershell
Copy-Item -LiteralPath .env.example -Destination .env
& 'C:\Users\rigu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -e '.[dev]'
pnpm install
```

Default personal configuration:

```dotenv
APP_ENV=personal
PERSONAL_MODE=true
AI_PROVIDER=unconfigured
AI_MONTHLY_BUDGET_USD=10.00
AI_BUDGET_HARD_STOP=true
```

First-run setup offers `ollama`, `openai`, or `anthropic`. Add the selected provider's key/model only to your uncommitted `.env`; automated tests use a fake adapter. Never paste credentials into issues, commits, logs, or prompts.

## Verification

Run the dependency-free foundation checks in PowerShell:

```powershell
pwsh -NoProfile -File scripts/verify-repository.ps1
```

The script validates required files, local Markdown links, code fences, environment keys, JSONL evaluation fixtures, forbidden tracked secret files, and common credential patterns. GitHub Actions runs the same checks for pushes and pull requests with read-only repository permissions.

Application-specific setup and tests will be added with the first vertical slice. A feature is pushed only after relevant tests pass and the diff is reviewed.

Start PostgreSQL using `DATABASE_URL`, apply the schema, then run API and web in separate PowerShell terminals:

```powershell
& '.\.venv\Scripts\alembic.exe' upgrade head
& '.\.venv\Scripts\python.exe' -m uvicorn liproser.main:app --app-dir apps/api --host 127.0.0.1 --port 8000 --reload
pnpm --filter @liproser/web dev
```

Open `http://127.0.0.1:3000`. Personal mode refuses production or non-loopback binding. Uploaded PDFs are retained under the ignored `PRIVATE_STORAGE_ROOT` until you use the visible delete action.

## Implemented `v0.1` slice

Build only the `v0.1` path first:

`manual/PDF profile import → confirm extraction → section analysis → before/after suggestion → accept/edit/reject → re-score`

The current implementation includes provider readiness, hosted-cost ledger primitives, manual/PDF import, extraction confirmation, deterministic fact-preserving analysis fallback, section decisions, source download/deletion, and same-rubric re-score. Do not begin calendars, publishing, analytics, or SaaS infrastructure until its exit criteria in [ROADMAP.md](ROADMAP.md) pass.

## License

No license is granted at this time. The repository is public for visibility, but public access does not itself grant permission to copy, modify, or distribute the work. A license decision may be made later, and the repository may become private.
