# Parallel Work Claims Test Design

> Test Design ID: `TEST-DESIGN-PARALLEL-WORK-CLAIMS@0.1.0`  
> SPEC: `SPEC-PARALLEL-WORK-CLAIMS@0.1.0`  
> Goal: Issue #55  
> Profile: `DEV3 / UX0`

## Risk statement

The feature can create silent repository corruption if two executors believe they own the same Work Item, if dependency checks are stale, or if integration work is parallelized accidentally.

## Threat model

| Threat | Required defense |
|---|---|
| Two allocators read the same registry | one CAS winner; loser rereads at most once |
| Two different Work Items share one exclusive domain | second claim rejected |
| Two claims point to the same branch or PR | second claim rejected |
| Old executor resumes after expiry/takeover | per-mutation claim-token fencing |
| Human changes a claimed branch | branch-head mismatch causes `REPLAN_REQUIRED` |
| Expired claim still has active CI | stale recovery refuses takeover |
| Partial registry update | schema validation and all-or-nothing replacement |
| Integration executor overlaps module work | separate integration lease and state gate |
| Parallelism hides failed evidence | module/group/final gates remain mandatory |
| Engineering control is misreported as product M4 | machine invariant `product_m4_claim: false` |

## SPEC-phase obligations

- both YAML files parse;
- all Work Item IDs and exclusive domains are non-empty;
- Work Item IDs are unique;
- every dependency references an existing Work Item;
- dependency graph is acyclic;
- every Work Item has exactly one integration group that exists;
- `READY` items have satisfiable current authority and no unresolved listed dependency;
- M1B remains blocked by M1A closure;
- M2 remains blocked by M1 Gate;
- M3 remains blocked by M2 completion;
- M4 is not introduced as an active Work Item;
- integration and release domains remain serialized;
- Markdown and YAML reference the same SPEC and authority IDs.

## Implementation-phase obligations

1. deterministic selection under identical registry and work-map revisions;
2. one winner and one explicit CAS conflict for simultaneous claim attempts;
3. two independent domains active together;
4. duplicate domain, branch and PR rejection;
5. claim heartbeat and expiry;
6. stale recovery with active-branch and active-CI counterexamples;
7. claim-token and expected-head fencing before every mutation;
8. integration queue ordering;
9. one integration lease holder;
10. disable-task recovery and legacy global-lease rollback.

## Acceptance campaign

The bounded acceptance campaign must contain at least:

- independent claim A: `parallel-delivery-control`;
- independent claim B: `memory-runtime-contracts` or `ux-benchmark`;
- conflicting claim C against one active domain;
- stale claim with no activity that is recoverable;
- expired claim with running CI that is not recoverable;
- unexpected branch-head movement;
- integration queue with two eligible entries;
- task disablement before the next scheduled trigger.

Every scenario records registry revision, claim token, selected Work Item, rejected candidates, reason, branch head and final state.

Critical False Green target: `0`.
