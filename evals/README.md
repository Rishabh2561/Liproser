# Evaluation fixtures

These fixtures establish regression tests before application prompts or models are implemented. They are synthetic and contain no founder, customer, LinkedIn-export, or third-party post data.

## Files

- `profile_rewrite_cases.jsonl`: protected facts, prohibited inventions, target role, and expected behavior for profile analysis.
- `content_generation_cases.jsonl`: voice/content constraints, evidence requirements, and expected drafting behavior.
- `platform_contract_cases.jsonl`: personal-mode binding, PDF handling, provider-schema, budget-ledger, retention, and memory-eligibility cases.

## Required evaluation record

Each run must record dataset version, case ID, provider/model, prompt/schema/policy versions, output, deterministic checks, human scores, usage, estimated cost, latency, and timestamp.

## Scoring

- Critical protected-fact or invented-claim failures are release blockers.
- Schema validity and required warning behavior are deterministic assertions.
- Usefulness, voice fit, and relevance require blinded human scoring with a written rubric.
- Do not tune prompts on these fixtures and report the same set as an unbiased test set. Split future consented/synthetic cases into development and frozen holdout sets.
- Citation release tests use controlled local HTTP fixtures; live third-party URL availability is monitored separately and cannot fail a deterministic release gate.
