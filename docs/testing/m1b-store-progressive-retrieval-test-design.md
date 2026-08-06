# M1B Store & Progressive Retrieval Test Design

> Test Design: `TD-M1B-STORE-PROGRESSIVE-RETRIEVAL@0.1.0`  
> SPEC: `SPEC-M1B-STORE-PROGRESSIVE-RETRIEVAL@0.1.0`  
> Goal: Issue #62  
> Assurance: `DEV3 / UX0`

## 1. Purpose

Prove that the M1B contract can be implemented without weakening M1A and that retrieval quality, isolation, consistency, failure behavior and performance are measurable rather than model-asserted.

This document separates SPEC-phase evidence from the later runtime implementation evidence.

## 2. SPEC-phase evidence

### 2.1 Cross-file consistency

Validate:

- exact SPEC ID/version/status;
- Goal #62, Memory Campaign #59 and top Campaign #65 references;
- M1A dependency and six Port names;
- no normative vendor selection;
- no runtime implementation in the SPEC PR;
- progressive stages, budgets, failure matrix and thresholds agree between Markdown/YAML;
- threat IDs and required test layers are complete;
- the Beta relationship says M1B supports `BETA-D` and does not block `BETA-A`.

### 2.2 M1A invariant preservation

Assertions cover:

- immutable Revision and append-only events;
- Namespace/ACL before relevance;
- provenance and canonical hash;
- expected-Head CAS;
- authenticated-request idempotency;
- lifecycle/read-mode release policy;
- retention, revoke, expire and forget;
- Memory never overrides Requirement/Oracle/Policy/Permission.

### 2.3 Deterministic retrieval contract

Validate:

- exact filter order;
- Hot/Warm/Cold monotonic stage and cumulative budgets;
- default candidate/result/token/latency limits;
- versioned weighted RRF formula and weights;
- deterministic rounding and tie-breakers;
- exact-ref precedence only after authorization;
- non-authority relevance scores;
- versioned plan/result/cursor/evidence fields.

### 2.4 Degraded and fail-closed behavior

For each declared failure mode, assert one outcome:

- `BLOCKED` when primary authority or ACL/Forget epoch is unknown;
- `DEGRADED` when a recall channel/index is unavailable or stale;
- cache bypass without authority change;
- no hidden provider substitution;
- bounded retry and no retry storm.

### 2.5 Forget and migration

Validate the acknowledgement barrier, query checks, backup/restore order, index rebuild order, migration identity/hash preservation and rollback non-resurrection.

## 3. Implementation test architecture

A later implementation Goal must supply a deterministic reference adapter and at least one real storage/index profile.

### 3.1 Contract/model tests

- request, plan, result, cursor and profile schema validation;
- immutable IDs and canonical hashes;
- invalid wildcard Namespace request rejection;
- invalid budget/profile/version rejection;
- cursor actor/query/epoch binding;
- result/evidence completeness.

### 3.2 Primary Store integration

Against the real adapter/profile:

- first append and exact replay;
- changed actor/payload/expected Head idempotency rejection;
- concurrent compare-and-append produces one winner and explicit conflicts;
- State/ACL/Forget transactions are atomic;
- audit chain and outbox sequence verify;
- read-your-writes and monotonic Head;
- crash/restart around every transaction boundary;
- duplicate outbox delivery is idempotent;
- sequence gap reconciliation.

### 3.3 Isolation and authorization

- Organization, Project, Campaign, Agent and Shared scopes;
- parent/child access is not implicit;
- Shared membership and ACL allow/deny precedence;
- delegated Principal expiry and audit binding;
- no global vector/keyword/graph query before authorization;
- unauthorized candidate count/score/timing not emitted;
- exact ref cannot bypass ACL/lifecycle.

### 3.4 Progressive retrieval

Ground-truth fixtures contain relevant, irrelevant, stale, conflicting, revoked, expired, forgotten and cross-project Memory.

For each request:

- prove Hot is attempted first;
- prove stage escalation reason;
- prove cumulative budget accounting;
- prove exact-ref recall;
- prove coverage/stop rule;
- prove content release only after primary validation;
- prove deterministic ordering and cursor continuation;
- prove equivalent replay from plan/evidence.

### 3.5 Channel evidence

#### Metadata

- exact fields and deterministic sorting;
- malformed/unknown metadata rejected;
- current Head only unless explicit history request.

#### Keyword

- tokenizer/profile pinning;
- term stuffing mutation;
- Unicode/case/normalization replay;
- stale token index rejection.

#### Vector

- embedding profile/version pin;
- partition isolation;
- high-similarity unauthorized/stale Candidate filtered;
- provider outage and drift;
- raw query/embedding persistence disabled by default.

#### Graph

- edge allowlist;
- depth/fanout/visited limits;
- cycle and high-degree mutations;
- stale edge and cross-project edge rejection.

#### Archive

- Cold-only access;
- explicit escalation reason;
- retention and Forget barrier;
- no hidden unbounded history load.

### 3.6 Fusion and ranking

- known channel rankings produce exact weighted-RRF score;
- missing channel contributes zero;
- score rounded to 12 places;
- tie-breakers execute in declared order;
- provider result ordering changes do not change fused output when ranks are equal;
- one poisoned channel cannot bypass primary filters;
- score never changes authority or lifecycle.

### 3.7 Cache/index consistency

