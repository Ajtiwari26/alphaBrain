# MAB-AGC-001
## Architectural Garbage Collector & Context Lifecycle Subsystem

| Field | Specification |
|---|---|
| System | AlphaBrain |
| Architectural authority | Tier 0 Chief Strategic Architect |
| Status | Proposed normative blueprint; pending canonical ratification |
| Source | `ASTRA_AGC_DIGEST.md` |
| Canonical author | Claude Opus 4.6 Thinking |
| Governance | Existing invariants I-1 through I-68 retain precedence |
| Scope | Architectural context selection, modularization, archival, ephemeral pruning, provenance, recovery |

**Normative language:** MUST, MUST NOT, and SHOULD express mandatory requirements, prohibitions, and recommended defaults.

**Authority boundary:** Supplied digest references I-65 but omits its canonical wording. This blueprint specifies deadlock and fail-closed requirements without redefining I-65. Activation MUST remain blocked until Claude Opus verifies compatibility against the canonical invariant text and ratifies the integration.

---

## 1. Executive Architectural Directive

AGC SHALL reduce active architectural context while preserving authoritative meaning, reproducible evidence, and immutable provenance.

AGC is a deterministic maintenance subsystem. It MUST NOT independently decide which architectural proposals become authoritative, rewrite architectural conclusions, or treat age as proof that an artifact is disposable.

Three operations are authorized by this design:

1. Keep current directives and in-flight epic materials in an explicit active context set.
2. Relocate completed or superseded architectural records into verifiable cold archives.
3. Remove explicitly classified ephemeral artifacts only after durable evidence capture and provenance verification.

Compression, relocation, and pruning MUST remain distinct from architectural ratification.

### 1.1 Core invariant extensions

Identifiers below are blueprint-local. Canonical invariant numbering remains reserved for ratification.

| ID | Required invariant |
|---|---|
| AGC-01 — Authority preservation | Every authoritative requirement retains an identified canonical location, stable identifier, and ratification provenance. |
| AGC-02 — Active-work exclusion | No artifact referenced by an admitted, queued, leased, running, reviewing, or promotion-pending task may leave the active working set. |
| AGC-03 — Evidence before removal | Source removal requires independently verified durable evidence and a recoverable transaction record. |
| AGC-04 — Exact identity | Every mutation binds artifact identity, original path, byte length, pre-compression SHA-256, and lifecycle generation. |
| AGC-05 — Exclusive authorship | Only authenticated Claude Opus 4.6 Thinking authority may authorize architectural Markdown creation, modification, relocation, or deletion. |
| AGC-06 — Fail closed | Missing, stale, inconsistent, unsupported, or unverifiable prerequisites deny mutation. |
| AGC-07 — No inferred disposal | File age, filename, extension, directory placement, or low retrieval frequency cannot independently establish pruning eligibility. |
| AGC-08 — Atomic logical visibility | Context readers observe either the old complete generation or the new complete generation. Partial transitions are never authoritative. |
| AGC-09 — Immutable archives | Published archive generations cannot be overwritten. Corrections create new generations with explicit predecessor links. |
| AGC-10 — Provenance continuity | Evidence and referenced Git objects remain retained and reachable. A hash alone is not a recoverable record. |
| AGC-11 — Bounded coordination | Locks have bounded acquisition, fixed ordering, fencing, and recovery ownership. No model or network call occurs while mutation locks are held. |
| AGC-12 — Deterministic execution | Execution applies an exact reviewed plan. It cannot add candidates or expand scope during mutation. |

---

## 2. Three-Tier Lifecycle State Machine

### 2.1 States

| State | Meaning | Default context behavior |
|---|---|---|
| `ACTIVE_WORKING_SET` | Current governing material, active epic artifacts, or registered ephemeral working artifacts | Eligible for role-scoped retrieval |
| `ARCHIVED_COLD` | Immutable, compressed historical architectural records with verified manifest and provenance | Excluded unless explicitly requested |
| `PRUNED_EPHEMERAL` | Ephemeral source removed; durable evidence reference and tombstone retained | Excluded |

