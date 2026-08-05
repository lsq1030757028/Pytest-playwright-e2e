## Goal and scope

- Goal / Issue:
- Business or engineering outcome:
- In scope:
- Out of scope:
- Requirement revision / authority:

## Development assurance

- Profile: `DEV0` / `DEV1` / `DEV2` / `DEV3` / `DEV-E`
- Why this profile is sufficient:
- Escalation signals considered:
- Human approval required: yes / no

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
- Replay / mutation / benchmark / canary:
- Repository regression:

### Intentionally skipped

Describe every relevant layer that was not executed and why another form of evidence is sufficient.

- Skipped evidence:
- Reason:
- Replacement evidence:

## Test and engineering assets

- Added:
- Changed:
- Invalidated / requires rerun:
- Retired:
- Test design / Golden / Negative / Adversarial asset paths:

## Requirement, Oracle, Policy, Permission

- Requirement changed during implementation: yes / no
- Oracle changed: yes / no
- Policy / Permission / Assurance Floor changed: yes / no
- Change authority and approval:
- Historical evidence impact:

## Deployment, recovery, and rollback

- Runtime / schema / data / model / memory / device impact:
- Deployment path:
- Smoke / probe / canary:
- Rollback or recovery:
- Irreversible effects:

## Review findings and residual risk

- Open blockers:
- Accepted residual risks:
- Assumptions and unknowns:
- Follow-up items with owner and deadline:

## Merge eligibility

- [ ] Goal and scope remain approved.
- [ ] Assurance profile is justified and has not been silently downgraded.
- [ ] Change-specific evidence is sufficient.
- [ ] Required GitHub checks are green.
- [ ] Critical False Green is zero.
- [ ] Review threads and blockers are resolved.
- [ ] Assets, status, and ledgers are truthful.
- [ ] Deployment and rollback are credible.
- [ ] Human approval is present when required by the SSOT.

Auto-merge eligibility: `ELIGIBLE` / `NOT_ELIGIBLE` / `HUMAN_APPROVAL_REQUIRED`

Normative process: `docs/github-development-ssot.md`.