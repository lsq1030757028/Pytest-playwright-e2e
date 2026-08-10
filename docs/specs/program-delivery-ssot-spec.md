# Program Delivery SSOT SPEC

> SPEC ID: `SPEC-PROGRAM-DELIVERY-SSOT@1.0.0`  
> Goal: Issue #91  
> Parent Campaign: Issue #65  
> Product Architecture Goal: Issue #66  
> Relay / Parallel Control: Issues #49 / #55  
> Status: `CANDIDATE`  
> Assurance: `DEV3 / UX0`

## 1. Business outcome

The repository has exactly one authoritative answer to **what should be delivered next**.

Every human, interactive Agent and scheduled Relay Runtime must derive the current critical path, active/next product slice and claimable product work from one machine-readable Program Delivery SSOT rather than independently interpreting stale status documents, horizontal roadmaps, work maps, open PRs or the operational claim registry.

This SPEC changes program governance and work selection only. It does not implement the Test Agent runtime and does not re-enable scheduled Relay execution.

## 2. Problem statement

The repository currently contains several durable assets that can imply a delivery order:

- `docs/implementation-status.md`;
- `docs/agent-os-roadmap.yaml` and `docs/agent-os-evolution-roadmap.md`;
- `docs/product-work-map.yaml`;
- the merged `docs/test-agent-runtime-beta-roadmap.yaml` vertical product roadmap;
- `.agent/relay/work-claims.json` on the Relay control branch.

Those assets have different update cadence and different semantic roles. They can disagree without a deterministic authority rule. In particular, an executor following the older horizontal M1→M3 sequence can make a different next-work decision from an executor following Campaign #65 / Goal #66 and the Beta vertical slices.

The control failure is not missing information. It is duplicated ownership of delivery truth.

## 3. Governing authority

This SPEC is authorized by Goal #91 and inherits the product objective from Campaign #65 and Goal #66.

`MANDATE-AUTONOMY-M1-M3@1.0.0` remains unchanged. This SPEC does not widen it. M4–M6 work must continue to cite explicit owner authority from #65/#66 plus an approved module SPEC.

The existing GitHub development, safety, Oracle, Policy and Permission rules remain higher authority than delivery ordering.

## 4. Responsibility split

### 4.1 Authorization plane — `MAY_DO`

Answers whether an action is permitted.

Authoritative inputs include:

1. legal/privacy/security/organization policy;
2. confirmed Oracle, production invariant, Permission and release protection;
3. explicit owner authority;
4. active Mandate;
5. approved Goal;
6. approved Module SPEC.

The Program Delivery SSOT cannot grant authority that these sources do not grant.

### 4.2 Delivery plane — `SHOULD_DO_NEXT`

The planned canonical source is:

```text
docs/program-delivery-ssot.yaml
```

with a human-readable companion:

```text
docs/program-delivery-ssot.md
```

Only the machine-readable Program Delivery SSOT may define:

- top-level product objective;
- product lifecycle state;
- active and next operating slice;
- critical path;
- product slice dependency graph;
- capability lanes and their slice mapping;
- claimable Work Item definitions and product priority;
- blocker relationships;
- next-work selection policy;
- transition state needed before scheduled Relay can run.

### 4.3 Execution ownership plane — `WHO_DOES_IT`

The Relay control branch claim registry owns only mutable execution coordination:

- claim token and executor surface;
- branch / PR / expected Head fencing;
- heartbeat and expiry;
- operational checkpoint;
- integration queue and integration lease state.

The claim registry must never create product priority, change product completion truth or make a blocked Work Item ready.

## 5. Product model

The top-level delivery object is `TEST_AGENT_RUNTIME_BETA` from Campaign #65.

The product is advanced through vertical operating slices:

### BETA-A — Execute an existing governed test pack

A user submits a durable job through the supported CLI, the runtime executes an existing governed Pytest + Playwright pack, preserves evidence and returns a deterministic evidence-backed verdict.

### BETA-B — Generate and execute a bounded test

A requirement becomes a reviewable, Oracle-bound test patch that is validated and executed through the BETA-A path.

### BETA-C — Diagnose, repair test workflow and re-run

A failed run is classified; an authorized test-workflow defect may be repaired within bounded paths/cycles and re-run. A product defect must not be masked by weakening the test.

### BETA-D — Restart and resume with governed context

The same durable job survives runtime restart and resumes without duplicate uncertain effects. Governed Memory may support context; stale/revoked/forgotten Memory remains excluded.

### BETA-E — Two-project Beta acceptance

