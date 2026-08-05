# AGENTS.md

This file is the mandatory entrypoint for every human or AI agent that changes this repository.

## 1. Read order

Before planning or editing, read:

1. `docs/github-development-ssot.md` — normative GitHub development lifecycle.
2. `docs/github-development-ssot.yaml` — machine-readable policy invariants.
3. `docs/implementation-status.md` — current project state and next milestone.
4. `docs/agent-os-evolution-roadmap.md` — product and research roadmap.
5. The relevant architecture, SPEC, test-design, and implementation documents for the touched area.

A chat instruction may define the current Goal, but it does not replace repository state, approved requirements, Oracle, Policy, Permission, or this SSOT.

## 2. Repository operating model

The repository is developed cloud-first through GitHub:

```text
Goal / Issue
→ risk and impact triage
→ SPEC branch / PR
→ SPEC review and merge
→ implementation branch / PR
→ change-specific evidence
→ GitHub Actions and evidence artifacts
→ review
→ merge to main
→ release verification
→ status and asset ledger
```

`main` is the authoritative code baseline. GitHub Actions results and uploaded evidence are authoritative verification. Local or conversational results are supporting evidence only.

Never push directly to `main`.

## 3. SPEC-first module rule

Every nontrivial module or independently deliverable behavior change starts with an explicit SPEC before runtime implementation begins.

A module SPEC must define, at the depth appropriate to its risk:

- Goal, approved scope and exclusions;
- authoritative requirements, Oracle and decision authority;
- affected architecture, data, state, interfaces and dependencies;
- safety, privacy, permission and production boundaries;
- falsifiable acceptance criteria and failure modes;
- test obligations, evidence plan and managed assets;
- migration, deployment, rollback and recovery expectations;
- unresolved decisions and implementation boundaries.

Normal path:

```text
Goal
→ SPEC Candidate
→ SPEC Review / CI
→ SPEC merged to main
→ Implementation begins
```

Rules:

- Runtime implementation must not begin before the relevant SPEC is approved and merged.
- The SPEC and implementation must use separate PR phases unless the change is a small `DEV0` or narrowly scoped `DEV1` change whose complete inline SPEC remains independently reviewable.
- A `DEV0` change may use a lightweight inline SPEC in the Goal or PR when there is no runtime or governance effect.
- `DEV-E` may use an emergency SPEC containing the minimum safe scope, risk, evidence, rollout and rollback plan; full SPEC and evidence backfill remain mandatory with a deadline.
- Requirement changes after SPEC merge create a versioned Change Event and impact assessment. Do not silently edit the meaning of an approved SPEC.
- SPEC completion does not mean module implementation or milestone completion.

## 4. Do not use mechanical test rules

Do not automatically require the same unit and integration test commands for every change.

For each change:

1. Identify the affected business rules, contracts, state, data, capabilities, policies, environments, and release surfaces.
2. Select a development assurance profile from `DEV0`, `DEV1`, `DEV2`, `DEV3`, or `DEV-E`.
3. Define falsifiable test obligations and the cheapest trustworthy evidence for each obligation.
4. State why a test layer is selected or skipped.
5. Escalate when new evidence reveals a larger blast radius.

Examples:

- Documentation-only changes normally need formatting, schema, link, or policy validation—not invented unit tests.
- Isolated deterministic logic normally needs focused unit or contract tests.
- API, storage, workflow, capability, or process-boundary changes normally need boundary integration evidence.
- Oracle, Policy, Permission, Memory promotion, model routing, device control, release, destructive data, financial, privacy, or security changes require `DEV3` evidence and human approval.

The repository-wide CI regression suite may still run on every PR. That is a release-protection baseline, not a substitute for change-specific test design.

## 5. Required engineering behavior

Every nontrivial change must make the following explicit in its Issue, SPEC, or PR:

- Goal and approved scope;
- change and dependency map;
- assurance profile and escalation reasons;
- acceptance criteria and test obligations;
- selected evidence and skipped evidence with reasons;
- affected and newly created assets;
- migration, deployment, rollback, and recovery impact;
- requirement or Oracle changes;
- unresolved assumptions, risks, and blockers.

Prefer a small vertical slice that can be independently reviewed and rolled back. Do not create large speculative frameworks without an executable acceptance path.

## 6. Truth and safety boundaries

An agent may propose candidates, but it must not silently:

- change a confirmed Oracle;
- lower a Policy floor or assurance level;
- widen Permission;
- promote an assumption into a fact;
- promote Memory, Prompt, Procedure, Skill, test, or Capability into production status;
- delete or weaken assertions to make CI green;
- add fixed sleeps or blind retries to hide nondeterminism;
- modify production data, secrets, devices, or release settings outside approved scope.

Any such change requires explicit authority, dedicated evidence, and the approval rules in the SSOT.

## 7. Requirement and scope changes

When a requirement changes during or after SPEC implementation:

```text
Change Event
→ authority check
→ semantic and risk classification
→ impact graph
→ invalidate only affected SPEC sections, plans, assets, and evidence
→ recalculate valid progress
→ recompile remaining work
```

Do not overwrite prior requirements, SPECs, or evidence. Preserve history and mark it `SUPERSEDED`, `REQUIRES_REVIEW`, or `REQUIRES_RERUN` as appropriate.

## 8. Pull Request and merge behavior

A PR is ready only when:

- the approved Goal and SPEC are still represented accurately;
- required checks are green;
- change-specific evidence is sufficient for the selected assurance profile;
- no unresolved review thread or blocker remains;
- test, replay, benchmark, migration, and release assets are registered where applicable;
- deployment and rollback are credible;
- status and ledger changes are truthful.

Within an already approved Goal, an agent may auto-merge an eligible `DEV0`, `DEV1`, or `DEV2` PR after all SSOT gates pass. `DEV3`, emergency production actions, Oracle/Policy/Permission changes, secrets, real-device fleet changes, destructive migrations, and release-control changes require explicit human approval.

## 9. Completion report

Report completion using evidence, not confidence language:

- Goal, SPEC, branch, PR, and merge commit;
- assurance profile;
- tests and evidence actually executed;
- CI and release run IDs;
- artifacts and hashes when relevant;
- assets added, changed, invalidated, or retired;
- remaining risks, assumptions, and next state.

The full normative process is `docs/github-development-ssot.md`.
