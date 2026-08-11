# BETA-A Durable Governed Pack Independent Test Design

> Test Design: `TD-BETA-A-DURABLE-GOVERNED-PACK@0.1.0`  
> SPEC: `SPEC-BETA-A-DURABLE-GOVERNED-PACK@0.1.0`  
> Goal: Issue #95  
> Parent Campaign: Issue #65  
> Assurance: `DEV3 / UX3`

## 1. Purpose

Prove that BETA-A can become a real, user-runnable product slice without falsely claiming the later BETA-B/C/D/E capabilities.

The implementation must show that an existing governed Pytest/Playwright pack can be submitted through the real CLI, persisted durably, executed once within a bounded sandbox, converted into immutable evidence, deterministically verified, cancelled truthfully, and safely reconciled after a control-process restart.

This design separates three evidence questions:

1. **Did the runtime do the declared work?** — execution and lifecycle evidence.
2. **Is the verdict justified?** — required-node, Oracle and artifact evidence.
3. **Can interruption/cancellation create a false or duplicate result?** — restart, lease and process-tree evidence.

## 2. SPEC-phase obligations

The SPEC PR itself must prove:

- Goal #95, parent #65/#66 and parent architecture SPEC are consistently referenced;
- `BETA-A-SPEC` is the scoped Work Item;
- the standing M1–M3 mandate is explicitly unextended and does not claim to cover BETA-A;
- phase is `SPEC_ONLY` and no runtime implementation is claimed by this PR;
- DEV3 and UX3 are explicit;
- BETA-A includes existing-pack execution but excludes generation, repair, governed Memory and cross-project acceptance;
- CLI commands and operator bootstrap are explicit;
- submission idempotency and request rebound rules are deterministic;
- governed-pack required-node semantics prevent partial-pack false success;
- job/attempt lifecycle and terminal verdict mapping are consistent;
- uncertain launched work is not auto-reexecuted after restart;
- sandbox, product-source, Secret and network boundaries remain fail-closed;
- deterministic verifier is the only success authority;
- cancellation cannot publish `CANCELLED` without process-tree/cleanup proof;
- budgets are finite and automatic execution retries are zero;
- critical mutation catalog is complete and survivors allowed are zero;
- Program Delivery transition is BETA-A-SPEC → BETA-A-IMPLEMENTATION only after main verification;
- scheduled Relay remains disabled.

## 3. Implementation evidence matrix

| Obligation | Cheapest trustworthy evidence | Boundary not allowed to mock |
|---|---|---|
| CLI submit/status/events/result | CLI contract + real process invocation | CLI parser/output and durable state |
| request idempotency/rebound | deterministic unit/SQLite integration | persistent fingerprint state |
| durable job/event state | SQLite restart integration | SQLite persistence |
| stale revision/lease fencing | coordinated concurrency test with injected clock | store transaction/fencing logic |
| governed pack completeness | real Pytest collection + JUnit comparison | Pytest collection/execution |
| Playwright execution | real Chromium run | browser runtime |
| product-source read-only | sandbox integration + before/after tree digest | workspace filesystem boundary |
| artifact durability/hash | real content-addressed store + tamper test | filesystem persistence/hash check |
| deterministic verdict | verifier contract + replay | verifier logic/evidence manifests |
| cancellation | real process-tree cancellation | child process lifecycle |
| restart reconciliation | separate runtime processes sharing state dir | process restart and durable state |
| uncertain launch safety | controlled crash after durable command-start marker | launch journal/restart reconciler |
| package/container entrypoint | built package/container smoke | packaged runtime |
| UX3 clarity | real CLI journey evidence | rendered CLI output and actual states |

## 4. Required implementation scenarios

### 4.1 Happy-path existing governed pack

Use a pinned supported project fixture with:

- at least one pure Pytest required node;
- at least one Playwright Chromium required node;
- authoritative Oracle binding;
- immutable governed-pack manifest.

Prove:

1. `submit` returns a durable job ID and `ACCEPTED`, not success;
2. `status/events` expose monotonic truthful progression;
3. exact governed nodes are collected;
4. exactly one execution attempt launches;
5. required nodes execute and pass;
6. JUnit and selected browser evidence are persisted;
7. evidence hashes verify;
8. product source is unchanged;
9. cleanup verifies;
10. deterministic verifier returns `VERIFIED_SUCCESS`;
11. `result` returns the same final revision and evidence references after control-process restart.

### 4.2 Product-defect classification

Run a governed assertion against a seeded product-behavior mutation while keeping the test/fixture valid.

Expected:

- required node executes;
- assertion evidence is complete;
- valid Oracle binding exists;
- verdict = `PRODUCT_DEFECT`;
- job state = `FAILED`;
- BETA-A performs no test or product repair.

