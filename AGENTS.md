# AGENTS.md

This file is the mandatory entrypoint for every human or AI agent that changes this repository.

## 1. Read order

Before planning or editing, read:

1. `docs/github-development-ssot.md` — normative GitHub development lifecycle.
2. `docs/github-development-ssot.yaml` — machine-readable policy invariants.
3. `docs/user-communication-ssot.md` — normative cloud-development user communication standard.
4. `docs/user-communication-ssot.yaml` — machine-readable communication invariants.
5. `docs/ux-assurance-ssot.md` — normative user-experience acceptance addendum.
6. `docs/ux-assurance-ssot.yaml` — machine-readable UX assurance policy.
7. `docs/specs/autonomous-execution-mandate.yaml` — active standing authorization.
8. `docs/implementation-status.md` — current project state and next milestone.
9. `docs/agent-os-evolution-roadmap.md` — product and research roadmap.
10. The relevant architecture, SPEC, test-design, and implementation documents for the touched area.

A chat instruction may define or change a Goal, but durable authority must be recorded through a repository Goal, Change Event, SPEC, mandate, or approved policy asset.

## 2. Repository operating model

The repository is developed cloud-first through GitHub:

```text
Goal / Issue
→ risk, impact, and UX triage
→ SPEC branch / PR
→ SPEC review and merge
→ implementation branch / PR
→ change-specific functional and experience evidence
→ GitHub Actions and evidence artifacts
→ review
→ merge to main
→ release verification
→ status and asset ledger
```

`main` is the authoritative code baseline. GitHub Actions results and uploaded evidence are authoritative verification. Local or conversational results are supporting evidence only.

Never push directly to `main`.

## 3. Standing autonomous mandate

`MANDATE-AUTONOMY-M1-M3@1.0.0` authorizes the Agent to execute the approved M1–M3 roadmap without requesting repeated per-module human approval.

Within a covered Goal and approved SPEC, the Agent may autonomously:

- create Goal, Change Event, SPEC, implementation, test, benchmark, and release assets;
- select or escalate `DEV0`—`DEV3` and `UX0`—`UX3`;
- repair evidence-backed failures;
- review and merge eligible PRs after all gates pass;
- publish packages and GHCR images;
- verify `main`, release, ledger, and branch cleanup.

Autonomy changes authorization cadence, not safety requirements. The Agent must still stop with `BLOCKED`, `REPLAN_REQUIRED`, or `OUT_OF_MANDATE` for:

- work outside M1–M3 without a recorded scope extension;
- higher-authority, Oracle, Experience Oracle, production-invariant, Policy, or Permission conflict;
- real production data or personal data;
- real Secret acquisition or disclosure;
- destructive production migration or irreversible external write;
- material irreversible cost or uncontrolled resource creation;
- dangerous real-device or hardware-fleet action without an approved bounded Device SPEC and recovery path;
- failed CI, evidence, replay, mutation, benchmark, rollback, or review gates;
- `DEV-E` production action.

The mandate is versioned and revocable. A revoked or non-covering mandate cannot authorize a new autonomous DEV3 merge.

## 4. SPEC-first module rule

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
- The SPEC and implementation use separate PR phases unless the change is a small `DEV0` or narrowly scoped `DEV1` whose complete inline SPEC remains independently reviewable.
- `DEV-E` requires a minimum emergency SPEC before action and a time-bounded evidence backfill.
- Requirement changes after SPEC merge create a versioned Change Event and impact assessment.
- SPEC completion does not mean module implementation or milestone completion.

## 5. UX Triage and Synthetic User acceptance

Every change must explicitly determine whether it has a user-facing effect.

User-facing changes include UI, interaction, copy, feedback, browser/device journeys, visible business-rule changes, error recovery, interruption, accessibility, and release/UAT readiness.

For each user-facing change:

1. select `UX1`, `UX2`, or `UX3`; use `UX0` only when no user-facing behavior changes;
2. identify affected Journey and Experience Oracle references;
3. pin an `ExperienceEnvironment` with persona, device, locale, network, input, accessibility, fixture, code, browser, evaluator, seed, time, and step revisions;
4. execute the cheapest trustworthy real Playwright journey evidence;
5. keep AI experience findings as non-authoritative Candidates;
6. report Human UAT requirements and uncovered experience risks.

Unknown user impact defaults to `UX2`, not `UX0`.

The SyntheticUserAgent is a governed controller over declared capabilities. It must not:

- narrate hypothetical behavior instead of interacting with the real target;
- infer protected or sensitive demographic traits;
- use biometric emotion recognition;
- expose evaluator-only fields or hidden expected actions to the actor;
- turn AI opinion into a blocker;
- replace Human UAT;
- change Requirement, Oracle, Experience Oracle, Policy, Permission, or Release State.

The initial Synthetic User Gate is `SHADOW`. Promotion to `ADVISORY` or `BLOCKING` requires the benchmark, mutation, replay, rollback, and versioned policy conditions in `docs/ux-assurance-ssot.md`.

## 6. Do not use mechanical test rules

Do not automatically require the same unit and integration commands for every change.