Two materially different supported projects complete the product journey with release/deployment smoke and Human UAT.

## 6. Capability lanes

M1–M6 are capability lanes, not a mandatory all-horizontal-before-product sequence.

| Lane | Primary product contribution |
|---|---|
| M1 Governed Memory | BETA-D and repeated-job context quality |
| M2 Model normalization / safe degradation | BETA-B, BETA-C, BETA-E |
| M3 Project / architecture adapters | BETA-E |
| M4 Bounded orchestration | only when needed by BETA-B/C |
| M5 Durable runtime / control plane | BETA-A and BETA-D |
| M6 Integrated Beta | BETA-E acceptance |
| UX FP/FN Assurance | BETA-C and BETA-E |

A capability Work Item may run in parallel when safe, but it is not product critical path merely because its lane is numerically earlier.

## 7. Critical-path invariant

Every Work Item promoted to the product critical path must declare at least one of:

- `blocks_slice`: the active/next slice cannot satisfy acceptance without it;
- `closes_slice`: completion directly satisfies a remaining slice gate;
- `unblocks_integration`: it removes a proven integration blocker for the active/next slice.

A horizontal infrastructure Work Item without one of those mappings is `PARALLEL_SUPPORT` or `FUTURE`, never product critical path.

## 8. Deterministic next-work selection

After authorization, safety and active foreign-claim checks, selection priority is:

1. `SECURITY_CORRECTNESS_REPAIR`;
2. direct blocker of the active product slice;
3. work that directly closes the active product slice;
4. dependency-unblocking integration;
5. parallel capability work explicitly mapped to active/next slices;
6. required preparation for the next slice;
7. horizontal infrastructure with no active/next slice blocker mapping.

Within one class, use explicit priority, then stable `work_item_id` as deterministic tie-breaker.

No selector may infer priority from milestone number, file age, PR number, discussion volume or claim-registry sequence.

## 9. Planned canonical schema

The implementation SSOT must minimally contain:

```yaml
program:
  id: TEST_AGENT_RUNTIME_BETA
  campaign_issue: 65
  architecture_goal_issue: 66
  state: PRE_BETA_A

product_slices:
  BETA-A: {state: PLANNED, dependencies: []}
  BETA-B: {state: BLOCKED, dependencies: [BETA-A]}
  BETA-C: {state: BLOCKED, dependencies: [BETA-B]}
  BETA-D: {state: BLOCKED, dependencies: [BETA-A, BETA-C]}
  BETA-E: {state: BLOCKED, dependencies: [BETA-B, BETA-C, BETA-D]}

execution_pointer:
  active_slice: null
  next_slice: BETA-A
  critical_path: []

capability_lanes: {}
work_items: []
selection_policy: {}
source_roles: {}
relay_enablement: {}
```

The final schema may add fields but must preserve one authoritative execution pointer.

## 10. Current transition snapshot

The migration implementation must reconcile live GitHub before writing final state. The SPEC records the latest observed transition, not an immutable claim that future state cannot move.

Observed 2026-08-10 after this SPEC work began:

- PR #87 **merged** to `main` as `9fa07d59f57a7d4bffd25e7252c5172bb97c9933`; the Beta vertical architecture is now an approved repository baseline rather than a pending dependency;
- `docs/test-agent-runtime-beta-roadmap.yaml` is now present on `main` and is an approved product-slice input to be folded into or continuously validated against Program Delivery SSOT;
- the architecture dependency for `BETA-A` is therefore satisfied;
- PR #85 remains the parallel M1C migration-evidence closure lane unless live GitHub changes;
- PR #63 remains the parallel UX FP/FN assurance lane unless live GitHub changes;
- PR #89 remains a bounded repair of the old product work map and must not establish that map as the long-term delivery authority;
- scheduled `Pytest GitHub Relay` remains disabled during governance migration;
- after the Program Delivery control migration, the next runtime product slice is `BETA-A`.

The Program Delivery governance migration is a prerequisite for **automated** BETA-A selection, not evidence that BETA-A has an unresolved architecture dependency.

If live GitHub differs during implementation, the migration enters `REPLAN_REQUIRED` and records the new truth rather than copying this snapshot blindly.

## 11. Source-role migration

The implementation phase must assign each durable source exactly one role:

| Source | Target role |
|---|---|
| `docs/program-delivery-ssot.yaml` | `AUTHORITATIVE_DELIVERY` |
| `docs/program-delivery-ssot.md` | human-readable companion, semantically equivalent |
| `docs/github-development-ssot.*` | `AUTHORITATIVE_PROCESS_AND_SAFETY` |
| `docs/specs/autonomous-execution-mandate.yaml` | `AUTHORITATIVE_STANDING_AUTHORITY` |
| `docs/implementation-status.md` | `GENERATED_VIEW` or manually generated non-authoritative view |
| `docs/agent-os-roadmap.yaml` | `REFERENCE_ARCHITECTURE` / superseded delivery sequence |
| `docs/agent-os-evolution-roadmap.md` | `REFERENCE_ARCHITECTURE_AND_RESEARCH` |
| `docs/product-work-map.yaml` | `SUPERSEDED_DELIVERY_MAP` or generated compatibility view |
| `docs/test-agent-runtime-beta-roadmap.yaml` | approved product-slice input folded into / validated against Program Delivery SSOT |
| `.agent/relay/work-claims.json` | `OPERATIONAL_EXECUTION_STATE_ONLY` |

History must be preserved. Existing approved documents are marked superseded/reference/generated; they are not silently rewritten to pretend they never governed delivery.

## 12. Required repository changes after SPEC approval

Implementation is expected to include, as separate reviewable changes where useful:

1. canonical Program Delivery SSOT Markdown/YAML;
2. `AGENTS.md` read-order and responsibility update;
3. GitHub Development SSOT authority/delivery split;
4. Parallel Work Claims selector-source migration;
5. Hourly Relay prompt/selector migration;
6. source-role markers on old roadmaps/status/work map;
7. deterministic parser/validator/selector;
8. CI consistency gate;
9. derived status rendering or validation;
10. Relay enablement proof.

## 13. Consistency invariants

Implementation CI must fail when any of the following is true:

- more than one source is marked `AUTHORITATIVE_DELIVERY`;
- an authoritative old roadmap contains an independent `next_execution_sequence`;
- human-readable and machine-readable Program Delivery SSOT disagree on active/next slice;
- a critical-path Work Item has no product-slice/blocker mapping;
- a READY Work Item lacks required Goal/SPEC/authority references;
- the claim registry is treated as a source of product priority;
- Relay selector can choose a different product-critical Work Item from the deterministic Program Delivery selector;
- product slice dependencies are cyclic or reference unknown slices;
- a CLOSED slice has an unsatisfied completion gate;
- scheduled Relay is marked enableable before migration/main verification/selector proof are green.

## 14. Relay re-enable gate

Scheduled Relay remains disabled until all are true:

1. Program Delivery SSOT implementation merged to `main`;
2. main Full Quality / security gates are green;
3. delivery-source consistency gate is green;
4. deterministic selector proof is green;
5. current claims/integration queue are reconciled;
6. selector resolves the intended next product implementation to `BETA-A` once its architecture dependency is satisfied;
7. Relay prompt reads Program Delivery SSOT as delivery authority;
8. a bounded read-only/bounded-write acceptance run proves fencing and no stale-map selection.

Re-enable is a separate explicit lifecycle action; merging this SPEC does not enable the task.

## 15. Failure behavior

Fail closed as:

- `REPLAN_REQUIRED` for conflicting delivery sources, stale transition snapshot or dependency disagreement;
- `BLOCKED` for missing Goal/SPEC/authority or failed evidence;
- `OUT_OF_MANDATE` when authorization is absent;
- `LOST_CLAIM` when execution ownership fencing fails.

No failure mode authorizes falling back to chat history or silently selecting from a deprecated roadmap.

## 16. Rollback

Before Relay re-enable, rollback is simply:

- keep the scheduled task disabled;
- preserve branch/PR/claims/evidence;
- revert the unmerged implementation branch if needed.

After a future re-enable, rollback requires:

- disable scheduled Relay first;
- stop new claims;
- preserve claim registry and GitHub audit;
- revert selector/source migration through a reviewed Change Event;
- never force-reset active branches or rewrite evidence.

## 17. SPEC acceptance

This SPEC is ready to merge only when:

- dedicated SPEC validation passes;
- Markdown and YAML contract agree;
- threat model covers split-brain delivery, stale source selection, claim/product truth confusion and unauthorized scope widening;
- test design defines deterministic source-role and selector proofs;
- repository Full Quality, Secret Scan and CodeQL are green;
- review threads/blockers are zero;
- the diff remains SPEC/test-design/threat-model/validation only;
- no runtime selector, existing SSOT authority, Relay prompt or scheduled task behavior is changed in this PR.

Runtime/governance implementation begins only after this SPEC is approved and merged.