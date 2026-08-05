# Autonomous Execution Mandate Test Design

> SPEC: `SPEC-AUTONOMY-M1-M3@1.0.0`  
> Profile: `DEV3`  
> Authority: Issue #23

## 1. Objective

Prove that the repository can replace repeated per-module approval with a bounded standing mandate without weakening SPEC, evidence, review, rollback, release, Oracle, Policy, Permission, production-data, secret, device, or irreversible-action boundaries.

## 2. Failure modes

| ID | Failure mode | Required result |
|---|---|---|
| AUT-01 | DEV3 merges without an active mandate | Reject |
| AUT-02 | Mandate silently covers work outside M1–M3 | Reject |
| AUT-03 | Missing approved SPEC is treated as covered | Reject |
| AUT-04 | Failed CI or Review Thread is ignored | Reject |
| AUT-05 | Production write, Secret, destructive migration, or irreversible spend is treated as routine autonomy | Block |
| AUT-06 | Candidate Memory is promoted directly | Reject |
| AUT-07 | DEV-E production action uses standing mandate | Reject |
| AUT-08 | Revoked mandate still permits new merge | Reject |
| AUT-09 | Templates do not record mandate scope | Reject |
| AUT-10 | M1.0 is marked implemented by governance-only change | Reject |

## 3. Test obligations

- Mandate ID, authority, scope, status, and revocation are machine validated.
- Covered profiles include DEV3 but exclude DEV-E.
- DEV3 authorization mode is `standing_mandate_or_explicit_human_approval`.
- Auto-merge requires mandate, Goal, SPEC, evidence, review, and rollback.
- Out-of-mandate operations remain explicit blockers.
- `AGENTS.md`, SSOT, Goal template, PR template, CI, and status remain consistent.
- Existing repository regression remains green.

## 4. Evidence selection

Selected:

- deterministic YAML and text contract tests;
- GitHub template parsing;
- dedicated CI Gate;
- full repository regression;
- post-merge main, package/GHCR release, and branch cleanup.

Skipped:

- Memory runtime integration, because this change only establishes authorization;
- real production/secret/device execution, because those are intentionally out of mandate;
- model benchmark, because model behavior is unchanged.

## 5. Acceptance

- all mandate policy tests pass;
- no DEV3 safety evidence requirement is removed;
- in-mandate DEV3 can proceed without repeated approval;
- out-of-mandate actions are still blocked;
- PR, main, release, and cleanup workflows succeed;
- no runtime Memory code is introduced by this SPEC.