Lifecycle state belongs to an artifact revision. Paths alone do not define identity or state.

### 2.2 Allowed transitions

| Transition | Preconditions | Postconditions |
|---|---|---|
| `ACTIVE_WORKING_SET → ARCHIVED_COLD` | Epic terminal; no active references or pins; explicit archival classification; verified successor where superseded; exact Opus authorization for Markdown mutations | Verified immutable bundle published; catalog committed; original active source removed through recoverable cleanup |
| `ACTIVE_WORKING_SET → PRUNED_EPHEMERAL` | Explicit ephemeral classification; no unique governing content; no active references; durable evidence captured; verified Git trailer provenance | Source absent; immutable tombstone and evidence locator retained |
| `ARCHIVED_COLD → ACTIVE_WORKING_SET` | Explicit reactivation request; archive verification; admission coordination; authority checks | New active revision created from verified bytes; historical archive remains immutable |

`ARCHIVED_COLD → PRUNED_EPHEMERAL` is prohibited.

`PRUNED_EPHEMERAL` is terminal. Reusing retained evidence creates a new artifact revision linked to the tombstone.

Transaction phases such as `PREPARED` or `COMMITTED` are operational states, not additional lifecycle tiers.

### 2.3 Eligibility and reference semantics

Archival requires all associated tasks to be terminal, with no unresolved review, promotion, retry, dependency, or evidence-retention requirement.

Reference checks MUST include:

- Task packets and admission records.
- Queued and leased work.
- Reviews, promotions, and retry eligibility.
- Cross-epic dependencies.
- Explicit human or system retention pins.

Expired leases alone do not establish terminal status. Unknown scheduler state blocks mutation.

Shared artifacts remain active until every relevant reference permits transition.

### 2.4 Locking contract

Scheduler admission, context readers, directive updates, and AGC MUST share one coordination domain.

Global acquisition order:

```text
repository coordination lock
  → epic locks, ascending epic_id
    → artifact locks, ascending artifact_id
      → lifecycle catalog transaction
```

- Normal admissions and reads acquire shared coordination protection.
- AGC commit and directive topology changes acquire exclusive coordination protection.
- Context readers hold generation pins for their full read operation.
- Active tasks retain durable reference pins beyond short-lived read locks.
- Every mutation transaction carries a monotonically increasing fencing token.
- Every filesystem mutation passes through a mutation broker that validates the current token.
- Workers without broker authorization MUST lack direct mutation access to protected paths.

A process-local mutex or unenforced lease is insufficient.

Lock timeout releases acquired locks and returns a retryable denial. Lock acquisition MUST NOT wait indefinitely or upgrade shared locks in place.

### 2.5 Transaction protocol

1. **Plan:** Capture candidates, hashes, task references, policy versions, Git identity, and lifecycle generation.
2. **Prepare:** Build and verify staged archives or ephemeral evidence outside exclusive mutation locks.
3. **Revalidate:** Acquire ordered locks; reread scheduler state, pins, generations, source identities, and authorization.
4. **Publish:** Durably publish immutable evidence and append transaction intent.
5. **Commit:** Atomically switch lifecycle catalog generation to verified destinations.
6. **Clean up:** Remove redundant source copies under the same fencing protections.
7. **Finalize:** Record completion and release locks.

Published destinations MUST exist and pass verification before catalog commit.

A cleanup failure leaves redundant bytes, never missing evidence. Recovery resumes cleanup only after revalidation. A pre-commit failure leaves sources active.

---

## 3. Master Directive Modularization

### 3.1 Required topology

```text
docs/architecture/
├── SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md
├── invariants/
│   ├── INDEX.md
│   ├── I-001.md
│   ├── ...
│   └── I-068.md
├── topologies/
│   ├── autonomous-development.md
│   └── context-lifecycle.md
├── security/
│   ├── authority-and-path-protection.md
│   ├── safety-gates.md
│   └── locking-and-recovery.md
├── epics/
│   └── <epic_id>/
│       ├── MAB-<id>.md
│       └── <active-review>.md
└── archive/
    └── <epic_id>/
        └── <archive_id>/
            ├── manifest.json
            └── payload.tar.zst
```

