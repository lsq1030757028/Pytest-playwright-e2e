# UX1 TodoMVC Mutation Proof Runner

> Status: `IMPLEMENTED / EVIDENCE_PENDING`  
> Goal: Issue #36  
> Pull request: #37  
> SPEC: `SPEC-UX1-TODOMVC-MUTATION-PROOF@1.0.0`  
> Parent runtime: `UX0-SYNTHETIC-USER-SHADOW@1.0.0`  
> Mandate: `MANDATE-AUTONOMY-M1-M3@1.0.0`  
> Assurance: `DEV3 / UX3`  
> Runtime mode: `SHADOW`  
> Release effect: `NONBLOCKING_SHADOW`  
> Human UAT: `REQUIRED`

## Purpose

The UX1 Runner proves that the merged Synthetic User Shadow Runtime can detect bounded user-experience regressions, not only pass healthy journeys.

For each catalogued mutation it executes:

```text
Materialize isolated pinned TodoMVC checkout
→ verify revision, source inventory and clean tree
→ Baseline affected journeys PASS
→ apply exactly one declared text replacement
→ verify exact postimage and changed-file boundary
→ Mutated affected journeys fail the declared Experience Oracle checkpoints
→ classify KILLED or SURVIVED without AI authority
→ restore exact original bytes in recovery-safe flow
→ verify preimage hash and clean Git tree
→ Restored affected journeys PASS
→ write artifact and replay manifests
```

The campaign passes only when all five critical mutations are killed, every healthy phase passes, source restoration is exact, Critical False Green is zero, hidden metadata leakage is zero, and independent replay reproduces the semantic verdict.

## Implemented components

### Frozen contracts

`src/test_workflow/ux_mutation/models.py` defines:

- target source inventory and mutation catalog contracts;
- mutation families, phases, outcomes and proof states;
- transition, patch and phase evidence;
- per-mutation proof results;
- campaign metrics and verdict;
- artifact and replay manifests.

The loaded catalog enriches every mutation with the pinned mutable-file Git blob and required-unmodified file inventory, so runtime checks cannot silently omit the SPEC source boundary.

### Catalog and plan loading

`src/test_workflow/ux_mutation/catalog.py` loads the UX1 campaign, merged mutation catalog and existing UX0 campaign. It verifies:

- SPEC, parent runtime and mandate references;
- target revision alignment with UX0;
- selected mutation IDs;
- affected Journey, Experience Oracle and checkpoint mappings;
- target manifest consistency;
- SHADOW, nonblocking and Human UAT invariants.

### Disposable target sandbox

`src/test_workflow/ux_mutation/sandbox.py` enforces:

- relative paths without traversal;
- symlink rejection before path resolution;
- target path containment inside the disposable checkout;
- clean preimage worktree;
- mutable and required-unmodified Git blob inventory;
- exact preimage, Search and Replacement hashes;
- replacement count exactly equal to one;
- exact postimage hash;
- only the declared file changed;
- byte-for-byte restore and clean Git status.

Recovery calls restore from saved original bytes even when the mutated phase raises an exception. Failure to restore makes the proof `INVALID`.

### Three-phase runner

`src/test_workflow/ux_mutation/runner.py` reuses the merged UX0 Playwright execution and deterministic evaluator. It runs only the affected Journey set declared by each mutation and records per-phase:

- UX campaign report and semantic digest;
- Playwright Trace, screenshot and semantic snapshot;
- state and interaction events;
- actor-input hashes;
- failed checkpoints;
- target file hash and changed-file list;
- target logs and clean-tree status.

Mutation and expected-failure metadata are not included in the actor input. AI Candidate Findings remain supplemental and cannot convert a surviving mutation into a kill.

### CLI

```bash
uv run test-workflow ux-mutation validate benchmarks/ux/ux1/campaign.yaml

uv run test-workflow ux-mutation run \
  benchmarks/ux/ux1/campaign.yaml \
  --workspace /tmp/test-workflow-ux-mutation \
  --output test-results/ux-mutation

uv run test-workflow ux-mutation replay \
  test-results/ux-mutation \
  --workspace /tmp/test-workflow-ux-mutation-replay
```

