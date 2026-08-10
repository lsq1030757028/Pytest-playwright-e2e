# Program Delivery SSOT Test Design

> Test Design: `TD-PROGRAM-DELIVERY-SSOT@1.0.0`  
> SPEC: `SPEC-PROGRAM-DELIVERY-SSOT@1.0.0`  
> Goal: Issue #91  
> Profile: `DEV3 / UX0`

## 1. Test objective

Prove that the future Program Delivery control plane has one delivery authority, selects work deterministically, cannot launder authorization through delivery priority, cannot confuse claim ownership with product truth, and cannot re-enable scheduled Relay while stale selectors remain.

This SPEC-phase test design validates the contract only. Runtime selector and migration implementation tests are deferred until the SPEC is approved and merged.

## 2. Truth boundaries

The implementation proof must observe real repository-controlled representations for:

- Program Delivery YAML parsing and schema;
- product slice dependency graph;
- capability-lane mapping;
- Work Item readiness and critical-path mapping;
- source-role registry;
- deterministic selection;
- Relay selector source configuration;
- claim registry as operational-only input;
- source consistency scan.

Tests may use fixture GitHub state for deterministic selector cases, but must not mock away the authority, dependency or claim-product separation being tested.

## 3. SPEC-phase obligations

### O-SPEC-1 — Markdown/YAML contract identity

Assert the machine contract declares:

- SPEC ID/version/status;
- Goal #91, Campaign #65 and Goal #66;
- `SPEC_ONLY` phase;
- scheduled Relay not enabled;
- three responsibility planes.

### O-SPEC-2 — vertical product slices

Assert BETA-A through BETA-E exist with the approved dependency graph:

```text
A
→ B
→ C
A + C → D
B + C + D → E
```

### O-SPEC-3 — capability lanes are not delivery sequence

Assert M1–M6 and UX lanes map to product slices and milestone number is explicitly forbidden as a priority signal.

### O-SPEC-4 — critical-path mapping rule

Assert the contract requires one of `blocks_slice`, `closes_slice`, or `unblocks_integration` before an item can be product critical path.

### O-SPEC-5 — source roles

Assert exactly one planned machine source is `AUTHORITATIVE_DELIVERY` and claim registry role is `OPERATIONAL_EXECUTION_STATE_ONLY`.

### O-SPEC-6 — selection order

Assert security/correctness repair precedes active-slice work and unmapped horizontal infrastructure is last.

### O-SPEC-7 — Relay remains disabled

Assert SPEC merge does not enable Relay and the re-enable gate requires main/security/consistency/selector/claim reconciliation/acceptance proof.

### O-SPEC-8 — phase boundary

Assert the SPEC forbids runtime selector change, current SSOT authority change, Relay prompt change, scheduled task re-enable and product runtime implementation in the SPEC PR.

## 4. Implementation-phase functional obligations

### O-IMP-1 — singleton delivery authority

Fixtures:

1. one canonical Program Delivery source;
2. a second file marked authoritative;
3. no authoritative file.

Expected:

- case 1 validates;
- case 2 fails closed;
- case 3 fails closed for autonomous selection.

### O-IMP-2 — deterministic selection

For identical Program Delivery + authority + claim inputs, two independent selector executions must return identical:

- candidate set;
- exclusion reasons;
- priority class;
- selected Work Item;
- next product slice.

### O-IMP-3 — security repair outranks product slice

Given a valid BETA-A implementation item and an eligible security/correctness repair, select the repair first. Removing the repair condition must then select the BETA-A item.

### O-IMP-4 — horizontal infrastructure cannot jump queue

Given:

- a BETA-A blocker;
- a high-numeric-priority infrastructure item with no slice mapping;

select the BETA-A blocker regardless of infrastructure milestone/priority cosmetics.

### O-IMP-5 — active/next slice mapping

An item mapped only to BETA-D may run as parallel support if safe, but cannot replace a BETA-A critical-path item while BETA-A is active/next unless it also proves a BETA-A blocker.

### O-IMP-6 — claim registry cannot create readiness

Start with a BLOCKED Work Item and an active claim registry entry for it. Selection must keep it blocked. Removing the claim must not change product readiness.

### O-IMP-7 — active foreign claim removes ownership candidate only

A READY Work Item stays product-ready but is excluded from current executor allocation when another valid claim owns its domain/branch/PR. The exclusion reason must be operational conflict, not product BLOCKED.

### O-IMP-8 — authority is independent from priority