- valid cache hit;
- ACL/lifecycle/Forget epoch change creates miss;
- stale cache cannot release content;
- stale index candidate is rejected by primary;
- orphan/duplicate index events;
- rebuild from primary history;
- poisoned/tampered partition quarantine;
- index/cache outage degraded behavior;
- convergence/lag metrics.

### 3.8 Revoke, expire and Forget

Fault injection at every step:

1. before Tombstone;
2. after Tombstone before primary content removal;
3. after primary barrier before outbox;
4. during cache invalidation;
5. during each index invalidation;
6. during archive cleanup;
7. during backup/restore;
8. during index rebuild.

Success requires:

- acknowledgement only after the declared barrier;
- content release count `0` after acknowledgement;
- query barrier survives restart;
- backup restore cannot resurrect content;
- verification spans primary, all indexes, cache, archive and replay bundle.

### 3.9 Degraded modes

Inject:

- primary unavailable;
- keyword/vector/graph/index unavailable;
- cache unavailable;
- index stale/sequence gap;
- ACL/Forget epoch unknown;
- timeout and budget exhaustion.

Assert exact status, omitted-layer reason, retry count and content-release rule.

### 3.10 Migration and rollback

- generate source Store with Revisions/events/Tombstones;
- backfill target and verify count/hash manifest;
- apply ACL/Tombstone/state before content;
- shadow-read identical query fixtures;
- compare results and evidence;
- cutover only after replay green;
- inject failure during cutover;
- rollback to prior read path;
- prove no forgotten content is resurrected.

## 4. Retrieval benchmark

## 4.1 Ground truth

Ground truth is verifier-only and versioned by:

- dataset revision;
- query/objective revision;
- actor/Namespace/ACL revision;
- current time and lifecycle events;
- compatibility profile;
- required and acceptable Memory refs;
- prohibited Memory refs;
- channel/provider profile;
- budget profile.

It never enters actor context or Memory formation.

## 4.2 Metrics

- exact-ref recall;
- required-authority recall;
- labeled recall and precision;
- unauthorized/invalid release count;
- forgotten-content release count;
- false-positive/false-negative by stage/channel;
- nDCG/MRR as diagnostics only, not authority;
- deterministic-order equivalence;
- replay equivalence;
- stage latency p50/p95/p99;
- tokens/results/candidates;
- degraded-mode correctness;
- Forget barrier latency.

## 4.3 Thresholds

```text
Critical unauthorized release = 0
Forgotten content release = 0
Exact-ref recall = 100%
Required authority Memory recall = 100%
Noncritical recall >= 95%
Noncritical precision >= 90%
Replay equivalence = 100%
Deterministic ordering = 100%
Default p95 <= 3,000 ms
Hot p95 <= 250 ms
```

Efficiency cannot compensate for a safety or authority regression.

## 5. Mutation families

- remove Namespace prefilter;
- search globally then post-filter;
- ignore ACL epoch in cache/cursor;
- release stale Head/state;
- ignore Forget barrier;
- acknowledge Forget before invalidation barrier;
- allow partial Revision transaction;
- disable Head CAS;
- weaken idempotency binding;
- process duplicate outbox non-idempotently;
- drop an outbox sequence;
- term stuffing;
- vector high-similarity poison;
- graph cycle/fanout explosion;
- change RRF constant/weights/tie order;
- remove provider/profile version;
- exceed candidate/result/token/time budget;
- retry indefinitely;
- release cache-only content during primary outage;
- reuse cursor across actor/query/epoch;
- index content before Tombstone/ACL during rebuild;
- change IDs/hashes during migration;
- remove Tombstone on rollback;
- leak hidden ground truth.

Every critical mutation must be detected. A surviving critical mutation is a critical false green.

## 6. Repetition and replay

- deterministic fixtures: at least 3 identical runs;
- provider-dependent profiles: at least 5 runs;
- concurrency races: at least 100 coordinated repetitions per critical CAS/outbox case;
- restart/fault checkpoints: every declared mutation boundary;
- independent verifier replay: byte-equivalent decision and ordered refs;
- tampered evidence/hash/cursor: explicit rejection.

## 7. Performance method

The implementation profile declares:

- dataset size and distribution;
- Namespace count;
- Revision/event count;
- index size;
- cache state;
- hardware/runtime profile;
- provider/profile versions;
- warm-up method;
- concurrency level;
- seed and query set;
- network conditions.

Performance evidence without a complete profile is `INCONCLUSIVE`.

No benchmark may use production/personal data or hidden credentials.

## 8. Selected and skipped layers

Selected in SPEC phase:

- Markdown/YAML consistency;
- threat/test coverage;
- deterministic budget/filter/fusion checks;
- dedicated CI, full CI, Secret Scan and CodeQL;
- independent review.

Deferred to implementation:

- database/index/cache adapters;
- persistence/restart and concurrency tests;
- real benchmark and fault injection;
- migration profile.

Skipped for UX:

- Synthetic User and browser journey evidence because M1B is `UX0` and changes no user interaction.

## 9. Exit criteria

The SPEC PR is mergeable only when:

- all SPEC assets agree;
- M1A invariants remain stronger than relevance;
- no vendor is selected normatively;
- budgets, thresholds and failures are deterministic;
- runtime implementation remains absent;
- dedicated and full checks are green;
- Review Threads and blockers are zero.

A later implementation is complete only after real Store, index/cache, fault, replay, performance, migration and benchmark evidence meet every threshold.
