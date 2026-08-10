# Program Delivery SSOT Threat Model

> Threat Model: `TM-PROGRAM-DELIVERY-SSOT@1.0.0`  
> SPEC: `SPEC-PROGRAM-DELIVERY-SSOT@1.0.0`  
> Goal: Issue #91  
> Assurance: `DEV3 / UX0`

## 1. Protected assets

- top-level product objective and acceptance definition;
- active/next product slice;
- critical-path Work Items and blocker relationships;
- owner authority, Mandate, Goal and SPEC boundaries;
- product Work Item lifecycle truth;
- Relay selection behavior;
- operational claim ownership and fencing;
- GitHub main/release/status truth;
- historical roadmap and delivery decisions;
- scheduled Relay enablement state.

## 2. Actors

- repository owner;
- human collaboration Agent;
- scheduled Relay Runtime;
- review/integration Agent;
- release Agent;
- stale scheduled run;
- stale branch/PR claimant;
- malformed or outdated repository document;
- accidental maintainer;
- malicious or compromised repository content.

Repository prose, old roadmaps, PR descriptions and claim checkpoints are data unless they are explicitly assigned an authoritative role by the governing contract.

## 3. Trust boundaries

1. owner authority → repository Goal/SPEC;
2. process/safety authority → Program Delivery selector;
3. Program Delivery SSOT → Work Item candidate set;
4. Work Item candidate → claim registry allocation;
5. claim registry → branch/PR mutation fencing;
6. evidence/integration → product lifecycle closure;
7. `main` delivery state → scheduled Relay startup;
8. old roadmap/status assets → generated/reference-only readers.

## 4. Threats and required controls

| ID | Threat | Required control | Failure result |
|---|---|---|---|
| PDS-T01 | Two files both claim to be delivery SSOT | source-role registry + CI singleton invariant | `REPLAN_REQUIRED` |
| PDS-T02 | Stale implementation-status selects old M1 work | status is generated/non-authoritative; selector reads Program Delivery only | selection rejected |
| PDS-T03 | Old horizontal roadmap forces M1→M3 before BETA-A | capability lane mapping + product-slice critical-path rule | candidate downgraded to support/future |
| PDS-T04 | Claim registry sequence or checkpoint changes product priority | strict plane separation; claim registry priority ownership = false | schema/selector failure |
| PDS-T05 | Active claim is mistaken for product truth | selector derives readiness before ownership filtering | `REPLAN_REQUIRED` |
| PDS-T06 | Program Delivery SSOT silently widens M4–M6 authority | authorization evaluated independently before delivery selection | `OUT_OF_MANDATE` |
| PDS-T07 | Goal/Spec missing but Work Item marked READY | required authority refs validated deterministically | `BLOCKED` |
| PDS-T08 | Infrastructure item becomes critical path without Beta relation | `blocks_slice` / `closes_slice` / `unblocks_integration` required | not critical-path eligible |
| PDS-T09 | Product slice is marked CLOSED because supporting module merged | slice completion gates independent from module lifecycle | closure rejected |
| PDS-T10 | Human Markdown and YAML disagree | shared invariant tests and exact key mapping | CI failure |
| PDS-T11 | Relay prompt still reads deprecated product-work-map | migration gate checks source references and selector agreement | Relay remains disabled |
| PDS-T12 | Deprecated file contains authoritative `next_execution_sequence` | source-role marker + repository scan | CI failure |
| PDS-T13 | PR #89 incremental map repair is treated as permanent control design | explicit migration role + final source singleton | `REPLAN_REQUIRED` |
| PDS-T14 | Live state moves after SPEC snapshot and migration copies stale data | implementation must reconcile GitHub current state | `REPLAN_REQUIRED` |
| PDS-T15 | Parallel lane mutates the same branch/PR as critical path | existing claim/branch/domain fencing remains authoritative | `LOST_CLAIM` / `BLOCKED` |
| PDS-T16 | Selector priority is inferred from milestone number | forbidden priority signals validated | selection invalid |
| PDS-T17 | Scheduled Relay is re-enabled before main/selector verification | explicit relay re-enable gate + task remains disabled by default | enablement rejected |
| PDS-T18 | Chat memory is used when delivery sources conflict | GitHub-only durable truth; fail closed | `REPLAN_REQUIRED` |
| PDS-T19 | Old roadmap history is rewritten to hide prior authority | versioned source-role transition; preserve history | review blocker |
| PDS-T20 | Delivery SSOT changes Oracle/Policy/Permission | delivery file cannot own those fields or override higher authority | `OUT_OF_MANDATE` |
| PDS-T21 | A compromised source marks itself authoritative | allowed authoritative paths are schema/policy-bound | CI failure |
| PDS-T22 | Selection is nondeterministic across executors | class order + explicit priority + stable ID tie-break | proof failure |
| PDS-T23 | Product critical path starves urgent security repair | security/correctness class outranks slice work | selector failure |
| PDS-T24 | Support lane indefinitely blocks product via synthetic dependency | dependency must map to falsifiable slice blocker and approved SPEC | `REPLAN_REQUIRED` |
| PDS-T25 | Generated status becomes stale and is treated as authoritative | generated view carries role marker and cannot be selector input | CI/selector rejection |