### 4.3 Test-defect classification

Use a broken selector, import, fixture or malformed test structure that prevents valid governed execution.

Expected verdict: `TEST_DEFECT` and terminal `FAILED`.

The test must not be silently edited or retried.

### 4.4 Environment failure

Make Chromium/runtime/dependency infrastructure unavailable without changing the governed Oracle.

Expected verdict: `ENVIRONMENT_FAILURE`, not `PRODUCT_DEFECT` and not success.

### 4.5 Insufficient evidence

Delete or tamper with one required artifact after execution but before verification.

Expected verdict: `INSUFFICIENT_EVIDENCE` and terminal `BLOCKED`.

### 4.6 Oracle conflict

Provide missing or conflicting current Oracle authority.

Execution must fail closed before a success verdict; expected `ORACLE_CONFLICT` / `BLOCKED`.

### 4.7 Policy block

Attempt product-source write permission, arbitrary shell/Pytest argument injection, forbidden network access or path escape.

Expected: `POLICY_BLOCKED`, no forbidden side effect, no success.

## 5. Governed-pack false-green matrix

Every case below must prevent `VERIFIED_SUCCESS`:

- required node not found during collection;
- required node deselected by configuration/plugin;
- required node skipped;
- required node xfailed;
- required node absent from JUnit despite process exit `0`;
- duplicate node IDs causing ambiguous manifest semantics;
- collection manifest hash mismatch;
- pack commit differs from submitted commit;
- Oracle binding missing for a required node;
- exit code `0` with incomplete evidence.

At least one controlled test must demonstrate that a naive exit-code-only verifier would falsely pass the fixture while the governed verifier blocks it.

## 6. Idempotency, revision and concurrency proof

### 6.1 Submission idempotency

- same idempotency key + byte-equivalent normalized request → same job/result;
- same key + changed commit/pack/objective/budget/evidence ref → explicit conflict;
- concurrent equivalent submissions → exactly one logical job;
- concurrent rebound submissions → no request substitution.

### 6.2 Job revision

Two writers attempt a transition from the same expected revision. Exactly one may commit; stale writer receives explicit conflict.

### 6.3 Worker lease

Using an injectable clock:

- current lease holder may mutate;
- expired/stale lease token cannot mutate;
- a pre-launch expired lease may be reclaimed;
- a post-`command_started` expired lease cannot authorize automatic relaunch.

No test should rely on fixed real sleeps for these correctness proofs.

## 7. Restart matrix

Use separate runtime processes against the same persistent state directory.

| Crash point | Expected recovery |
|---|---|
| after ACCEPTED, before attempt | continue safely |
| after lease acquired, before command-start marker | reclaim after lease expiry |
| immediately after command-start marker, before spawn confirmation | treat execution as uncertain; do not auto-rerun |
| after spawn while running | uncertain/blocked; do not auto-rerun |
| after complete immutable evidence, before verdict write | deterministic reverify/finalize |
| after terminal result | return existing immutable truth |

Critical invariant: duplicate execution after restart = `0`.

A control test may deliberately remove the uncertain-execution guard to prove that duplicate launch would become possible; the real implementation must kill that mutant.

## 8. Cancellation matrix

Use a real test process that has a child process and a real Playwright browser process.

Prove:

- cancellation request is durable and idempotent;
- new worker steps do not start after cancellation is observed;
- graceful termination is attempted;
- force kill occurs after bounded grace when needed;
- worker-owned child processes are gone;
- browser process/context is gone;
- lease is revoked;
- partial logs/artifacts are retained;
- workspace cleanup is verified;
- only then is job terminal `CANCELLED`.

Negative case: deliberately simulate an unkillable/unverified child/cleanup condition. The runtime must not claim `CANCELLED`; it returns an explicit non-success cleanup truth.

## 9. Sandbox and security proof

The implementation must exercise real boundary probes for:

- product-source write attempt;
- `../` traversal;
- symlink escape;
- inherited secret-like environment access;
- host socket discovery/use;
- undeclared network access;
- user-provided shell fragment;
- arbitrary Pytest plugin/argument injection.

A boundary is not considered proven by validating a string while the real process still receives the forbidden capability.

## 10. Evidence and replay proof

Create a finalized attempt bundle, then replay the deterministic verifier from only declared durable state/artifacts.

Required assertions:

- same verifier result and evidence digest;
- every referenced artifact hash validates;
- project/pack/environment revisions match;
- tampered artifact fails replay;
- deleted required artifact fails replay;
- substituted artifact from another run fails binding;
- partial cancelled attempt cannot be replayed into success;
- original failing/non-success attempt evidence remains available.

## 11. Critical mutation catalog

The implementation proof must kill all required critical mutants:

