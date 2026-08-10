# Parallel GitHub Work Claims and Integration Queue SPEC

> SPEC ID: `SPEC-PARALLEL-WORK-CLAIMS@0.1.0`  
> Goal: Issue #55  
> Parent Relay Goal: Issue #49  
> Status: `CANDIDATE`  
> Authority: `OWNER-AUTH-PARALLEL-WORK-CLAIMS-M1-M3@1.0.0`  
> Standing mandate: `MANDATE-AUTONOMY-M1-M3@1.0.0`  
> Delivery selection addendum: `SPEC-PROGRAM-DELIVERY-SSOT@1.0.0` / Goal #91  
> Assurance: `DEV3 / UX0`

## 1. Business outcome

Human collaboration and scheduled Relay Runtime may progress different non-conflicting **authorized** Work Items at the same time without editing the same branch, PR, files, release state or Program Delivery closure state.

The control model is:

```text
Program Delivery SSOT decides SHOULD_DO_NEXT
+ authorization decides MAY_DO
→ Claim Registry allocates WHO_DOES_IT
→ independent branch / PR / evidence
→ staged integration queue
→ serialized main / release / Program Delivery closure
```

This is engineering delivery coordination. Claim allocation is not product-runtime multi-Agent orchestration and does not itself authorize M4/M5/M6. `MANDATE-AUTONOMY-M1-M3@1.0.0` remains limited to M1–M3; work outside that scope requires explicit recorded authority such as Campaign #65 / Goal #66 plus an approved relevant SPEC.

## 2. Scope

This SPEC defines:

- operational Work Item claim, progress and integration states;
- atomic claim allocation using GitHub compare-and-swap;
- conflict domains that prevent overlapping writes;
- per-claim heartbeat, expiry, stale recovery and fencing;
- branch-head fencing for each claimed Work Item;
- a separate serialized integration lease;
- module, integration-group and final verification;
- migration rules for human and scheduled Relay consumers.

**Product state, dependency priority, active/next slice and next-work order are not owned by this SPEC.** They come from `docs/program-delivery-ssot.yaml`.

It does not authorize:

- concurrent changes to the same PR or branch;
- direct writes to `main`;
- bypassing failed CI, Review, Evidence, Release or Human UAT gates;
- product-runtime multi-Agent orchestration;
- silent expansion of M4, M5 or M6 authority;
- production/personal data, Secrets or irreversible external actions.

## 3. Durable sources of truth

| Concern | Authoritative source |
|---|---|
| **Product state, slices, Work Items, dependencies and priority** | **`docs/program-delivery-ssot.yaml` on `main`** |
| Human-readable Program Delivery view | `docs/program-delivery-ssot.md` |
| Old product work map | `docs/product-work-map.yaml` — `SUPERSEDED_DELIVERY_MAP_OR_COMPATIBILITY_VIEW` only |
| Goal, scope and owner authority | linked Goal / Issue and approved SPEC |
| Active claims and claim sequence | control branch claim registry — `OPERATIONAL_EXECUTION_STATE_ONLY` |
| Branch and PR evidence | GitHub branch, PR, checks and artifacts |
| Integration ownership/order | control branch integration queue / integration lease |
| Final product delivery state | Program Delivery SSOT after main/release evidence |

Chat history is never authoritative project, delivery or claim state.

## 4. Work Item contract

Claimable Work Item definitions come from Program Delivery. At minimum they declare:

- stable `work_item_id` and business outcome;
- lifecycle phase and current state;
- Program Delivery selection class and explicit priority;
- dependency Work Item IDs;
- authority Issue and required SPEC;
- target branch and PR when known;
- exactly one `exclusive_domain`;
- independent completion checks;
- product relation such as `blocks_slice`, `closes_slice`, `unblocks_integration`, or `supports_slices`.

Execution-only metadata may be resolved from a linked Goal/SPEC when a Work Item becomes claimable, but missing authority, required SPEC, branch ownership or conflict information fails closed.

A Work Item is not claimable merely because a claim entry exists. Product readiness is calculated first from Program Delivery and authorization.

## 5. Work Item states

