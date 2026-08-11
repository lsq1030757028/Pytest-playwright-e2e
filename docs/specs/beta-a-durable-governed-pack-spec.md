# BETA-A Durable Governed Pack Execution SPEC

> SPEC ID: `SPEC-BETA-A-DURABLE-GOVERNED-PACK@0.1.0`  
> Goal: Issue #95  
> Parent Campaign: Issue #65  
> Parent Architecture Goal: Issue #66  
> Parent SPEC: `SPEC-TEST-AGENT-RUNTIME-BETA@0.1.0`  
> Work Item: `BETA-A-SPEC`  
> Phase: `SPEC_ONLY`  
> Assurance: `DEV3 / UX3`

## 1. Business outcome

BETA-A is the first slice that must make the repository behave like a product rather than a collection of testing components.

A user provides a pinned supported project, a bounded objective and an **existing governed Pytest/Playwright pack**. The user can submit a durable job, inspect progress, receive a deterministic evidence-backed result, inspect ordered events, and cancel active work. The same job truth remains queryable after the control process restarts.

BETA-A deliberately does **not** generate tests, diagnose or repair failures, reuse governed Memory, or prove cross-project generalization. Those remain BETA-B through BETA-E.

The user journey is:

```text
pinned project + objective/oracle refs + governed existing pack
→ test-agent job submit
→ durable ACCEPTED job
→ exact collection preflight
→ bounded sandboxed execution
→ immutable evidence bundle
→ deterministic verifier
→ status / events / result
```

Cancellation is a first-class journey:

```text
active job
→ test-agent job cancel
→ durable cancellation request
→ stop future steps + terminate process tree
→ preserve partial evidence
→ verify cleanup
→ CANCELLED only when cancellation truth is proven
```

## 2. Authority and phase boundary

Issues #65 and #66 record explicit owner authority for the M1–M6 path required to deliver `TEST_AGENT_RUNTIME_BETA`. Goal #95 narrows that authority to BETA-A.

`MANDATE-AUTONOMY-M1-M3@1.0.0` remains unchanged and does not cover this M5 slice. This work therefore cites the separate explicit #65/#66 authority and Goal #95. No standing-mandate expansion is implied.

This PR is SPEC-only. It may define contracts, threats, test obligations and implementation boundaries. It must not add BETA-A Runtime behavior.

After this SPEC is merged and post-merge main verification is green, Program Delivery may close `BETA-A-SPEC` and make `BETA-A-IMPLEMENTATION` READY. Scheduled Relay remains disabled.

## 3. Slice scope

### 3.1 Included

- `test-agent job submit/status/result/events/cancel` user contract;
- one internal/operator bootstrap for the single-node runtime;
- pinned GitHub commit validation;
- immutable governed-pack manifest and exact selected test nodes;
- SQLite WAL durable job/event/attempt/lease state;
- content-addressed SHA-256 evidence storage;
- one worker per job and one browser context per attempt;
- exact Pytest collection preflight;
- execution of existing Pytest/Playwright nodes only;
- worker/run-token fencing;
- deterministic evidence completeness and verdict rules;
- safe control-process restart reconciliation;
- truthful cancellation and process-tree cleanup;
- replayable evidence;
- package/container smoke through the documented entrypoint.

### 3.2 Excluded

- requirement-to-test generation;
- test patch generation or modification;
- diagnosis, repair or re-run loops;
- automatic execution retry after a launched attempt;
- governed Memory retrieval/reuse;
- cross-project Beta acceptance;
- autonomous product-code repair;
- arbitrary shell service;
- production/personal data;
- private-repository credential acquisition;
- direct `main` writes;
- scheduled Relay re-enable.

## 4. Product entrypoint

The required user commands remain the parent Beta commands:

```text
test-agent job submit
test-agent job status <job-id>
test-agent job result <job-id>
test-agent job events <job-id>
test-agent job cancel <job-id>
```

The single-node reference profile also needs an operator/runtime bootstrap. The reference contract names:

```text
test-agent runtime serve --state-dir <path>
```

This bootstrap is not the product journey itself. It starts the local durable runtime/worker loop that shares the declared state directory with the job CLI commands. A later HTTP profile may wrap the same control-plane ports without changing BETA-A semantics.

User command output must have a concise human-readable form and a stable JSON form. Default output must not dump unbounded logs.

## 5. Submission contract