A desirable M5/BETA-A Work Item without current explicit authority must resolve to `OUT_OF_MANDATE` even when it is first in delivery order.

### O-IMP-9 — stale source rejection

A generated/reference/superseded file containing an old active-module or next-sequence field must not affect selection. If it is incorrectly marked authoritative, CI must fail.

### O-IMP-10 — live transition reconciliation

Migration must not copy the SPEC snapshot blindly. Test fixture moves one referenced PR/Goal after snapshot creation; reconciler must use current repository state or return `REPLAN_REQUIRED`.

### O-IMP-11 — source-role scan

Repository scan must reject:

- more than one `AUTHORITATIVE_DELIVERY` source;
- a deprecated source without a role marker when it contains selector fields;
- a Relay prompt referring to deprecated delivery source as authoritative.

### O-IMP-12 — human/machine companion consistency

Validate product ID, product state, active/next slice, critical path and source roles match between Markdown rendered/declared summary and YAML.

### O-IMP-13 — closed slice gate integrity

Attempt to mark BETA-A CLOSED while any mandatory completion criterion is false. Validator must reject closure.

### O-IMP-14 — cycle and unknown dependency rejection

Reject product slice or Work Item dependency graphs that are cyclic or reference missing nodes.

### O-IMP-15 — BETA-A selector acceptance

After fixtures represent:

- Beta architecture approved/closed;
- required authority present;
- no security repair;
- no active conflicting claim;

selector must choose the BETA-A implementation path rather than M1D/M1E horizontal continuation.

## 5. Relay migration obligations

### O-RELAY-1 — prompt source

The production Relay prompt must explicitly read Program Delivery SSOT for delivery truth and treat status/roadmap/work-map as generated/reference/superseded according to their roles.

### O-RELAY-2 — claim separation

Relay selection reads Program Delivery first, then uses claim registry only to allocate/remove owned candidates.

### O-RELAY-3 — stale prompt detection

A scheduled prompt that still treats `docs/product-work-map.yaml` as authoritative must fail validation and must not be enabled.

### O-RELAY-4 — enablement state machine

Relay task can move from disabled to enableable only after all declared gates are green. No single merged PR or green module test can bypass the gate.

### O-RELAY-5 — bounded acceptance run

Acceptance must prove:

- unique claim and branch fencing;
- selector agreement;
- no stale-map selection;
- GitHub-only state recovery;
- task can be disabled without residual writes.

## 6. Adversarial / mutation obligations

Kill at least these critical mutations:

1. allow two authoritative delivery sources;
2. allow claim registry priority to override Program Delivery;
3. remove `blocks_slice` mapping requirement;
4. swap security repair below horizontal infrastructure;
5. allow milestone number as a priority signal;
6. allow READY without Goal/SPEC/authority;
7. allow Relay enablement without selector proof;
8. allow deprecated product-work-map fallback;
9. skip live-state reconciliation;
10. treat desired M4–M6 work as automatically covered by M1–M3 Mandate.

Critical mutation survivors must be `0` before Relay re-enable.

## 7. Regression obligations

Implementation changes must re-run risk-relevant existing suites for:

- Parallel Work Claims selection/fencing;
- Hourly Relay conversation isolation and claim behavior;
- GitHub development SSOT validation;
- autonomous mandate validation;
- Full Quality baseline;
- Secret Scan and CodeQL.

Tests are selected because governance and Relay selection are touched, not as a mechanical checklist.

## 8. Evidence outputs

Implementation evidence should include:

- normalized Program Delivery manifest;
- source-role scan result;
- deterministic selector decision trace without hidden chain-of-thought;
- excluded candidate reasons;
- authority decision result;
- claim-conflict result;
- Relay enablement checklist;
- mutation proof manifest;
- CI run references.

Decision traces may contain declared facts, rules and outcomes but must not store hidden reasoning.

## 9. Acceptance thresholds

```text
Authoritative delivery source count = 1
Selector replay equivalence = 100%
Relay/program selector disagreement = 0
Critical path item without slice mapping = 0
READY without authority/SPEC = 0
Claim registry product-priority influence = 0
Deprecated-source selection = 0
Unauthorized M4–M6 execution = 0
Critical mutation survivors = 0
Critical False Green = 0
```

## 10. SPEC-only verification

The initial SPEC PR should run a focused deterministic unit test that parses the YAML and proves the contract-level invariants in Section 3. It must also run the normal repository quality/security checks required by the repository governance.

No implementation behavior is claimed by the SPEC-phase unit test.