```text
PLANNED / FUTURE
→ BLOCKED | READY
→ CLAIMED
→ IN_PROGRESS
→ EVIDENCE_READY
→ INTEGRATION_WAITING
→ INTEGRATING
→ MERGED
→ RELEASE_VERIFYING
→ CLOSED
```

Exceptional states:

```text
REPLAN_REQUIRED
OUT_OF_MANDATE
FAILED
CANCELLED
```

Rules:

- `READY` is a **product/authority fact from Program Delivery**, not a Claim Registry fact.
- `CLAIMED` means an atomic operational claim exists but development has not yet produced a durable checkpoint.
- `IN_PROGRESS` requires a branch or PR checkpoint.
- `EVIDENCE_READY` requires the Work Item's own checks to pass.
- `INTEGRATION_WAITING` means no further product implementation write is allowed except evidence repair.
- `INTEGRATING` requires the integration lease.
- `CLOSED` requires main, release, Program Delivery/status and cleanup evidence where applicable.

## 6. Claim registry

Operational mutable state remains on the non-merge control branch:

```text
branch: ops/hourly-github-relay-control
registry: .agent/relay/work-claims.json
integration lease: .agent/relay/leases/integration.json
```

The claim registry is explicitly `OPERATIONAL_EXECUTION_STATE_ONLY`. It contains:

- schema version and monotonic `claim_sequence`;
- active claims keyed by `work_item_id`;
- claim token, executor surface, target branch, expected Head and PR;
- exclusive domain;
- start, heartbeat and expiry timestamps;
- operational phase and last checkpoint;
- pending integration queue entries.

It does **not** own Product Slice, product readiness, selection class, critical path or completion truth.

## 7. Atomic claim allocation

An executor must:

1. read and validate `main:docs/program-delivery-ssot.yaml`;
2. obtain the ordered delivery candidate set from Program Delivery selection classes and tie-break rules;
3. independently verify Goal/SPEC/Mandate or Explicit Authority for each candidate before allocation;
4. fetch the claim registry and retain its blob SHA;
5. expire only claims proven stale by recovery rules;
6. remove already-owned Work Items and candidates whose exclusive domain/branch/PR conflicts with another active claim;
7. choose the first remaining candidate **without changing Program Delivery order**;
8. append the claim and increment `claim_sequence` in one CAS update;
9. derive a unique claim token from Work Item ID, sequence and UTC start time;
10. reread and verify the exact claim before any development mutation.

A Claim Registry cannot:

- reorder Program Delivery candidates;
- make a `BLOCKED` item `READY`;
- increase priority because its sequence is newer;
- silently substitute a deprecated `product-work-map` candidate.

A CAS conflict means ownership state changed. The executor may reread and attempt allocation once. It must not retry in a loop.

The registry CAS is short-lived allocation coordination, not a long-running repository lock. Different claimed Work Items may then proceed concurrently.

## 8. Conflict model

Every claimable Work Item has exactly one exclusive domain. Examples include:

```text
program-delivery-control
beta-a-runtime
memory-formation
ux-benchmark
model-generalization
project-generalization
integration-main
release-status
```

Two active claims with the same exclusive domain are forbidden.

Separate domains may still be incompatible when they share an unavoidable file, generated asset or external environment. The allocator must reject the current executor's ownership candidate without changing the Work Item's product readiness.

The following are always serialized:

- the same branch or PR;
- `main` integration;
- package/image release;
- Program Delivery closure/state pointer mutation;
- implementation-status and ledger closure;
- branch cleanup that affects an active Work Item;
- any operation declared as a shared mutable external boundary.

## 9. Fencing before every mutation

Immediately before every GitHub mutation, the executor must reread the claim registry and verify:

```text
claim exists
claim token matches
claim is not expired
work_item_id matches
exclusive domain matches
target branch matches
actual branch head equals expected_head_sha
```

After each self-created Commit, the executor updates `expected_head_sha` through CAS before the next development mutation.

Loss of any fence stops writes with `LOST_CLAIM`, `REPLAN_REQUIRED` or `BLOCKED`. Force push, reset and silent patch replay are forbidden.