A BETA-A submission binds:

- client idempotency key;
- project repository identity;
- immutable commit SHA;
- project profile/version;
- objective manifest/version;
- immutable governed-pack manifest reference;
- permitted test paths;
- permitted runtime capabilities;
- Oracle references;
- environment profile;
- budget profile;
- evidence profile.

The request fingerprint covers every required field.

Rules:

- same key + same fingerprint returns the original job;
- same key + changed fingerprint is an explicit conflict;
- floating refs are rejected;
- missing/stale Oracle authority is rejected;
- a mutable or unknown pack manifest is rejected;
- product-source write permission is rejected;
- free-form shell or Pytest argument strings are rejected.

`submit` returning `ACCEPTED` means only that the durable request exists. It must never be worded or surfaced as a successful test verdict.

## 6. Governed existing-pack contract

BETA-A does not infer test scope from model output. It executes a previously governed pack manifest.

The immutable pack manifest contains at least:

- `pack_id` and `pack_version`;
- project profile reference;
- exact commit SHA;
- framework identifier;
- exact selected node IDs;
- exact required node IDs;
- Oracle binding per required node;
- environment profile reference;
- evidence profile reference.

The manifest is content-hash bound.

Before execution, the runtime performs collection preflight with the same project/configuration boundary used for execution. The collection result is itself persisted and hashed.

A `VERIFIED_SUCCESS` is forbidden if any required node:

- cannot be collected;
- is deselected;
- is skipped;
- is xfailed rather than passed;
- lacks the governed Oracle binding;
- is absent from the final JUnit/evidence set.

This prevents a green process exit from being mistaken for a complete product result.

## 7. Durable state model

BETA-A uses a strict subset of the parent job lifecycle:

```text
DRAFT
→ ACCEPTED
→ READY_TO_EXECUTE
→ EXECUTING
→ VERDICT_READY
→ SUCCEEDED | FAILED | BLOCKED | CANCELLED | TIMED_OUT
```

Every state transition is an append-only durable event with a monotonic sequence and expected job revision. A stale revision is an explicit conflict. Terminal states are immutable.

Verdict-to-terminal-state mapping is deterministic:

| Verdict | Job terminal state |
|---|---|
| `VERIFIED_SUCCESS` | `SUCCEEDED` |
| `PRODUCT_DEFECT` | `FAILED` |
| `TEST_DEFECT` | `FAILED` |
| `ENVIRONMENT_FAILURE` | `FAILED` |
| `INSUFFICIENT_EVIDENCE` | `BLOCKED` |
| `ORACLE_CONFLICT` | `BLOCKED` |
| `POLICY_BLOCKED` | `BLOCKED` |
| `CANCELLED` | `CANCELLED` |
| `TIMED_OUT` | `TIMED_OUT` |

`job result` before a terminal state must report that the result is not ready. It cannot synthesize a tentative verdict from current progress.

## 8. Attempt, lease and execution fencing

An execution attempt has its own lifecycle:

```text
CREATED
→ LEASED
→ STARTING
→ RUNNING
→ COLLECTING_EVIDENCE
→ VERIFYING
→ COMPLETED | FAILED | CANCELLED | TIMED_OUT | ABANDONED_UNCERTAIN
```

After a worker claims an attempt, all attempt/job mutations require the current lease token and expected revision.

Reference defaults:

- heartbeat every 2 seconds;
- lease TTL 10 seconds;
- one execution launch per BETA-A job;
- zero automatic execution retries.

Tests use an injectable clock rather than wall-clock sleeps.

The worker durably records `command_started` **before** spawning the test command. This deliberately prefers a safe false negative over duplicate uncertain execution: if the runtime crashes after that marker, recovery must treat execution as potentially started.

## 9. Restart semantics: BETA-A versus BETA-D

BETA-A proves durable truth and safe reconciliation, not full active-work resume.

On control-process restart:

- `ACCEPTED` with no attempt may continue;
- a pre-launch lease may be reclaimed only after lease expiry;
- a durable `command_started` without terminal attempt evidence becomes `ABANDONED_UNCERTAIN` and **must not be automatically re-executed**;
- if complete immutable evidence exists but the final verifier/result write was interrupted, the deterministic verifier may replay and finalize safely;
- a terminal job returns the existing result unchanged.

An uncertain launched attempt produces a blocked/non-success result with explicit recovery evidence. Full resume of an active execution is BETA-D scope.