The default runtime workspace is under the system temporary directory rather than the repository. `INVALID`, `BLOCKED` and non-PASS campaign verdicts exit nonzero.

## Proof state machine

```text
PLANNED
→ BASELINE_RUNNING
→ BASELINE_PROVEN
→ MUTATION_APPLYING
→ MUTATION_VERIFIED
→ MUTATED_RUNNING
→ MUTATION_KILLED
→ RESTORING
→ RESTORE_VERIFIED
→ RESTORED_RUNNING
→ CLOSED_PASS
```

A surviving mutation still restores before reaching `MUTATION_SURVIVED`:

```text
MUTATED_RUNNING
→ RESTORING
→ RESTORE_VERIFIED
→ MUTATION_SURVIVED
```

Terminal failure states include `BASELINE_FAILED`, `MUTATION_APPLY_FAILED`, `MUTATION_SURVIVED`, `RESTORE_FAILED`, `REPLAY_DRIFTED`, `INVALID_EVIDENCE` and `BLOCKED`. No terminal failure can transition to PASS.

## Five initial mutations

1. `UXM-001 / MISSING_FEEDBACK`
2. `UXM-002 / VISIBLE_SUCCESS_STATE_LOSS`
3. `UXM-003 / KEYBOARD_FOCUS_SEMANTIC_BARRIER`
4. `UXM-004 / INTERRUPTED_RESUME_FAILURE`
5. `UXM-005 / FILTER_ROUTE_STATE_DRIFT`

Each mutation is an exact-text replacement against the pinned `index.html` preimage in a separate disposable checkout.

## Evidence gates

### Focused Unit / Contract

`tests/unit/test_ux_mutation_runtime.py` covers:

- five-mutation catalog and target-pin loading;
- exact mutation and restoration;
- source-inventory rejection;
- symbolic-link rejection;
- repository/workspace isolation;
- survived-mutation recovery order;
- illegal state transitions.

### Real target integration

`tests/integration/test_ux_mutation_proof_integration.py` is designed to prove:

- five real TodoMVC mutations are killed by affected Playwright Journeys;
- Baseline and Restored phases remain green;
- exact restore and hidden-boundary metrics are 100% / zero as required;
- phase traces, screenshots and semantic evidence exist;
- independent replay reproduces the campaign semantic digest;
- artifact tampering is rejected before replay.

### Dedicated GitHub Action

`.github/workflows/ux1-todomvc-mutation-proof.yml` executes:

1. focused lint;
2. Unit / Contract / sandbox / state-machine evidence;
3. CLI validation;
4. real five-mutation Playwright campaign;
5. independent replay and tamper rejection;
6. evidence artifact upload.

## Current evidence status

```text
Implementation: PRESENT
Focused Lint: PASS in an initial PR run
Focused Unit: EVIDENCE_PENDING after a porcelain-path parser repair
CLI Validate: PENDING
Real Five-mutation Campaign: PENDING
Independent Replay: PENDING
Full Repository CI: PENDING
Review Threads: PENDING
Merge: NOT_ELIGIBLE
```

This document must be updated with authoritative run IDs, artifact IDs and semantic digests only after the final focused and full CI executions succeed.

## Protected boundaries

- Target writes are limited to disposable local pinned checkouts.
- Repository, remote service, production environment and customer data writes are forbidden.
- Arbitrary commands, Regex mutations, path traversal and symlink escape are forbidden.
- AI-only findings cannot count as mutation kills.
- Experience Oracle and expected failures remain hidden from the acting Synthetic User.
- Runtime remains `SHADOW` and release effect remains `NONBLOCKING_SHADOW`.
- Advisory and Blocking gates remain disabled.
- Human UAT remains required.
- M1A remains the project main module; the M1 Memory Gate remains open.

## Rollback and recovery

- Runtime rollback: revert the implementation merge or disable the dedicated UX1 workflow.
- Per-mutation recovery: restore saved original bytes in the runner recovery path, terminate browser/target processes and verify clean Git status.
- Evidence remains historical and hash-verifiable after rollback.
- No production schema, data or irreversible external resource is changed.
