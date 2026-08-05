# M1A Memory Runtime Contract Security Repair Test Design

## 1. Authority and classification

- Goal: Issue #43
- Approved SPEC: `SPEC-M1A-MEMORY-CONTRACTS-NAMESPACES@1.0.0`
- Approval: `APPROVAL-M1A-MEMORY-CONTRACTS-NAMESPACES-SPEC@1.0.0`
- Mandate: `MANDATE-AUTONOMY-M1-M3@1.0.0`
- Repair profile: `DEV3 / UX0`
- Change type: evidence-backed implementation repair inside the approved Goal and SPEC

No Requirement, Oracle, Policy, Permission, production data, Secret, external system or user-facing behavior is changed.

## 2. Review findings

Post-merge review found three false-green paths in the deterministic reference adapter:

1. a newly appended immutable revision inherited the previous revision's effective lifecycle state, so new content could remain `PROMOTED` without fresh verification;
2. the idempotency fingerprint did not include the authenticated actor or `expected_head_revision_id`, and the cached result was returned before current permission was checked;
3. a forgotten logical Memory ID could accept a new content-bearing revision even though the tombstone continued to make that ID non-effective.

These are contract implementation defects, not SPEC changes. M1A must not be closed until the repair passes the dedicated gate, full regression, review, main, release and cleanup verification.

## 3. Test obligations

| Obligation | Failure mode | Required evidence |
|---|---|---|
| Revision-scoped lifecycle | a new revision inherits `VERIFIED` or `PROMOTED` from an older revision | promote revision 1, append revision 2, prove revision 2 is `CANDIDATE`, invisible to production retrieval and visible only in advisory mode |
| Permission-safe idempotency | an unauthorized actor receives a cached accepted result | accept a request, replay the exact request as an unprivileged actor, require `ACL_DENIED` |
| Complete request binding | the same key with a changed CAS precondition replays the old result | reuse the key with another `expected_head_revision_id`, require `DUPLICATE_IDEMPOTENCY_KEY` |
| Exact replay | the same authorized actor and same complete request does not return the original result | require `IDEMPOTENT_REPLAY` without another write or audit mutation |
| Forget finality | a forgotten logical ID accepts new content | revoke, forget, append a later revision, require `FORGOTTEN_CONTENT_UNAVAILABLE` and no revival |
| Historical compatibility | existing 15-scenario proof or established integration behavior drifts | run the existing proof, independent replay, focused reference tests and full repository CI |

## 4. Evidence selection

Selected:

- focused boundary integration against the real deterministic in-memory adapter;
- current permission, actor, CAS and lifecycle-state assertions on final effective state;
- existing 15-scenario deterministic proof and independent replay;
- dedicated M1A GitHub Actions gate;
- full repository regression and historical UX gates.

Skipped:

- database, network and browser integration because this repair changes only the storage-neutral reference adapter contract;
- Human UAT because the change has no user-facing behavior;
- migration tests because no persisted or external state exists.

## 5. Deployment and rollback

Deployment is merge to `main` followed by normal package/GHCR release verification. Rollback is a Git revert of the repair PR. The historical adapter implementation remains reviewable in Git history; no data migration or destructive action is involved.

## 6. Exit criteria

- all three new adversarial regressions pass;
- existing focused M1A tests and 15/15 proof remain green;
- independent replay and tamper rejection pass;
- full repository CI and affected historical gates pass;
- Review Threads and blockers are zero;
- main, release, delivery ledger and repair-branch cleanup are verified;
- Critical False Green and unauthorized Memory actions remain zero.