This distinction is required to keep duplicate uncertain side effects at zero without pretending BETA-D is already implemented.

## 10. Reference persistence profile

### 10.1 Job store

Reference profile:

- SQLite WAL;
- `synchronous=FULL`;
- explicit schema version;
- persistent state directory;
- transactional expected-revision updates;
- append-only events;
- durable submission fingerprints;
- attempt and worker lease state;
- cancellation requests;
- artifact/verdict references.

Job state is not governed semantic Memory.

### 10.2 Artifact store

Artifacts use a persistent content-addressed filesystem:

```text
write temporary file
→ bounded/redacted content
→ fsync
→ SHA-256
→ atomic finalization
→ immutable manifest reference
```

The runtime must not publish a manifest row that points to an artifact that was not durably finalized.

## 11. Workspace and sandbox boundary

Existing repository tests are executable code and therefore untrusted from the host perspective.

The reference worker boundary requires:

- isolated worker execution;
- pinned project checkout;
- product tree read-only from the Agent/runtime modification path;
- only scratch and evidence locations writable;
- no inherited host Secret environment;
- no host control socket mounts;
- deny-by-default network;
- no path traversal or symlink escape;
- no model/user shell interpolation;
- argv-list process launch only;
- adapter-generated `python -m pytest ...` command family only.

The governed pack selects exact node IDs. User input cannot append arbitrary shell fragments or arbitrary Pytest plugin arguments.

## 12. Execution order

The reference execution pipeline is:

1. validate authority and profile refs;
2. verify pinned project commit;
3. verify governed-pack manifest/hash;
4. verify read-only product-tree boundary;
5. collect exact selected nodes;
6. verify required-node collection and persist collection manifest;
7. acquire attempt lease;
8. persist command manifest;
9. persist `command_started` marker;
10. launch sandboxed Pytest/Playwright argv;
11. collect bounded/redacted logs, JUnit and selected browser evidence;
12. persist immutable attempt evidence manifest;
13. run deterministic verification;
14. finalize the job result.

A product-source diff after the attempt invalidates the attempt and forbids success.

## 13. Evidence bundle

Every valid BETA-A attempt requires:

- submission manifest and request fingerprint;
- complete job event history;
- project commit/profile;
- governed-pack manifest/hash;
- collection manifest/hash;
- command manifest;
- worker identity, lease and Run Token;
- bounded redacted stdout/stderr;
- JUnit;
- environment/dependency manifest;
- artifact index with SHA-256 hashes;
- deterministic verifier output;
- cancellation/timeout evidence when applicable;
- workspace reset/cleanup result;
- replay manifest and instructions.

Playwright screenshots/trace/video and browser console/network/DOM/accessibility evidence are conditional on the evidence profile.

Only successful-attempt retention is forbidden. The final result references the complete evidence set.

## 14. Deterministic verifier rules

The deterministic verifier owns final verdict authority. Model output has no BETA-A verdict authority.

`VERIFIED_SUCCESS` requires all of the following:

- the terminal attempt completed;
- process exit indicates success;
- all required nodes collected;
- all required nodes executed;
- all required nodes passed;
- all required evidence exists;
- every artifact hash verifies;
- project/pack/environment bindings agree;
- no product-source diff exists;
- no Policy or Oracle conflict exists;
- cleanup is verified.

Exit code alone can never produce `VERIFIED_SUCCESS`.

Deterministic failure classification:

- governed assertion failure with valid Oracle binding → `PRODUCT_DEFECT`;
- collection/import/fixture/test-structure failure → `TEST_DEFECT`;
- browser/dependency/runtime/sandbox failure → `ENVIRONMENT_FAILURE`;
- missing/stale/tampered/conflicting evidence → `INSUFFICIENT_EVIDENCE`;
- missing/conflicting Oracle authority → `ORACLE_CONFLICT`;
- forbidden capability/boundary violation → `POLICY_BLOCKED`.

BETA-A does not repair any of these outcomes.

## 15. Cancellation contract

Cancellation is durable and idempotent.

An active cancellation must:

1. persist the cancellation request;
2. prevent new execution steps;
3. revoke the active lease;
4. terminate the worker-owned process tree;
5. allow at most 10 seconds for graceful termination, then force kill;
6. preserve partial evidence;
7. verify process termination and workspace cleanup;
8. only then publish terminal `CANCELLED`.