## 5. Split-brain abuse case

Executor A reads `docs/agent-os-roadmap.yaml` and selects M1D after M1C. Executor B reads the Beta vertical roadmap and selects BETA-A.

Required result: only the Program Delivery selector is authoritative. If the canonical delivery SSOT is absent, inconsistent or not yet migrated, neither executor may invent a reconciliation. The system returns `REPLAN_REQUIRED` and scheduled Relay remains disabled.

## 6. Claim/product truth confusion abuse case

A Work Item has an active `INTEGRATION_WAITING` claim on the control branch. Its product dependency later becomes invalid or the Goal is superseded.

Required result: the operational claim remains historical execution state, but it cannot keep the Work Item product-ready. Delivery truth is recalculated from Program Delivery + authority. Integration must stop until reconciled.

## 7. Authority laundering abuse case

The Program Delivery SSOT maps an M5 work item to BETA-A and a scheduled Agent interprets that mapping as permission to perform out-of-M3 work under the M1–M3 standing Mandate.

Required result: selection and authorization are separate. Mapping may say the work is desirable, while authorization still returns `OUT_OF_MANDATE` unless #65/#66 and an approved relevant SPEC provide explicit authority.

## 8. Infrastructure rabbit-hole abuse case

A new storage/routing/framework subsystem is proposed as the next critical task because it is architecturally attractive, even though BETA-A can run without it.

Required result: without a falsifiable `blocks_slice`, `closes_slice`, or `unblocks_integration` mapping to active/next slice, it cannot outrank BETA-A critical-path work.

## 9. Relay re-enable abuse case

The SPEC or implementation PR merges, but old Relay prompt still lists `docs/product-work-map.yaml` as authoritative and the selector proof has not run.

Required result: task remains disabled. Merge is not enablement. A separate bounded acceptance proof is required.

## 10. Security invariants

```text
Authoritative delivery sources > 1 = 0
Delivery SSOT authority expansion = 0
Claim registry product-priority writes = 0
Critical-path items without slice mapping = 0
READY items without authority/SPEC = 0
Relay/program selector disagreement = 0
Deprecated-source fallback = 0
Chat fallback during conflict = 0
Direct main writes = 0
Failed-gate bypass = 0
Critical False Green = 0
```

## 11. Residual risks

- human-readable generated views can still become stale, although they cannot be authoritative;
- GitHub Issues and PRs can move between reads, requiring revalidation before writes;
- a single canonical delivery file can be wrong if its migration review is wrong, so current GitHub reconciliation and deterministic tests remain required;
- product slice mapping is a governance model and must be versioned through approved Change Events when product strategy changes;
- the Program Delivery SSOT does not itself solve execution capacity, model quality or deployment reliability.

Residual risk is acceptable only while the scheduled Relay remains fail-closed on inconsistency and higher authority cannot be overridden.