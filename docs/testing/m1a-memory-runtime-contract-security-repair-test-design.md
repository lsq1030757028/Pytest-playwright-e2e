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

Post-merge review found false-green paths in the deterministic reference adapter and identity validation:

1. partial delegated identity fields were accepted instead of failing closed;
2. exact idempotency replay returned a changed result instead of the original result required by the SPEC;
3. idempotency was not bound to the authenticated actor or CAS expected head, and replay happened before current permission was checked;
4. a newly appended immutable revision inherited the previous revision's effective lifecycle state, so new content could remain `PROMOTED` without fresh verification;
5. a forgotten logical Memory ID could accept a new content-bearing revision;
6. source absence and source-hash mismatch were collapsed into the same provenance error;
7. concurrent mutations lacked an atomic boundary;
8. ACL self-grant was not explicitly rejected and ACL changes were not entered into the chained audit evidence.

These are contract implementation defects, not SPEC changes. M1A cannot be closed until the repair passes the dedicated gate, full regression, review, main, release and cleanup verification.

## 3. Test obligations

| Obligation | Failure mode | Required evidence |
|---|---|---|
| Delegation completeness | a partial delegated identity is treated as authenticated authority | parameterized negative model tests for every partial field combination |
| Exact idempotency | same authenticated CAS request returns a changed result | accept once and prove exact replay equals the original result without another write |
| Permission-safe replay | an unauthorized actor receives a cached accepted result | accept as owner, replay as unprivileged actor, require `ACL_DENIED` |
| Complete request binding | changed actor or expected head reuses the old result | reuse the key with a changed CAS precondition, require `DUPLICATE_IDEMPOTENCY_KEY` |
| Revision-scoped lifecycle | a new revision inherits `VERIFIED` or `PROMOTED` | promote revision 1, append revision 2, prove revision 2 is `CANDIDATE` and absent from production retrieval |
| Forget finality | a forgotten logical ID accepts new content | revoke, forget, append a later revision, require `FORGOTTEN_CONTENT_UNAVAILABLE` |
| Provenance integrity | a known source with changed bytes is reported only as missing | missing source => `PROVENANCE_MISSING`; mismatched hash => `INTEGRITY_FAILED` |
| Atomic CAS | two concurrent writers both win | coordinated two-thread CAS with exactly one `ACCEPTED` and one `CONFLICT` |
| ACL authority | a manager grants itself new access | explicit self-grant rejection and no ACL mutation |
| ACL audit | an accepted ACL change is not chained | accepted other-subject grant creates `ACL_CHANGED` audit and chain verifies |
| Historical compatibility | existing proof or integration semantics drift | existing focused tests, 15-scenario proof, independent replay and full repository CI |

## 4. Evidence selection

Selected:

- model/unit negatives for delegated identity completeness;
- focused boundary integration against the real deterministic in-memory adapter;
- synchronized concurrent CAS integration;
- current permission, actor, CAS and final lifecycle-state assertions;
- ACL mutation and chained audit assertions;
- existing 15-scenario deterministic proof and independent replay;
- dedicated M1A GitHub Actions gate;
- full repository regression and historical affected gates.

Skipped:

- database, network and browser integration because this repair changes only storage-neutral contracts and the deterministic reference adapter;
- Human UAT because the module has no user-facing behavior (`UX0`);
- migration tests because no persisted or external state exists.

## 5. Deployment and rollback

Deployment is merge to `main` followed by normal package/GHCR release verification. Rollback is a Git revert of the repair PR. No data migration or destructive action is involved.

## 6. Exit criteria

- all new negative, concurrency and adversarial regressions pass;
- existing focused M1A tests and 15/15 proof remain green;
- independent replay and tamper rejection pass;
- full repository CI and affected historical gates pass;
- Review Threads and blockers are zero;
- main, release, delivery ledger and remediation-branch cleanup are verified;
- Critical False Green and unauthorized Memory actions remain zero.
