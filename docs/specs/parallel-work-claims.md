# Parallel GitHub Work Claims and Integration Queue SPEC

> SPEC ID: `SPEC-PARALLEL-WORK-CLAIMS@0.1.0`  
> Goal: Issue #55  
> Parent Relay Goal: Issue #49  
> Status: `CANDIDATE`  
> Authority: `OWNER-AUTH-PARALLEL-WORK-CLAIMS-M1-M3@1.0.0`  
> Standing mandate: `MANDATE-AUTONOMY-M1-M3@1.0.0`  
> Assurance: `DEV3 / UX0`

## 1. Business outcome

The human collaboration Chat and scheduled Relay Runtime can progress different M1–M3 Work Items at the same time without editing the same branch, PR, files, release state or project status.

The development system changes from:

```text
one repository-wide long-running lease
→ one active developer
→ all other invocations wait
```

to:

```text
approved product Work Item map
→ atomic claim of one ready Work Item
→ independent branch / PR / evidence
→ staged integration queue
→ serialized main / release / status closure
```

This is an engineering delivery optimization for M1–M3. It does not implement or claim the Test Agent OS product milestone M4.

## 2. Scope

This SPEC defines:

- the authoritative product Work Item map and dependency graph;
- Work Item readiness, claim, progress and integration states;
- atomic claim allocation using GitHub compare-and-swap;
- conflict domains that prevent overlapping writes;
- per-claim heartbeat, expiry, stale recovery and fencing;
- branch-head fencing for each claimed Work Item;
- a separate serialized integration lease;
- module, integration-group and final-stage verification;
- migration rules for human and scheduled Relay prompts.

It does not authorize:

- concurrent changes to the same PR or branch;
- direct writes to `main`;
- bypassing failed CI, Review, Evidence, Release or Human UAT gates;
- product-runtime multi-Agent orchestration;
- M4, M5 or M6 capability claims;
- production/personal data, Secrets or irreversible external actions.

## 3. Durable sources of truth

| Concern | Authoritative source |
|---|---|
| Product modules and dependencies | `docs/product-work-map.yaml` on `main` |
| Human-readable module plan | `docs/product-work-map.md` on `main` |
| Goal, scope and owner authority | Issue #55 |
| Work Item details and lifecycle | linked Issue / SPEC / PR |
| Active claims and claim sequence | control branch claim registry |
| Branch and PR evidence | GitHub branch, PR, checks and artifacts |
| Integration order | control branch integration queue |
| Final product state | `main`, status and ledgers |

Chat history is never authoritative project or claim state.

## 4. Work Item contract

Every claimable Work Item must declare:

- stable `work_item_id`;
- milestone and business outcome;
- lifecycle phase: `SPEC`, `IMPLEMENTATION`, `EVIDENCE`, `INTEGRATION` or `CLOSURE`;
- current state;
- priority;
- dependency Work Item IDs;
- authority Issue and required SPEC;
- target branch and PR when known;
- exactly one `exclusive_domain`;
- optional read-only observation domains;
- expected file or subsystem scope;
- assurance and UX profiles;
- independent completion checks;
- integration group;
- rollback or recovery action.

A Work Item is not claimable when any required field is absent or its dependency is not satisfied.

## 5. Work Item states

```text
PLANNED
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
BLOCKED
OUT_OF_MANDATE
FAILED
CANCELLED
```

Rules:

- `READY` means dependencies and authority are satisfied.
- `CLAIMED` means an atomic claim exists but development has not yet produced a durable checkpoint.
- `IN_PROGRESS` requires a branch or PR checkpoint.
- `EVIDENCE_READY` requires the Work Item's own checks to pass.
- `INTEGRATION_WAITING` means no further module write is allowed except evidence repair.
- `INTEGRATING` requires the integration lease.
- `CLOSED` requires main, release/status and cleanup evidence where applicable.

## 6. Claim registry

Operational mutable state remains on the non-merge control branch:

```text
branch: ops/hourly-github-relay-control
registry: .agent/relay/work-claims.json
integration lease: .agent/relay/leases/integration.json
```

The approved work definitions remain on `main`; only active operational claims and queue entries live on the control branch.

The claim registry contains:

- schema version and monotonic `claim_sequence`;
- active claims keyed by `work_item_id`;
- claim token, surface, target branch, expected head and PR;
- exclusive domain;
- start, heartbeat and expiry timestamps;
- current phase and last checkpoint;
- pending integration queue entries.