Existing ratified sections MUST receive explicit destinations. Migration cannot silently discard text that does not fit proposed module names.

### 3.2 Master index contract

`SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md` remains the canonical entry point. It contains:

- Governance authority and precedence rules.
- Mandatory baseline modules for every agent.
- Topic-to-module routing.
- Stable invariant links.
- Current ratified revision and migration provenance.
- Explicit separation between governing modules and historical evidence.

Each index entry MUST expose:

```text
module_id | topic | relative_path | stable_anchor
authority_status | ratification_ref | required_for_roles
```

Authoritative module hashes reside in a versioned, machine-readable lifecycle catalog bound to a Git revision. Modules MUST NOT contain self-referential hashes.

Agents load the master index, mandatory governance baseline, and relevant topic modules. Recursive loading of all architectural Markdown is prohibited as the default context strategy.

### 3.3 Opus-exclusive authoring

Path protection MUST cover:

- Every Markdown file directly or recursively under `docs/architecture/`.
- Both source and destination paths for moves.
- Rename, unlink, replacement, and symlink-based bypass attempts.
- Extraction or restoration that would materialize protected Markdown.

AGC may mechanically execute a Markdown lifecycle mutation only under an authenticated Opus authorization bound to:

```text
plan_digest
source_paths_and_hashes
destination_paths
permitted_operations
policy_revision
expiry
```

An author field or model name inside a document is not authorization.

Non-Opus agents may propose changes through review artifacts outside canonical protected paths. They MUST NOT author canonical modules.

### 3.4 Migration acceptance

Before modularization becomes authoritative, Opus MUST approve a coverage ledger mapping every existing ratified section, invariant, and stable reference to its destination.

Required checks:

- I-1 through I-68 remain represented without semantic loss.
- Existing internal references resolve or have explicit compatibility mappings.
- No competing canonical copy remains active.
- Index and modules publish as one catalog generation.
- Previous directive bytes remain recoverable with verified provenance.

AGC cannot ratify its own modularization.

---

## 4. Cold Archive Specification

### 4.1 Archive identity and formats

`epic_id` and `archive_id` MUST be validated path-safe identifiers. Each archive generation is immutable.

Supported schema-v1 formats:

| Format | Policy |
|---|---|
| `tar.zst` | Default |
| `tar.gz` | Explicit compatibility option |

Archive creation MUST normalize member ordering, ownership metadata, and timestamps according to a versioned compression profile.

Only regular-file members are permitted. Absolute paths, traversal, duplicate names, links, devices, and undeclared members are prohibited.

### 4.2 `manifest.json` schema

The following typed contract is mandatory. All fields are required unless marked optional; unknown fields are rejected for schema version 1.

| Field | Type / constraint |
|---|---|
| `schema_version` | Integer; exactly `1` |
| `archive_id` | Unique path-safe string |
| `epic_id` | Path-safe string |
| `created_at` | UTC RFC 3339 timestamp |
| `transaction_id` | Unique string |
| `plan_sha256` | 64 lowercase hexadecimal characters |
| `policy_revision` | Immutable policy identifier |
| `catalog_generation_before` | Nonnegative integer |
| `authority_ref` | Durable reference to verified authorization |
| `predecessor_archive_id` | String or `null` |
| `source_git` | Object defined below |
| `bundle` | Object defined below |
| `files` | Nonempty array of file entries |

`source_git`:

```text
repository_id: string
object_format: enum("sha1", "sha256")
commit_oid: valid object ID for object_format
retention_ref: durable Git reference
```

`bundle`:

```text
name: enum("payload.tar.zst", "payload.tar.gz")
format: enum("tar.zst", "tar.gz")
compression_profile: versioned string
bytes: nonnegative integer
sha256: 64 lowercase hexadecimal characters
```

Each `files[]` entry:

```text
artifact_id: string
revision_id: string
original_path: normalized repository-relative path
member_path: normalized archive-relative path
classification: enum("completed_architecture", "superseded_architecture")
bytes: nonnegative integer
sha256_precompression: 64 lowercase hexadecimal characters
source_blob_oid: valid Git blob object ID
superseded_by: artifact revision reference or null
```