For each change:

1. identify affected business rules, contracts, state, data, capabilities, policies, environments, experience journeys, and release surfaces;
2. select and justify `DEV0`, `DEV1`, `DEV2`, `DEV3`, or `DEV-E` and `UX0`—`UX3`;
3. define falsifiable obligations and the cheapest trustworthy evidence;
4. explain selected and skipped layers;
5. escalate when evidence reveals a larger blast radius.

Examples:

- documentation-only changes normally need formatting, schema, link, or policy validation;
- isolated deterministic logic normally needs focused Unit, Property, or Contract evidence;
- API, storage, workflow, capability, process, browser, or device boundaries need real boundary evidence;
- user-facing changes need affected Journey evidence selected by UX level;
- Memory, model routing, asset promotion, Oracle, Policy, Permission, device control, financial, privacy, security, destructive behavior, or UX release-gate promotion requires `DEV3` evidence. An active covering mandate or separate explicit authority is required.

The repository-wide CI suite is a release-protection baseline, not a substitute for change-specific test design.

## 7. Required engineering behavior

Every nontrivial change must make explicit:

- Goal and approved scope;
- SPEC ID/version and mandate reference when applicable;
- change and dependency map;
- DEV and UX assurance profiles with escalation reasons;
- acceptance criteria and test obligations;
- selected functional and experience evidence and skip reasons;
- affected, added, invalidated, and retired assets;
- migration, deployment, rollback, and recovery impact;
- Requirement, Oracle, Experience Oracle, Policy, Permission, mandate, or authority changes;
- assumptions, risks, blockers, residual limitations, and Human UAT needs.

Prefer a small vertical slice that can be independently reviewed and rolled back.

## 8. Truth and safety boundaries

An Agent may propose candidates, but it must not silently:

- change a confirmed Oracle, Experience Oracle, or production invariant;
- lower a Policy floor or assurance level;
- widen Permission;
- promote an assumption into a fact;
- promote Memory, Prompt, Procedure, Skill, test, Capability, or UX Finding into production status;
- delete or weaken assertions to make CI green;
- add fixed sleeps or blind retries to hide nondeterminism;
- modify production data, secrets, devices, or release settings outside approved scope and mandate.

## 9. Requirement and scope changes

```text
Change Event
→ authority and mandate check
→ semantic, risk, and UX classification
→ impact graph
→ invalidate only affected SPEC sections, plans, journeys, assets, and evidence
→ recalculate valid progress
→ recompile remaining work
```

Do not overwrite prior requirements, SPECs, mandates, Experience Oracles, or evidence. Preserve history and mark it `SUPERSEDED`, `REQUIRES_REVIEW`, `REQUIRES_RERUN`, or `REVOKED`.

## 10. Pull Request and merge behavior

A PR is ready only when:

- the approved Goal, SPEC, and mandate scope are represented accurately;
- DEV and UX classifications are truthful;
- required checks are green;
- change-specific functional and experience evidence is sufficient;
- unresolved review threads and blockers are zero;
- assets, deployment, rollback, recovery, Human UAT needs, status, and ledgers are truthful.

The Agent may auto-merge `DEV0`—`DEV3` when the active mandate covers the Goal, profile, and SPEC and all SSOT gates pass. `DEV-E` production actions and out-of-mandate boundaries are never covered by routine auto-merge.

## 11. User-facing cloud development communication

All user-facing progress updates and delivery reports must follow `docs/user-communication-ssot.md`.

Default behavior:

- explain the business outcome before internal implementation detail;
- distinguish `PLANNED`, `IMPLEMENTING`, `IMPLEMENTED`, `VERIFIED`, `MERGED`, `RELEASED`, `CLOSED`, `BLOCKED`, and `FAILED`;
- use unqualified “done” only when the work is `CLOSED`;
- describe the next plan as a business action, its purpose, and its completion standard;
- keep PR, Commit, CI, Artifact, Hash, class, function, and tool details as supporting evidence;
- report only meaningful state changes rather than a chronological tool diary;
- never hide failed, running, queued, unverified, unmerged, unreleased, blocked, out-of-scope, uncertain, or Human-UAT-dependent facts for brevity.

Simple updates should normally fit in one to three sentences. Stage or final reports should normally use no more than four parts: conclusion, implemented business capability, facts and boundaries, and next plan. Expand technical detail when the user requests it or when it changes the business conclusion.

## 12. Completion report

Report completion using concise business language first, then the minimum evidence needed to support the claim:

- business outcome and real lifecycle status;
- most important implemented capabilities;
- tests, journeys, CI, release, and evidence needed to substantiate the status;
- assets added, changed, invalidated, or retired when decision-relevant;
- Human UAT readiness, uncovered areas, residual risks, and next state.

Goal, SPEC, mandate, branch, PR, merge commit, run IDs, artifacts, and hashes belong in the evidence portion or a technical appendix rather than the opening narrative.

The full normative development process is `docs/github-development-ssot.md`. The communication standard is `docs/user-communication-ssot.md`. The UX addendum is `docs/ux-assurance-ssot.md`.
