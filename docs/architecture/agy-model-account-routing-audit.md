# AGY Model and Account Routing Audit

**Date:** 2026-08-27  
**Scope:** AlphaBrain supervision of AGY model choice and five saved OAuth profiles  
**Status:** design approved for bounded local implementation; production integration unverified

## Verified current state

- `agy models` currently exposes:
  - `gemini-3.1-pro-high`
  - `gemini-3.7-flash-high`, `medium`, and `low`
  - `claude-sonnet-4-6`
  - `claude-opus-4-6-thinking`
  - older Gemini Flash variants and `gpt-oss-120b-medium`
- Five saved profiles report valid refresh tokens through `agy-switch list`.
- Active profile pointer, standalone token, and macOS Keychain identity agree.
- Existing `switch-account` skill rotates profiles and runs a connectivity probe.
- AlphaBrain currently launches one globally configured model and effort from
  `ANTIGRAVITY_MODEL` and `ANTIGRAVITY_EFFORT`.
- Attempts already persist selected model, but no deterministic task-to-model policy exists.
- AGY rate-limit detection exists, but no per-account/per-model cooldown ledger or reset-aware
  selection exists.

## Gaps and unsafe assumptions

1. A valid OAuth refresh token proves authentication, not remaining Gemini or Claude quota.
2. `switch check` sends one default-model request. It cannot prove quota for every model.
3. Current round-robin rotation does not remember rate-limit time, reset time, recent use, or model
   family. It can rotate directly back onto an exhausted profile.
4. Account switching updates one global token file and one Keychain entry. Concurrent AGY launches
   can race and run under an unintended profile unless switching plus process launch is serialized.
5. Existing skill says mid-conversation switching has zero interruption, but this has not been
   proven for an already-running AGY process. Safe boundary is next AGY process/attempt.
6. A five-hour reset is user-observed behavior, not always machine-readable. Router must prefer an
   explicit provider retry/reset timestamp. When absent, it may use a configurable five-hour
   fallback marked `inferred`, never report it as provider-confirmed.
7. Model names alone do not prove best performance on AlphaBrain. Routing must collect benchmark
   evidence: accepted result, gate pass rate, rework count, duration, tokens, and rate limits.
8. Existing D1-2 evidence-review work is partial and unaccepted. Model-router work must not modify
   or declare D1 complete.

## Routing policy v1

| Stage | Default | Use when | Budget rule | Fallback |
|---|---|---|---|---|
| Critical architecture plan | `claude-opus-4-6-thinking` | High/critical risk, concurrency, security boundary, migration, cross-system design with unresolved choices | One read-only plan turn; no implementation tools; compact structured output | Sonnet 4.6, then Gemini 3.1 Pro High |
| Independent review | `claude-sonnet-4-6` | Diff review, seeded-defect search, contract/security review, plan critique | Read-only; bounded files and output; no implementation loop | Opus only for critical escalation; otherwise Gemini 3.7 Flash review marked same-family/degraded |
| Nontrivial implementation | `gemini-3.1-pro-high` | Runtime logic, state machines, security, migrations, multi-file feature work | One packet; one bounded repair pass | Gemini 3.7 Flash High |
| Fast execution | `gemini-3.7-flash-high` | Tests, docs, repetitive edits, focused bug repair, UI iteration, QA triage | Default high-throughput worker | Gemini 3.1 Pro High |

Google currently describes Gemini 3.7 Flash as its stable coding and agentic-workflow workhorse and
as migration target for Gemini 3.1 Pro. User preference keeps 3.1 Pro High as initial nontrivial
implementation default, but AlphaBrain benchmark evidence may promote 3.7 Flash later. Silent model
fallback is forbidden.

## Selection inputs

Router consumes explicit, persisted facts rather than free-form guesswork:

- project/task/attempt ID;
- stage: `plan`, `implement`, `review`, `qa`, or `mechanical`;
- risk class and complexity class;
- required capabilities and tool needs;
- implementation model/family when selecting independent reviewer;
- allowed models and account pool;
- observed per-account/per-model availability and cooldown;
- recent verified quality, duration, token use, and rework metrics;
- per-task escalation count and Claude-budget allowance.

## Account and quota state

Persist only non-secret metadata keyed by account ID and exact model ID:

- state: `unknown`, `available`, `cooldown`, `auth_failed`, or `disabled`;
- last selected, last success, last failure, and last rate-limit timestamps;
- `next_eligible_at` plus source: `provider`, `configured_fallback`, or `manual`;
- consecutive failures and last sanitized failure class;
- rolling task outcome metrics.

Never persist OAuth/access/refresh tokens, Keychain payloads, raw provider responses, or prompts.

## Execution boundary

```text
task packet
  -> deterministic router selects stage/model/effort
  -> quota ledger selects eligible profile
  -> acquire one global AGY credential lock
  -> switch profile and verify identity without exposing token
  -> launch one AGY process with explicit model and effort
  -> process exits
  -> record sanitized outcome and release lock
  -> on 429: mark exact profile/model cooldown; schedule new attempt
```

No account or model switch occurs inside a running process. Try at most one full eligible-profile
cycle per task attempt. Exhausted pool becomes truthful `RATE_LIMITED`, not infinite rotation.

## Quality and independence rules

- Model choice never bypasses task packet, path boundary, approvals, or QA gates.
- Opus plan is advice, not authority. Senior packet remains execution authority.
- Implementation and independent review should use different provider/model families when available.
- If independent family has no quota, mark review `degraded`, require founder review, and never claim
  independent review passed.
- Benchmark promotion requires enough comparable completed tasks; initial v1 records evidence but
  does not auto-promote models.

## Delivery sequence

1. Build local `alphabrain-model-router` AGY skill and deterministic non-secret selector/ledger.
2. Validate routing, cooldown, lock, no-secret, and bounded-fallback behavior in temporary fixtures.
3. Finish and accept D1-2 evidence-review work separately.
4. Integrate router selection into AlphaBrain task packets and worker launch path.
5. Run same bounded benchmark across Gemini 3.1 Pro High and Gemini 3.7 Flash High.
6. Add Claude planning/review only after bounded quota behavior is verified.
7. Run five-profile rate-limit/recovery proof without exposing tokens or deploying anything.

## Stop conditions

- Never alter saved profiles or active account during selector-only tests.
- Never probe all accounts automatically.
- Never run concurrent profile switches.
- Never deploy, push, commit, or mutate production services in this phase.