Additional constraints:

- Original paths, member paths, and artifact revisions MUST be unique.
- `superseded_architecture` requires a verified `superseded_by` reference.
- Bundle extension and format MUST agree.
- Every source MUST match retained Git content before archival.
- Pre-compression hashes cover exact original bytes, without newline or encoding normalization.

Manifest digest is recorded externally in the immutable transaction receipt and lifecycle catalog. It MUST NOT be embedded as a self-hash. A bundle digest alone does not authenticate a replaceable manifest.

### 4.3 Verification protocol

Before removing any source:

1. Verify manifest schema, authorization reference, and retained Git provenance.
2. Verify compressed bundle size and SHA-256.
3. Stream-decompress using bounded resource limits.
4. Reject unsafe, duplicate, missing, or undeclared members.
5. Verify each member’s uncompressed size and SHA-256 against `sha256_precompression`.
6. Verify reconstructed bytes against retained Git blobs.
7. Revalidate current source bytes under mutation locks.
8. Durably persist bundle, manifest, directory entries, and transaction receipt.

Restore MUST repeat verification before materializing files. Extracted content is historical evidence until separately admitted as active context.

### 4.4 Ephemeral pruning evidence

Before pruning, AGC MUST retain either the exact ephemeral bytes or an approved durable evidence record sufficient for the artifact’s retention policy.

A retained Git commit MUST contain:

```text
AlphaBrain-Review-Hash: <sha256>
```

An accompanying durable receipt maps that hash to artifact identity, original path, evidence locator, transaction, and retained commit.

The trailer is an integrity reference, not a substitute for evidence content. If unique evidence cannot be retained and verified, pruning is denied.

---

## 5. CLI Command Specification

### 5.1 Interfaces

```bash
# Build a read-only collection plan; no lifecycle or source mutations.
.venv/bin/python -m alpha_core.triage_cli gc \
  --dry-run \
  --format json

# Build an archival plan for one completed epic.
.venv/bin/python -m alpha_core.triage_cli archive-epic \
  --epic-id EPIC-042 \
  --compression tar.zst \
  --dry-run \
  --format json

# Apply an exact plan using a scoped authorization reference.
.venv/bin/python -m alpha_core.triage_cli gc \
  --apply \
  --plan /path/to/agc-plan.json \
  --expect-plan-sha256 <sha256> \
  --authorization-ref <reference>
```

`archive-epic` is a restricted planner/executor over the same transaction engine. It MUST NOT implement an independent deletion path.

### 5.2 Arguments

| Argument | Contract |
|---|---|
| `--dry-run` | Default; inspect and emit plan without mutation |
| `--apply` | Explicit execution; mutually exclusive with `--dry-run` |
| `--epic-id <id>` | Scope selection; required by `archive-epic` |
| `--action archive\|prune-ephemeral\|all` | `gc` selection; default `archive` |
| `--compression tar.zst\|tar.gz` | Archive encoding; default `tar.zst` |
| `--plan <path>` | Serialized immutable execution plan |
| `--expect-plan-sha256 <digest>` | Required with `--apply` |
| `--authorization-ref <ref>` | Required with `--apply` |
| `--lock-timeout-seconds <n>` | Bounded lock acquisition |
| `--format text\|json` | Human or machine-readable output |

No `--force`, recursive deletion option, or SafetyGate bypass is permitted.

Dry-run output MUST include eligible and rejected candidates, reasons, hashes, references, proposed destinations, expected storage changes, and captured generations. Eligibility is advisory until execution revalidation.

### 5.3 SafetyGate checks

Both planning and execution evaluate typed gates. Execution reruns all mutable checks under coordination protection.

Required checks:

1. Canonical policy available; I-65 compatibility ratified.
2. Plan digest, scope, expiry, and authority valid.
3. Opus authority valid for every protected Markdown operation.
4. Epic and task state authoritative and terminal where required.
5. Reference pins and retention holds absent.
6. Source identity, hashes, Git provenance, and generations unchanged.
7. Destinations collision-free and path-safe.
8. Evidence manifests and payloads valid.
9. Storage and audit facilities support durable commit and recovery.
10. Lock ownership and fencing token current.

