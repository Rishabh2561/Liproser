# Liproser

Liproser is a personal-first AI system for improving a LinkedIn profile and building a repeatable, evidence-aware content workflow. It starts as the founder's private operating system; capabilities are generalized into SaaS features only after sustained personal use demonstrates value.

> **Current status:** planning, evaluation, and repository foundation. Application code has not started.

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

1. **Identity link:** LinkedIn OIDC supplies limited identity information.
2. **User-authorized import:** the user uploads/pastes their LinkedIn PDF, data export, post history, or analytics export.
3. **Official API:** when the Liproser app has the necessary approval and the user grants the applicable scopes, it imports only the capabilities actually available.
4. **Fallback:** unavailable data remains user-imported/manual; no scraper or browser automation is introduced.

The user signs in on the provider's authorization page. Liproser must never request a LinkedIn password in chat or in its own form. See [LinkedIn OIDC](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2), [API access](https://learn.microsoft.com/en-us/linkedin/marketing/increasing-access), and the [LinkedIn API Terms](https://www.linkedin.com/legal/l/api-terms-of-use).

## AI providers and budget

The model gateway supports three selectable providers:

| Provider | Configuration | Intended use |
|---|---|---|
| Ollama (default) | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Local/private development with no external API charge |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_MODEL` | Opt-in hosted structured generation through the Responses API |
| Claude | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Opt-in hosted generation through the Messages API |

The application-level monthly budget defaults to **USD 10**, warns at 80%, and hard-stops paid-provider calls at the limit. Ollama requests count toward usage telemetry but have zero recorded external API cost; hardware/electricity costs are outside this budget.

The local budget is a safety control, not a provider billing guarantee. Configure provider-side limits/alerts independently. OpenAI requests should use `store=false` by default when the adapter supports it; the OpenAI Responses API exposes explicit storage behavior and token/tool ceilings in the [official API reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create). Claude reads `ANTHROPIC_API_KEY` through its SDK as documented in the [Claude authentication guide](https://platform.claude.com/docs/en/manage-claude/authentication). Ollama's local chat endpoint is documented in its [official API guide](https://docs.ollama.com/api/chat).

## Repository map

| File | Purpose |
|---|---|
| [plan.md](plan.md) | Product strategy, requirements, metrics, risks, and productization gates |
| [architecture.md](architecture.md) | System boundaries, data model, APIs, security, deployment, and tests |
| [AGENTS.md](AGENTS.md) | Repository working rules and bounded AI-agent design |
| [ROADMAP.md](ROADMAP.md) | One-feature-at-a-time implementation sequence and acceptance gates |
| [evals/](evals/) | Synthetic evaluation fixtures and scoring instructions |
| [scripts/verify-repository.ps1](scripts/verify-repository.ps1) | Local/CI repository checks |

## Configuration

The committed template is `.env.example`; the working `.env` is ignored by Git.

```powershell
Copy-Item -LiteralPath .env.example -Destination .env
```

Default personal configuration:

```dotenv
APP_ENV=personal
PERSONAL_MODE=true
AI_PROVIDER=ollama
AI_MONTHLY_BUDGET_USD=10.00
AI_BUDGET_HARD_STOP=true
```

To use a hosted provider, set `AI_PROVIDER=openai` or `AI_PROVIDER=anthropic`, then add the relevant key and an account-available model to your uncommitted `.env`. Never paste credentials into issues, commits, logs, or prompts.

## Verification

Run the dependency-free foundation checks in PowerShell:

```powershell
pwsh -NoProfile -File scripts/verify-repository.ps1
```

The script validates required files, local Markdown links, code fences, environment keys, JSONL evaluation fixtures, forbidden tracked secret files, and common credential patterns. GitHub Actions runs the same checks for pushes and pull requests with read-only repository permissions.

Application-specific setup and tests will be added with the first vertical slice. A feature is pushed only after relevant tests pass and the diff is reviewed.

## First implementation slice

Build only this path first:

`manual profile entry → section analysis → before/after suggestion → accept/edit/reject → re-score`

Do not begin calendars, publishing, analytics, or SaaS infrastructure until its exit criteria in [ROADMAP.md](ROADMAP.md) pass.

## License

No license is granted at this time. The repository is public for visibility, but public access does not itself grant permission to copy, modify, or distribute the work. A license decision may be made later, and the repository may become private.
