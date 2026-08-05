## Goal and scope

- Goal / Issue:
- Business or engineering outcome:
- In scope:
- Out of scope:
- Requirement revision / authority:

## SPEC reference and phase

- Phase: `SPEC` / `IMPLEMENTATION` / `SPEC_ADDENDUM` / `EMERGENCY`
- Approved SPEC ID / version:
- SPEC path and merge commit:
- Does this PR change SPEC semantics: yes / no
- SPEC Change Event / impact assessment when applicable:
- Implementation is blocked until required SPEC is merged: yes / no / not applicable

## Autonomy mandate

- Mandate ID / version: `MANDATE-AUTONOMY-M1-M3@1.0.0` / not applicable
- Mandate status verified: `ACTIVE` / not applicable
- Covered milestone: `M1` / `M2` / `M3` / cross-cutting M1-M3 / not covered
- Covered profile: yes / no
- Out-of-mandate external effects: none / describe blocker
- Separate explicit authority when mandate does not apply:

## Development assurance

- Profile: `DEV0` / `DEV1` / `DEV2` / `DEV3` / `DEV-E`
- Why this profile is sufficient:
- Escalation signals considered:
- Authorization mode: approved Goal / active standing mandate / explicit human authority / blocked

## User experience assurance

- User-facing effect: yes / no / unknown
- UX level: `UX0` / `UX1` / `UX2` / `UX3`
- Affected Journey / Experience Oracle refs:
- Primary Synthetic User Profile:
- ExperienceEnvironment revision:
- Accessibility impact:
- Recovery / interruption / network impact:
- Synthetic User mode: not applicable / SHADOW / ADVISORY / BLOCKING
- Experience evidence selected:
- Experience evidence intentionally skipped and reason:
- Human UAT required: yes / no, with authority:

Unknown user-facing impact defaults to `UX2`. AI-only findings cannot block.

## Change map

| Area / asset | Change | Dependency or blast radius |
|---|---|---|
| | | |

## Acceptance and evidence matrix

| Obligation / acceptance criterion | Failure mode | Selected evidence | Result / artifact |
|---|---|---|---|
| | | | |

## Test and evidence selection

### Executed

- Static / schema:
- Unit / property / contract:
- API / boundary integration:
- Browser / device / E2E:
- Synthetic User Journey / accessibility / recovery:
- Replay / mutation / benchmark / canary:
- Repository regression:

### Intentionally skipped

Describe every relevant layer that was not executed and why another form of evidence is sufficient.

- Skipped evidence:
- Reason:
- Replacement evidence:

## Test and engineering assets

- SPEC / Addendum / Mandate:
- Added:
- Changed:
- Invalidated / requires rerun:
- Retired:
- Test design / Golden / Negative / Adversarial asset paths:
- UX Profile / Journey / ExperienceEnvironment / Trace assets:

## Requirement, Oracle, Experience Oracle, Policy, Permission

- Requirement changed during SPEC or implementation: yes / no
- Oracle changed: yes / no
- Experience Oracle changed: yes / no
- Policy / Permission / Assurance Floor changed: yes / no
- Mandate scope or status changed: yes / no
- Change authority and approval:
- Historical SPEC / journey / evidence impact:

## Deployment, recovery, and rollback

- Runtime / schema / data / model / memory / device / UX Gate impact:
- Deployment path:
- Smoke / probe / canary:
- Rollback or recovery:
- Synthetic User Gate rollback:
- Irreversible effects:

## Review findings and residual risk

- Open blockers:
- Accepted residual risks:
- Assumptions and unknowns:
- Uncovered UX / Human UAT areas:
- Follow-up items with owner and deadline:

## Merge eligibility

- [ ] Goal and scope remain approved.
- [ ] Required SPEC is present, versioned and consistent with this PR.
- [ ] Implementation did not start before the required SPEC was merged.
- [ ] Active mandate covers the Goal, milestone, profile, and SPEC when autonomous DEV3 is used.
- [ ] No out-of-mandate external effect is being executed.
- [ ] DEV and UX assurance profiles are justified and have not been silently downgraded.
- [ ] Affected user journeys and Human UAT needs are stated truthfully.
- [ ] No AI-only UX finding is treated as a blocker.
- [ ] Change-specific functional and experience evidence is sufficient.
- [ ] Required GitHub checks are green.
- [ ] Critical False Green is zero.
- [ ] Review threads and blockers are resolved.
- [ ] Assets, status, and ledgers are truthful.
- [ ] Deployment and rollback are credible.
- [ ] Explicit authority is present only when the active mandate does not cover the change.

Auto-merge eligibility: `ELIGIBLE` / `NOT_ELIGIBLE` / `OUT_OF_MANDATE`

Normative process: `docs/github-development-ssot.md`. UX addendum: `docs/ux-assurance-ssot.md`.