Gate results MUST distinguish `PASS`, `DENY`, and `UNKNOWN`. Only complete `PASS` permits mutation.

### 5.4 Audit and exit behavior

Audit receipts record actor, authority, plan digest, source and destination hashes, lifecycle generations, fencing token, gate results, Git references, timestamps, and transaction outcome.

| Exit code | Meaning |
|---|---|
| `0` | Plan produced, verified no-op, or transaction completed |
| `2` | Invalid arguments or schema |
| `3` | SafetyGate denial or unknown prerequisite |
| `4` | Lock timeout or stale-plan conflict; replan required |
| `5` | Integrity or provenance failure |
| `6` | Interrupted transaction or recovery required |

Deterministic terminal-epic hooks MAY request plans. Automatic application requires an exact scoped authorization and the same gates; hooks confer no additional authority.

---

## 6. I-65 Deadlock and Fail-Closed Safeguards

### 6.1 Canonical integration requirement

Implementation MUST bind its I-65 compatibility check to an immutable canonical revision.

Missing invariant text, changed policy revision, or unresolved interpretation produces:

```text
DENY: CANONICAL_I65_COMPATIBILITY_UNVERIFIED
```

This blueprint does not claim that its safeguards reproduce the unavailable canonical wording.

### 6.2 Deadlock prevention

- All participants follow the global lock order.
- Compression, model review, authorization acquisition, and network work occur before exclusive locks.
- Lock acquisition has a finite deadline.
- Failed acquisition releases previously acquired locks.
- Recovery uses the same order and obtains a fresh fencing token.
- No workflow waits for a model decision while holding scheduler or mutation locks.
- No participant can reacquire an earlier lock while holding a later one.

### 6.3 Race and failure handling

| Condition | Required response |
|---|---|
| Epic reopens after planning | Generation/reference mismatch; deny before mutation |
| Task admission races archival | Shared coordination serializes admission against commit; admitted references prevent archival |
| Source changes during compression | Locked revalidation detects mismatch; discard staged candidate |
| Concurrent collectors select same artifact | Exclusive ownership and generation compare-and-swap allow one commit |
| Worker resumes after losing lease | Mutation broker rejects stale fencing token |
| Manifest missing or malformed | Preserve source; deny transition; never infer archive completeness |
| Hash mismatch or unsafe member | Reject candidate; preserve active state; record integrity failure |
| Crash before catalog commit | Sources remain authoritative; published candidate is uncommitted |
| Crash after catalog commit | Verified archive remains authoritative; recovery removes redundant source only after revalidation |
| Audit storage unavailable before commit | Deny mutation |
| Completion logging fails after commit | Recover from durable intent and catalog state; report recovery required |
| Symlink or path substitution | Reject using no-follow access and locked identity verification |
| Unknown scheduler or pin state | Fail closed |
| Existing archive destination | Verify transaction identity for idempotent retry; otherwise deny collision |

No failure path may fall back to blind deletion.

### 6.4 Activation acceptance criteria

AGC MUST remain disabled until focused tests demonstrate:

- Active, queued, reviewing, and promotion-pending work cannot be archived.
- Concurrent admission and collection preserve reference safety.
- Stale workers cannot mutate protected paths.
- Crash injection at every transaction boundary preserves recoverable evidence.
- Corrupt manifests and payloads block source removal.
- Restore reproduces original pre-compression SHA-256 values.
- Non-Opus callers cannot mutate architectural Markdown, including through moves or extraction.
- Modularization preserves every ratified section and invariant.
- Pruned artifacts retain valid evidence locators and commit-trailer provenance.
- Canonical I-65 compatibility is explicitly ratified.

Test scripts belong under `testscript/`. Activation evidence MUST identify tested revisions, exact gate results, and unresolved limitations.

**Ratification condition:** Claude Opus must incorporate the approved specification into canonical modules and authorize the corresponding protected-path migration before AGC mutation capability is enabled.