1. `REMOVE_SUBMISSION_FINGERPRINT_REBOUND_REJECTION`;
2. `REMOVE_EXPECTED_REVISION_OR_LEASE_FENCING`;
3. `REMOVE_REQUIRED_NODE_COLLECTION_COMPLETENESS`;
4. `ALLOW_SKIPPED_OR_DESELECTED_REQUIRED_NODE_SUCCESS`;
5. `REMOVE_EVIDENCE_COMPLETENESS_BEFORE_SUCCESS`;
6. `REMOVE_ARTIFACT_HASH_VERIFICATION`;
7. `REMOVE_PRODUCT_SOURCE_DIFF_REJECTION`;
8. `REMOVE_CANCELLATION_PROCESS_TREE_PROOF`;
9. `AUTO_REEXECUTE_UNCERTAIN_RESTART`;
10. `ALLOW_EXIT_CODE_ONLY_SUCCESS`.

Critical mutation survivors: `0`.

Controlled mutants may be explicit test doubles or toggled implementations, but the mutation evidence must demonstrate the associated unsafe outcome rather than merely assert that a flag changed.

## 12. UX3 journey design

Affected journey:

```text
start runtime
→ submit governed pack
→ understand durable ACCEPTED state
→ inspect status/events
→ distinguish execution from verification
→ inspect verdict/evidence/limitations
→ cancel when needed
→ query the same truth after restart
```

Personas:

1. first-time engineer — needs clear actionable states and evidence locations;
2. scripting/automation user — needs stable JSON and exit semantics;
3. recovery-focused operator — needs uncertainty/cancellation/restart truth.

Each critical journey is repeated at least three times. Include one adversarial environment where runtime interruption or cleanup failure occurs.

UX assertions:

- `ACCEPTED` cannot be mistaken for passed;
- `EXECUTING` cannot be mistaken for verified;
- `BLOCKED` explains why no trusted verdict exists;
- `PRODUCT_DEFECT`, `TEST_DEFECT`, and `ENVIRONMENT_FAILURE` are distinguishable;
- cancellation request, termination and terminal state are distinguishable;
- evidence references are discoverable without dumping raw unbounded logs;
- restart uncertainty is visible rather than hidden.

Synthetic User findings remain Candidate-only. BETA-A prepares a Human UAT package; full Human UAT completion remains BETA-E/final Beta acceptance.

## 13. Package/container smoke

The release evidence must use the documented packaged entrypoint, not a source-tree-only shortcut.

Minimum smoke:

1. start the packaged single-node runtime with a persistent state directory;
2. submit the pinned governed-pack fixture;
3. observe execution and final result;
4. restart the runtime process;
5. query the same job/result;
6. verify evidence references and hashes;
7. run a cancellation smoke against a long-running fixture;
8. verify cleanup.

Package/container smoke failure blocks BETA-A acceptance and release truth.

## 14. Performance and budget evidence

This slice does not set a throughput SLO. It proves hard ceilings:

- job wall clock ≤ 45 minutes;
- attempt ≤ 15 minutes;
- attempts = 1;
- worker/job = 1;
- browser context/attempt = 1;
- artifacts ≤ 500 MiB;
- automatic retry = 0.

Boundary tests should use smaller fixture-specific limits to keep CI cost bounded while proving the same hard-stop mechanism.

## 15. Selected and skipped layers

SPEC phase selects:

- YAML/Markdown structural consistency;
- authority and scope assertions;
- lifecycle/terminal mapping assertions;
- threat/test design presence;
- critical mutation catalog validation;
- dedicated SPEC gate;
- Full Quality, Secret Scan, CodeQL and review.

Implementation phase selects:

- unit/property/contract tests for deterministic state rules;
- SQLite integration/concurrency/restart;
- real CLI/process boundaries;
- real Pytest/Playwright/Chromium;
- real filesystem/artifact tamper;
- real process-tree cancellation;
- real packaged/container smoke;
- UX3 journey evidence;
- replay/mutation proof.

Skipped from BETA-A:

- generated-test evaluation;
- diagnosis/repair evaluation;
- governed Memory benchmark;
- two-project generalization;
- production/personal data;
- private-repository credentials;
- multi-tenant/cloud-scale availability.

## 16. SPEC exit criteria

The SPEC PR is mergeable only when:

- all six SPEC assets agree;
- dedicated BETA-A SPEC gate passes;
- Full Quality passes;
- full-history Secret Scan passes;
- CodeQL passes;
- Review Threads/blockers are zero;
- no Runtime implementation is present in this SPEC PR;
- Relay remains disabled.

After SPEC merge, the merge commit must pass the same applicable main gates before Program Delivery moves `BETA-A-IMPLEMENTATION` to READY.