## 7. Atomic claim allocation

An executor must:

1. read `main` Work Item definitions and current GitHub state;
2. fetch the claim registry and retain its blob SHA;
3. expire only claims proven stale by the recovery rules;
4. build the candidate set whose dependencies are satisfied;
5. remove already claimed items;
6. remove items whose exclusive domain is held by another active claim;
7. choose the highest priority candidate, using stable Work Item ID as the tie-breaker;
8. append the claim and increment `claim_sequence` in one CAS update;
9. derive a unique claim token from Work Item ID, sequence and UTC start time;
10. reread and verify the exact claim before any development mutation.

A CAS conflict means the allocator changed. The executor may reread and attempt selection once. It must not retry in a loop.

The registry CAS is short-lived allocation coordination, not a long-running repository lock. Different claimed Work Items may then proceed concurrently.

## 8. Conflict model

Every Work Item has exactly one exclusive domain. Examples:

```text
relay-control-plane
memory-runtime-contracts
memory-store-retrieval
ux-benchmark
model-generalization
project-generalization
integration-main
release-status
```

Two active claims with the same exclusive domain are forbidden.

Separate domains may still be declared incompatible in the Work Item map when they share an unavoidable file, generated asset or external environment. The allocator must reject a candidate when either direction of an incompatibility is active.

The following are always serialized:

- the same branch or PR;
- `main` integration;
- package/image release;
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

- after each meaningful state transition;
- before a long CI wait;
- at least every 45 minutes during active work.

An expired claim is recoverable only after checking:

- recent branch or PR activity;
- current queued or running CI;
- the claim's last checkpoint;
- whether a human or another authorized actor changed the branch.

Recent activity keeps the claim protected. A clearly abandoned claim may be marked `STALE_RECOVERED`; its branch must not be reset or overwritten.

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
→ main/release/status verification
```

Priority inside the integration queue is:

1. security or correctness repair;
2. dependency-unblocking module;
3. oldest eligible entry;
4. stable Work Item ID.

A failed integration returns the item to `REPLAN_REQUIRED` or `BLOCKED`; it does not weaken the gate or modify another item's accepted evidence.

## 12. Verification strategy

Three verification levels are mandatory:

1. **Module verification** — each Work Item proves its own contracts and risks.
2. **Integration-group verification** — related modules are tested together when a group reaches its declared boundary.
3. **Final stage verification** — M1, M2, M3 and global safety gates are replayed before stage delivery.

Parallel development never changes the required evidence. It only overlaps independent work.

## 13. Initial execution policy

During migration:

- the existing repository-wide Relay lease remains the compatibility safety lock;
- the new claim allocator is implemented and tested without enabling parallel production writes;
- acceptance first proves two independent claims and one conflicting rejection in a bounded test;
- after acceptance, human and scheduled executors use Work Item claims;
- the old global lease remains only as a kill switch and for legacy fallback until retired by a later Change Event;
- integration, release and status closure remain serialized from day one.

## 14. Failure modes

The system must fail closed for:

- duplicate Work Item IDs;
- missing or cyclic dependencies;
- missing authority or required SPEC;
- two active claims in one exclusive domain;
- claim token mismatch;
- stale branch head;
- expired claim with recent activity;
- claim registry schema mismatch;
- partial or conflicting integration state;
- scheduled task using the old prompt after migration;
- attempted M4/M5/M6 product claim.

## 15. Acceptance criteria

The implementation is acceptable only when evidence proves:

- deterministic Work Item selection;
- atomic one-winner claim under contention;
- two different exclusive domains can remain active concurrently;
- the same domain and same branch cannot be claimed twice;
- stale recovery preserves active branches and CI;
- every mutation is fenced by claim token and branch head;
- integration and release remain single-owner;
- module, group and final verification levels are recorded;
- bounded receipts remain isolated to the Relay Runtime conversation;
- disabling the scheduled task stops scheduled claims;
- Critical False Green remains 0.

## 16. Rollback and recovery

Rollback is:

1. disable the claim-aware scheduled task;
2. stop new claim allocation;
3. preserve the registry and GitHub evidence;
4. restore the existing global Relay lease behavior;
5. finish or explicitly abandon active branches without force reset;
6. record a Change Event before any new design attempt.

No product data migration is involved.
