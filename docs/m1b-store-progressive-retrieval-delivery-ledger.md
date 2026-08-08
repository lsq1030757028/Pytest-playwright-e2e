# M1B Store & Progressive Retrieval Delivery Ledger

## 结论

M1B Store & Progressive Retrieval 已完成 SPEC、实现、正确性修复、Resilience、主干验证和发布验证。该模块现在具备真实持久化 Memory Primary Store 与 authority-first progressive retrieval，但 **M1 Memory Gate 仍为 OPEN**；M1C、M1D、M1E、M1F 尚未关闭。

本 Ledger 只关闭 M1B，不宣称 Memory MVP、TEST_AGENT_RUNTIME_BETA 或 Stage Delivery 已完成。

## Authority

```text
Parent Campaign：Issue #59
SPEC Goal：Issue #62 — CLOSED
Implementation Goal：Issue #69 — closure target
Approved SPEC：SPEC-M1B-STORE-PROGRESSIVE-RETRIEVAL@0.1.0
Standing Mandate：MANDATE-AUTONOMY-M1-M3@1.0.0
Assurance：DEV3 / UX0
Next Goal：Issue #75 — M1C Memory Formation SPEC
```

## Delivery chain

```text
SPEC PR #68
→ f0c25b75b9bd2308e862a7ce8ad7d8092de7091f

I1 Primary Store PR #70
→ 54da6db80a9e7d099a8acb27b031c62a9b484148

I2 Progressive Retrieval PR #71
→ 517c4dc5ad3d0ccd72530dec80947774d5fb0e21

Exact-ref Correctness Repair PR #73
→ 69b31907d48241b59f05d311030a69c33e2825b6

I3 Resilience / Recovery / Migration / Benchmark PR #72
→ 9600ed4924ddb8b8f76322f8547c4864e71b3e67
```

## Delivered runtime

### Durable Primary Store

- SQLite WAL Reference Profile;
- immutable Revision / Head persistence;
- Head CAS and explicit Conflict;
- actor/CAS-bound Idempotency across restart;
- lifecycle, ACL, audit and Outbox persistence;
- physical Forget of Primary content with durable Tombstone;
- restart integrity checks for Head/history and Audit Chain.

### Progressive Retrieval

- Hot / Warm / Cold bounded retrieval;
- ACL / lifecycle / retention / compatibility / Forget filtering before relevance;
- deterministic Exact Ref / Metadata / Keyword / Archive channels;
- optional Vector / Graph adapters with explicit degradation;
- deterministic weighted RRF and tie-breaking;
- Primary Store revalidation before release;
- integrity-protected Cursor bound to Actor / Namespace / Snapshot / ACL / Forget epochs;
- strong exact/required refs are resolved independently of the broad 256-candidate window.

### Resilience and lifecycle proof

- derived-index health inspection and rebuild;
- Outbox gap recovery;
- Primary outage fail-closed behavior;
- Replay and Tamper rejection;
- migration manifest comparison and source/target Shadow Retrieval equivalence;
- rollback protection against resurrection of Target-only Forget;
- deterministic M1B Benchmark;
- 100 coordinated CAS / Outbox races with one accepted winner and one explicit conflict per race.

## Final authoritative evidence

```text
Final main runtime head：9600ed4924ddb8b8f76322f8547c4864e71b3e67

Main M1B focused / resilience：31146450584 — SUCCESS
Main Full Quality：31146450631 — SUCCESS
Main full-history Secret Scan：31146450593 — SUCCESS
Main CodeQL：31146450576 — SUCCESS
Release：31146450614 — SUCCESS
Cleanup baseline：31146450571 — SUCCESS

Focused M1B tests：36 / 36 PASS
Coordinated CAS / Outbox races：100 / 100 PASS
Critical double winner：0
Unauthorized critical release：0
Forgotten content release：0
Exact-ref recall：100%
Required-authority recall：100%
Deterministic replay：100%
Review Threads：0
```

## Release assets

```text
Python Distribution Artifact：8981646972
Digest：sha256:1ae404deab52790a5f0fad0d8acc3b7b17c7c168afa30ebd030f2ca782b9b375

GHCR Build Record Artifact：8981662218
Digest：sha256:2d345a90028414febc44f55c35de0ce09f60f096d7238b87e11abba4f90c1eb3
```

## Closure branch cleanup

The first post-I3 cleanup workflow completed successfully, but the then-current cleanup registry did not yet include newly created M1B branches. This Closure registers:

```text
spec/m1b-store-progressive-retrieval
feat/m1b-durable-store
feat/m1b-progressive-retrieval
fix/m1b-exact-ref-window
feat/m1b-resilience
docs/m1b-runtime-closure
```

Issue #69 is eligible for final `CLOSED` only after this Closure PR merges, main validation succeeds, and the registered M1B branches are actually deleted or confirmed absent.

## Protected boundaries

M1B does not provide:

- M1C Memory Formation;
- M1D Shared Memory Governance;
- M1E Controlled Self-Evolution;
- M1F final Memory Gate;
- automatic promotion of model output to Fact / Oracle / Policy / Permission;
- production/personal data or Secret access;
- M2/M3 completion or Stage Delivery.

Therefore:

```text
M1B：MERGED / CLOSURE VERIFYING
M1 Memory Gate：OPEN
Stage Delivery：NOT_READY
```

## Next

The next product module is `M1C_MEMORY_FORMATION_SPEC` under Issue #75. M1C must define governed Hot Path and Background Candidate formation on top of the durable M1B Store, with deterministic provenance, idempotency, conflict handling and replay before any implementation begins.