## 10. Heartbeat and stale recovery

Default claim duration is 120 minutes. A heartbeat is required:

- after each meaningful execution state transition;
- before a long CI wait;
- at least every 45 minutes during active work.

An expired claim is recoverable only after checking:

- recent branch or PR activity;
- current queued or running CI;
- the claim's last checkpoint;
- whether a human or another authorized actor changed the branch.

Recent activity keeps the claim protected. A clearly abandoned claim may be marked `STALE_RECOVERED`; its branch must not be reset or overwritten.

Recovery changes operational ownership only. It does not change Program Delivery state.

## 11. Integration queue

A Work Item enters `INTEGRATION_WAITING` only after its independent evidence is green.

Integration uses a distinct CAS lease and is serialized:

```text
module evidence
→ integration queue
→ integration lease
→ rebase/merge eligibility check
→ integration-group verification
→ merge
→ main/release verification
→ Program Delivery / generated status closure
```

Priority inside the integration queue remains:

1. security or correctness repair;
2. dependency-unblocking integration;
3. oldest eligible entry;
4. stable Work Item ID.

This queue order governs **integration ownership**, not future product priority.

A failed integration returns the item to `REPLAN_REQUIRED` or `BLOCKED`; it does not weaken the gate or modify another item's accepted evidence.

## 12. Verification strategy

Three verification levels remain mandatory:

1. **Module verification** — each Work Item proves its own contracts and risks.
2. **Integration-group verification** — related modules are tested together when a group reaches its declared boundary.
3. **Product/final verification** — Program Delivery Slice acceptance and global safety requirements are replayed before product closure.

Parallel development never changes required evidence. It only overlaps independent work.

## 13. Program Delivery migration policy

During the Program Delivery migration authorized by Goal #91:

- scheduled `Pytest GitHub Relay` stays disabled;
- `docs/program-delivery-ssot.yaml` becomes the only product selection source after merge;
- `docs/product-work-map.yaml` becomes a superseded/compatibility view and cannot select new work;
- the existing claim registry and integration lease are preserved as operational audit state;
- current claims are reconciled against live GitHub before Relay re-enable;
- a bounded acceptance proof must show the Program selector and Relay selector agree;
- after governance closure the selector must resolve `BETA-A-SPEC` as the next product path when no higher security/correctness item is eligible;
- integration, release and Program Delivery closure remain serialized.

## 14. Failure modes

The system must fail closed for:

- missing or invalid Program Delivery SSOT;
- more than one authoritative delivery source;
- unknown/cyclic product or Work Item dependencies;
- missing authority or required SPEC;
- Program Delivery / Relay selector disagreement;
- a Claim Registry attempt to change product priority/readiness;
- two active claims in one exclusive domain;
- claim token mismatch;
- stale branch Head;
- expired claim with recent activity;
- claim registry schema mismatch;
- partial or conflicting integration state;
- scheduled task using a deprecated product-work-map selector;
- desired M4/M5/M6 work without explicit authority and approved SPEC.

## 15. Acceptance criteria

The migrated implementation is acceptable only when evidence proves:

- Program Delivery is the only priority/readiness source;
- deterministic Work Item selection and replay;
- Claim Registry product-priority influence = `0`;
- atomic one-winner claim under contention;
- two different exclusive domains can remain active concurrently;
- the same domain and same branch cannot be claimed twice;
- stale recovery preserves active branches and CI;
- every mutation is fenced by claim token and branch Head;
- integration and release remain single-owner;
- module/product verification levels are recorded;
- bounded receipts remain isolated to the Relay Runtime conversation;
- disabling the scheduled task stops scheduled claims;
- Critical False Green remains `0`.

## 16. Rollback and recovery

Rollback is:

1. disable the claim-aware scheduled task first;
2. stop new claim allocation;
3. preserve the registry and GitHub evidence;
4. keep Program Delivery as delivery authority unless a reviewed Change Event changes that contract;
5. finish or explicitly abandon active branches without force reset;
6. record a Change Event before any new selector/control redesign.

No product data migration is involved.