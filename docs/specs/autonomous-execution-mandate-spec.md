# Autonomous Execution Mandate SPEC

> SPEC ID: `SPEC-AUTONOMY-M1-M3@1.0.0`  
> Status: `ACTIVE_WHEN_MERGED_TO_MAIN`  
> Authority: Goal Issue #23 and repository-owner instruction dated 2026-08-05  
> Assurance: `DEV3`  
> Scope: approved M1–M3 roadmap work

## 1. Goal

Replace repeated per-module human approval with one durable, versioned, revocable standing mandate so the Agent can autonomously complete the approved M1–M3 roadmap while preserving all existing evidence, scope, safety, rollback, and audit gates.

The mandate changes **authorization cadence**, not quality or safety requirements.

```text
Approved Roadmap
+ Active Mandate
+ Approved Module SPEC
+ Profile-specific Evidence
+ Deterministic Review Gate
= Autonomous Merge / Release / Closure
```

## 2. Authority and precedence

The repository owner explicitly authorized autonomous execution:

> 进入自治吧，按规范运行，不需要人类批准。

This authorization is recorded by Issue #23. The mandate becomes active only after this SPEC and machine-readable mandate are merged to `main`.

The mandate is subordinate to:

1. law, privacy, security, and organization-level policy;
2. confirmed production invariants and Oracle;
3. explicit repository Policy and Permission boundaries;
4. approved module SPECs;
5. this mandate.

The mandate cannot silently override a higher-authority conflict.

## 3. Authorized scope

Covered milestones:

- M1 Memory & Controlled Evolution;
- M2 Cross-model Generalization;
- M3 Project / Architecture Generalization.

Covered work:

- Goal, Change Event, SPEC, test design, implementation, review, benchmark, replay, mutation, canary, release, ledger, and cleanup;
- DEV0, DEV1, DEV2, and DEV3 changes inside the covered milestones;
- autonomous PR merge and release after all applicable gates pass.

Covered M1.0 implementation:

- Memory Off / On Campaign Runner;
- deterministic scenario loading;
- retrieval/context evidence capture;
- hidden evaluator boundary;
- metrics and benchmark verdict;
- benchmark artifacts and replay support.

## 4. Preconditions for autonomous DEV3

An in-scope DEV3 change may proceed and merge without repeated human approval only when all are true:

1. the mandate status is `ACTIVE` on `main`;
2. the Goal is within M1–M3;
3. the required Module SPEC is approved and merged to `main`;
4. the PR references mandate ID and SPEC version;
5. the final diff remains inside approved scope;
6. profile-specific test design, threat model, evidence, rollback, and recovery exist;
7. required CI checks pass;
8. unresolved Review Threads and blockers are zero;
9. Critical False Green is zero;
10. status and asset ledgers are truthful;
11. post-merge main, release, and cleanup verification succeeds.

## 5. Out-of-mandate boundaries

The mandate does not authorize autonomous execution of:

- work outside M1–M3 without a recorded scope-extension Change Event;
- real production data writes or personal-data exposure;
- real secrets acquisition, disclosure, or privilege escalation;
- destructive production migration or irreversible external writes;
- material irreversible spending or uncontrolled cloud resource creation;
- dangerous real-device or hardware-fleet actions without an approved bounded Device SPEC, lease, reset, health, and recovery path;
- silent Oracle, production-invariant, legal, Policy-floor, or Permission changes outside an approved SPEC;
- bypassing failed evidence, CI, replay, mutation, benchmark, rollback, or review gates.

These conditions produce `OUT_OF_MANDATE`, `BLOCKED`, or `REPLAN_REQUIRED`.

## 6. Autonomous decision model

```text
Candidate Change
→ Goal / Milestone Scope Check
→ Mandate Active Check
→ Approved SPEC Check
→ DEV Profile and Threat Check
→ Evidence Plan
→ Implementation
→ Independent Deterministic Gates
→ Review
→ Merge
→ Main / Release / Cleanup Verification
```

The Agent may choose implementation details and evidence layers, but may not lower the SPEC, Profile floor, Oracle, Policy, Permission, or release gate to make progress.

## 7. Revocation and expiry

The mandate has no fixed time expiry but remains valid only while:

- status is `ACTIVE`;
- covered milestones remain M1–M3;
- no higher-authority conflict is recorded;
- repository safety invariants remain unchanged.

Revocation requires a versioned Change Event. Revocation prevents new autonomous merges but preserves all historical evidence and already merged audit records.

## 8. Acceptance criteria

- A machine-readable active mandate exists on `main`.
- `AGENTS.md` and GitHub Development SSOT reference it.
- DEV3 supports standing-mandate authorization instead of repeated approval.
- In-mandate DEV3 can auto-merge only after full gates.
- DEV-E production actions remain outside the standing mandate.
- Real secrets, production data, destructive external actions, and irreversible cost remain blocked.
- CI validates mandate scope, status, authority, revocation, and template references.
- M1.0 Benchmark Harness is covered without marking it implemented.

## 9. Rollback

Rollback is a normal Git revert plus mandate status change to `REVOKED`. Any in-flight DEV3 PR must then become `BLOCKED` unless separately authorized.
