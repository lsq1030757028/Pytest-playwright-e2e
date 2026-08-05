# UX1 TodoMVC Mutation Proof Runner

> Status: `MERGED / CLOSED`  
> Goal: Issue #36  
> Pull request: #37  
> Merge commit: `2b5bc958e5c302cef8649e28ff13d8ebafa3afcc`  
> SPEC: `SPEC-UX1-TODOMVC-MUTATION-PROOF@1.0.0`  
> Parent runtime: `UX0-SYNTHETIC-USER-SHADOW@1.0.0`  
> Mandate: `MANDATE-AUTONOMY-M1-M3@1.0.0`  
> Assurance: `DEV3 / UX3`  
> Runtime mode: `SHADOW`  
> Release effect: `NONBLOCKING_SHADOW`  
> Human UAT: `REQUIRED`

## Purpose

The UX1 Runner proves that the merged Synthetic User Shadow Runtime detects bounded user-experience regressions, not only healthy journeys.

For each catalogued mutation it executes:

```text
Materialize isolated pinned TodoMVC checkout
→ verify revision, source inventory and clean tree
→ Baseline affected journeys PASS
→ apply exactly one declared text replacement
→ verify exact postimage and changed-file boundary
→ Mutated affected journeys fail the declared Experience Oracle checkpoints
→ classify KILLED or SURVIVED without AI authority
→ restore exact original bytes in a recovery-safe flow
→ verify preimage hash and clean Git tree
→ Restored affected journeys PASS
→ write artifact and replay manifests
→ independently replay the semantic proof
```

The campaign passes only when all five critical mutations are killed, every healthy phase passes, source restoration is exact, Critical False Green is zero, hidden metadata leakage is zero, and independent replay reproduces the semantic verdict.

## Implemented components

### Frozen contracts

`src/test_workflow/ux_mutation/models.py` defines target source inventory, mutation catalog, phases, outcomes, proof states, transition/patch/phase evidence, per-mutation results, campaign metrics/verdict and artifact/replay manifests.

The loaded catalog binds every mutation to the pinned mutable-file Git blob and required-unmodified file inventory so runtime execution cannot omit the SPEC source boundary.

### Catalog and plan loading

`src/test_workflow/ux_mutation/catalog.py` loads the UX1 campaign, merged mutation catalog and existing UX0 campaign. It validates SPEC, parent runtime and mandate references, target revision pins, selected mutation IDs, Journey/Oracle/checkpoint mappings, target manifest consistency, SHADOW mode, nonblocking release effect and Human UAT.

### Disposable target sandbox

`src/test_workflow/ux_mutation/sandbox.py` enforces relative paths, traversal denial, symlink rejection before resolution, target containment, clean preimage worktree, mutable/required-unmodified Git blob inventory, exact Search/Replacement/preimage/postimage hashes, replacement count = 1, declared-file-only mutation, byte-for-byte restoration and clean Git status.

Recovery restores saved original bytes even when the mutated phase raises. Failure to restore makes the proof `INVALID`.

### Three-phase runner

`src/test_workflow/ux_mutation/runner.py` reuses the merged UX0 Playwright execution and deterministic evaluator. It runs only affected Journeys and records per phase:

- UX report and semantic digest;
- Playwright Trace, screenshot and semantic snapshot;
- state and interaction events;
- actor-input hashes;
- failed checkpoints;
- target file hash and changed-file list;
- target logs and clean-tree status.

Mutation ID, patch and expected failures never enter actor input. AI Candidate Findings remain supplemental and cannot convert a surviving mutation into a kill.

### Stable UX0 route observation

`src/test_workflow/ux/execution.py` waits for the TodoMVC hash route and two animation frames before evaluating the completed-filter state. This removed a real healthy-baseline race without weakening the Oracle: UXM-005 still settles to the mutated active route and is killed deterministically.

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

The default workspace is under the system temporary directory rather than the repository. Invalid, blocked and non-PASS campaign verdicts exit nonzero.

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

A surviving mutation still restores before terminal failure:

```text
MUTATED_RUNNING
→ RESTORING
→ RESTORE_VERIFIED
→ MUTATION_SURVIVED
```

Terminal failures cannot transition to PASS.

## Five verified mutations

1. `UXM-001 / MISSING_FEEDBACK`
2. `UXM-002 / VISIBLE_SUCCESS_STATE_LOSS`
3. `UXM-003 / KEYBOARD_FOCUS_SEMANTIC_BARRIER`
4. `UXM-004 / INTERRUPTED_RESUME_FAILURE`
5. `UXM-005 / FILTER_ROUTE_STATE_DRIFT`