If the process tree or cleanup cannot be proven safe, the runtime must not falsely report `CANCELLED`. It returns a failure/blocked truth with the cleanup problem visible.

Cancelling an already terminal job is idempotent and returns the existing terminal truth.

## 16. Resource boundaries

BETA-A inherits the parent hard ceilings and tightens retry behavior:

- job wall clock ≤ 45 minutes;
- execution attempt ≤ 15 minutes;
- execution attempts = 1;
- workers per job = 1;
- browser contexts per attempt = 1;
- artifacts ≤ 500 MiB;
- free-form retry count = 0.

Budget exhaustion yields `TIMED_OUT` or another explicit non-success state. Limits are never widened automatically.

## 17. UX3 contract

Affected journey:

```text
start runtime
→ submit job
→ understand ACCEPTED is not success
→ inspect status/events
→ inspect evidence-backed result
→ cancel active work when needed
→ query same durable truth after control restart
```

Implementation evidence must cover at least three behavioral personas:

- first-time engineer;
- scripting/automation user;
- recovery-focused operator.

Critical journey repetitions: at least 3 each, with one adversarial recovery environment.

The CLI must make these distinctions visible:

- accepted vs executing vs verified;
- cancellation requested vs cleanup in progress vs cancelled;
- failed test vs environment failure vs policy/oracle block;
- evidence reference vs raw log dump;
- safe restart recovery vs uncertain execution.

Synthetic User evidence may produce Candidate findings. BETA-A must prepare a Human UAT package, but final Human UAT completion remains a BETA-E / final Beta acceptance requirement.

## 18. Critical mutation proof

Implementation must kill at least these critical mutant families:

1. remove submission-fingerprint rebound rejection;
2. remove expected-revision or worker-lease fencing;
3. remove required-node collection completeness;
4. allow skipped/deselected required nodes to count as success;
5. remove evidence completeness before success;
6. remove artifact-hash verification;
7. remove product-source diff rejection;
8. remove cancellation process-tree proof;
9. automatically re-execute an uncertain restarted attempt;
10. allow exit-code-only success.

Critical survivors allowed: `0`.

## 19. Protected invariants

```text
Critical False Green = 0
Unauthorized product-source write = 0
Unauthorized Oracle / Policy / Permission change = 0
Unverifiable success verdict = 0
Duplicate execution after restart = 0
Idempotency-key rebound accepted = 0
Stale worker state write = 0
Required node missing but success = 0
Artifact hash mismatch but success = 0
Child process survivor after CANCELLED = 0
Secret/personal-data exposure = 0
Unbounded retry/spend = 0
```

## 20. Implementation evidence obligations

The BETA-A implementation phase must produce:

- focused contract/state tests;
- SQLite restart/concurrency evidence;
- CLI contract evidence;
- real Pytest + Playwright execution;
- sandbox boundary evidence;
- process-tree cancellation evidence;
- artifact hash and deterministic replay evidence;
- package/container smoke;
- UX3 journey evidence;
- risk-selected regressions;
- Full Quality, Secret Scan, CodeQL and Release evidence.

No mocked boundary may substitute for the behavior being claimed.

## 21. Deployment, rollback and recovery

The first deployment remains a single-node durable profile.

Implementation must support:

- state-directory schema/version check before intake;
- backup before schema migration;
- fail-closed intake on incompatible state;
- immutable evidence preservation across upgrade/rollback;
- package/container rollback to the last known-good runtime while preserving the compatible state directory;
- no automatic downgrade when the state schema is incompatible.

SPEC rollback is simple: close/revert this SPEC branch/PR before implementation begins. Scheduled Relay remains disabled.

## 22. SPEC exit criteria

This SPEC PR is mergeable only when:

- Markdown/YAML/threat model/test design agree;
- Goal #95 and parent #65/#66 authority are explicit;
- M1–M3 mandate remains unextended;
- no BETA-A runtime implementation is present in the SPEC PR;
- dedicated SPEC CI is green;
- Full Quality, Secret Scan and CodeQL are green;
- Review Threads/blockers are zero;
- the final diff remains SPEC/test-design/threat-model/validation only.

Merging this SPEC does not complete BETA-A. It only authorizes the separately reviewed implementation phase and allows Program Delivery to advance from `BETA-A-SPEC` to `BETA-A-IMPLEMENTATION` after main verification.