Each mutation is an exact-text replacement against the pinned `index.html` preimage in a separate disposable checkout.

## Evidence

### Focused Unit / Contract

`tests/unit/test_ux_mutation_runtime.py` covers catalog and target pins, source-inventory binding, exact mutation/restoration, blob drift rejection, symlink rejection, repository/workspace isolation, survived-mutation recovery order and illegal transitions.

`tests/unit/test_ux1_mutation_delivery_status.py` binds live status, implementation ledger, protected boundaries and cleanup facts.

### Real target integration

`tests/integration/test_ux_mutation_proof_integration.py` executes the five real mutations, healthy Baseline and Restored phases, automatic replay before report persistence, explicit manifest replay and artifact tamper rejection.

### Dedicated GitHub Action

`.github/workflows/ux1-todomvc-mutation-proof.yml` runs focused lint, Unit/Contract, CLI validation, real five-mutation Playwright proof, independent replay/tamper rejection and evidence upload.

### Final delivery evidence

```text
Goal：Issue #36 — CLOSED
Implementation PR：#37 — MERGED
Implementation Merge：2b5bc958e5c302cef8649e28ff13d8ebafa3afcc
Final PR UX1 Gate：Run #16 / 31002474167 — SUCCESS
Final PR Full Quality：Run #173 / 31002474184 — SUCCESS
Main UX1 Gate：Run #17 / 31002717005 — SUCCESS
Main Full Quality：Run #174 / 31002716954 — SUCCESS
Release：Run #14 / 31002716980 — SUCCESS
Cleanup：Run #12 / 31002717017 — SUCCESS
Implementation Branch：DELETED
Focused Unit / Contract / Delivery：10 / 10 PASS
Real Integration：1 / 1 PASS
Real Mutation Campaign：5 / 5 KILLED
Baseline False Positive：0
Critical False Green：0
Exact Restore：100%
Independent Replay：100%
Oracle Coverage：100%
Journey Coverage：100%
Hidden Metadata Leakage：0
Undeclared Changed Files：0
AI-only Kills：0
Main UX Artifact：8929019254
Main UX Artifact Digest：sha256:c7e5f7e9ce4e2190c7e043765b3176fcc459782439f58c472954de417396c1fa
Main Semantic Digest：sha256:0ec56a6ca9f0b5f2c9b4564b5bc173df7f0621e32a15d1d84fa8711dad1c6322
Main Artifact Manifest Digest：sha256:34c8915bccb010a814b7783f43db25bcaf320c8a4634497e3eb70a4417622fed
Python Distribution：8928961328
Python Digest：sha256:bd18044e8fa442c54afb0e1d4e90d25e0caec81fc07b7b1be6b7152a2880d086
Docker Build Record：8928992374
Docker Digest：sha256:5e857db4bfe699961cb3d6934926e8587728763d5422c3f5c93ccb3dfb0f4761
Image Digest：sha256:e119014c9810d745ff989bf5b46f5aa19f71acf094e854130c968a26d2aa10ac
Image Config：sha256:7f6d6488d9562074a53ac0acd0de8768d93764b2c2bf1757a400ea0d2023287e
```

## Protected boundaries

- Target writes are limited to disposable local pinned checkouts.
- Repository, remote service, production environment and customer data writes are forbidden.
- Arbitrary commands, Regex mutations, traversal and symlink escape are forbidden.
- AI-only findings cannot count as kills.
- Experience Oracle and expected failures remain hidden from the acting Synthetic User.
- Runtime remains `SHADOW`; release effect remains `NONBLOCKING_SHADOW`.
- Advisory and Blocking remain disabled.
- Human UAT remains required.
- M1A remains the project main module; the M1 Memory Gate remains open.

## Rollback and recovery

- Runtime rollback: revert merge commit `2b5bc958e5c302cef8649e28ff13d8ebafa3afcc` or disable the dedicated UX1 workflow.
- Per-mutation recovery: restore saved original bytes, terminate target/browser processes and verify clean Git status.
- Historical evidence remains hash-verifiable.
- No production schema, data or irreversible external resource is changed.

## Next module

```text
UX False-positive / False-negative Benchmark SPEC
→ deterministic benchmark runtime and replay
→ promotion review for ADVISORY candidate only
```
