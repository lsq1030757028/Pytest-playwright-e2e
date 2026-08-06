# M1B Deterministic Memory Store & Progressive Retrieval SPEC

> SPEC ID: `SPEC-M1B-STORE-PROGRESSIVE-RETRIEVAL@0.1.0`  
> Status: `CANDIDATE`  
> Goal: Issue #62  
> Work Item: `M1B-STORE-RETRIEVAL-SPEC`  
> Parent Memory Campaign: Issue #59  
> Top-level Product Campaign: Issue #65 `TEST_AGENT_RUNTIME_BETA`  
> M1A dependency: Goal #43 `CLOSED`  
> Authority: `MANDATE-AUTONOMY-M1-M3@1.0.0`  
> Assurance: `DEV3 / UX0`  
> Machine contract: `docs/specs/m1b-store-progressive-retrieval.yaml`

## 1. Business result

M1B defines how governed Memory is stored durably and retrieved progressively without loading all history into an Agent context and without allowing similarity, ranking, indexes or caches to bypass authority.

The result is a vendor-neutral contract for an implementation that:

- preserves every M1A identity, namespace, ACL, provenance, lifecycle, CAS, idempotency, retention, revoke, expire and forget invariant;
- writes immutable revisions and event streams atomically;
- searches only already-authorized namespace partitions;
- uses Hot, Warm and Cold retrieval stages with hard latency, token, result and candidate budgets;
- treats metadata, keyword, vector, graph and archive recall as non-authoritative signals;
- revalidates every released Revision against the authoritative primary Store;
- survives stale indexes, partial outages, retries and migrations without silently releasing invalid content;
- proves false-positive retrieval, false-negative retrieval, poisoning resistance, performance and replayability.

M1B supports the `BETA-D` restart and governed-context slice in Campaign #65. It is a subsystem, not the product endpoint, and it must not block the earlier `BETA-A` operating slice.

## 2. Scope and exclusions

### 2.1 In scope

- architecture-neutral implementation contract for the six M1A Ports;
- primary Store authority and derived index/cache boundaries;
- append-only data and event transaction units;
- namespace partitioning and cross-scope isolation;
- progressive retrieval request, plan, result, cursor and evidence contracts;
- deterministic multi-channel recall and fusion;
- lifecycle/read-mode release policy;
- stale index, cache, timeout, outage and degraded-mode behavior;
- revoke, expire and forget barriers across all derived surfaces;
- replay, benchmark, observability, migration and rollback requirements.

### 2.2 Explicitly out of scope

- choosing a database, vector engine, embedding provider, graph engine, cache or cloud vendor as normative authority;
- implementing the Store or retrieval runtime in this SPEC PR;
- autonomous Memory formation, consolidation or promotion;
- shared Memory coordination beyond M1A namespace/ACL contracts;
- changing Requirement, Oracle, Experience Oracle, Policy or Permission;
- production or personal data;
- Secrets or hidden evaluator answers;
- destructive migration or irreversible external action;
- M4/M5/M6 capability claims;
- direct writes to `main`.

An implementation adapter may later select concrete technologies in its own approved Goal/SPEC. The selected technology remains an implementation profile, never domain authority.

## 3. Preserved M1A contract

M1B implements rather than replaces:

- `MemoryRevisionPort`;
- `MemoryStatePort`;
- `MemoryAclPort`;
- `MemoryQueryPort`;
- `MemoryAuditPort`;
- `MemoryMaintenancePort`.

The following invariants are not negotiable:

```text
Immutable content Revision
+ Append-only state / ACL / audit events
+ Authenticated Principal
+ Namespace and ACL before relevance
+ Provenance and canonical SHA-256
+ Atomic Head compare-and-swap
+ Authenticated-request idempotency
+ Retention / Revoke / Expire / Forget
+ Memory never becomes Oracle by relevance
```

A physical migration cannot change a logical Memory ID, Revision ID, Revision number, canonical hash, event identity or effective governance history.

## 4. Authoritative and derived data

### 4.1 Primary Store

The primary Store is authoritative for:

- immutable Revision content;
- current Head pointer;
- State Event stream;
- ACL Event stream and ACL epoch;
- Audit Event chain;
- Forget Tombstone and content-release barrier;
- retention and compatibility metadata;
- idempotency reservation and result;
- outbox sequence.

### 4.2 Derived surfaces

Keyword, vector, graph and archive indexes plus caches are derived surfaces.

They may accelerate candidate discovery, but they cannot:

- grant access;
- determine effective lifecycle state;
- supersede a Tombstone;
- release content without primary validation;
- create Oracle/Policy/Permission authority;
- make a stale candidate valid;
- silently omit a required exact reference.

Derived indexes should store reference and non-sensitive feature data by default. Plaintext content in an index requires a separately approved profile with equivalent isolation, encryption, deletion and evidence guarantees.

## 5. Physical and logical isolation

Every physical partition or equivalent query scope includes:

```text
organization_id
project_id_or_dash
scope_kind
scope_id
```

The query path is:

```text
Authenticate Principal
→ Resolve exact authorized Namespace handles
→ Apply ACL
→ Search only those partitions
→ Resolve current Head and effective state
→ Apply retention / compatibility / budget
→ Rank candidates
→ Revalidate selected refs in primary Store
→ Release content
```

Forbidden:

- one global cross-project vector query followed by post-filtering;
- exposing unauthorized candidate counts, distances, graph degree or timing;
- wildcard cross-project namespace selection;
- implicit Organization or Parent-scope access;
- Shared scope without explicit membership and ACL.

## 6. Mutation transactions

### 6.1 Append Revision

One atomic transaction includes:

1. reserve the idempotency key for the authenticated request fingerprint;
2. validate the current Head and expected Head;
3. append the immutable Revision;
4. advance the Head through compare-and-swap;
5. append the Audit Event;
6. append the index outbox event.

The result is either one accepted mutation or one explicit conflict/rejection. A partially committed Revision, Head or audit record is invalid.

### 6.2 State transition

One atomic transaction includes the State Event, effective-state sequence advancement, audit and invalidation outbox.

### 6.3 ACL change

One atomic transaction includes the ACL Event, ACL epoch advancement, audit and invalidation outbox.

### 6.4 Forget

One atomic transaction includes:

- durable Tombstone;
- content-release barrier advancement;
- immediate logical inaccessibility of content;
- Audit Event;
- invalidation outbox.

Physical cleanup may continue asynchronously only after every query path is fenced by the new barrier.

## 7. Consistency model

- writes for one logical Memory are serializable or equivalent;
- Head compare-and-swap is atomic;
- stale expected Head returns `EXPLICIT_CONFLICT`;
- primary reads are monotonic for Head and read-your-writes;
- queries use a primary-validated snapshot;
- outbox delivery is at-least-once and idempotent;
- index sequence is monotonic per namespace partition;
- cache fill occurs only after primary validation;
- UTC-aware injectable clocks drive retention and replay.

The contract does not require one global transaction across all namespaces or indexes.

## 8. Retrieval request

A `RetrievalRequest` includes:

- request ID;
- authenticated actor/delegation context;
- exact authorized Namespace set;
- read mode;
- objective reference and digest;
- Requirement/Oracle/Policy authority refs;
- compatibility context;
- retrieval and budget profile refs;
- evaluation time;
- optional exact Memory refs;
- optional Kind and metadata filters;
- optional keywords, graph seeds or vector query ref;
- required coverage obligations.

It cannot contain wildcard cross-project access, unversioned embeddings, model-declared permission or a relevance override.

## 9. Filter and release pipeline

Normative order:

```text
1. Authenticate Principal
2. Resolve exact Namespace handles
3. Evaluate ACL
4. Resolve current Head and effective lifecycle
5. Apply retention and Forget barrier
6. Validate provenance and integrity
7. Apply compatibility
8. Enforce budget
9. Discover and rank relevance
10. Revalidate selected refs against primary snapshot
11. Release content
```

Namespace, ACL, lifecycle, retention and compatibility filtering happen before relevance ranking.

If a candidate is discovered through a stale index, primary validation can reject it. Ranking cannot reverse that rejection.

## 10. Read-mode lifecycle policy

### Advisory

May release `CANDIDATE`, `VERIFIED` and `PROMOTED`, with Candidate state clearly labeled. Advisory output cannot become authority.

### Evidence-bearing

May release only `VERIFIED` and `PROMOTED` with complete provenance and integrity evidence.

### Production retrieval

May release only `PROMOTED` Revision content that remains compatible, unexpired and authorized.

Always excluded:

- `CONFLICTING`;
- `QUARANTINED`;
- `SUPERSEDED`;
- `REVOKED`;
- `EXPIRED`;
- `FORGOTTEN`.

## 11. Progressive stages

Budgets are cumulative. A request starts at Hot and may escalate only when the current stage cannot satisfy declared coverage or evidence obligations and budget remains.

### 11.1 Hot

Purpose:

- exact refs;
- current Campaign/Agent context;
- recent Verified/Promoted Memory;
- cheap metadata/keyword recall.

Default maximum:

- 24 candidates;
- 6 released Revisions;
- 2,000 estimated tokens;
- 250 ms.

### 11.2 Warm

Purpose:

- broader authorized Project/Shared recall;
- optional vector and graph channels;
- multi-channel fusion.

Cumulative maximum:

- 96 candidates;
- 12 released Revisions;
- 6,000 tokens;
- 1,000 ms.

### 11.3 Cold

Purpose:

- archive/history;
- older episodes;
- parent chains;
- conflict-resolution context.

Cumulative maximum:

- 256 candidates;
- 20 released Revisions;
- 12,000 tokens;
- 3,000 ms.

Cold requires an explicit escalation reason. The Agent cannot jump directly to Cold merely to increase recall.

### 11.4 Deterministic stop rules

Stop when:

- required exact refs are resolved;
- coverage obligations are met;
- the next stage has no remaining budget;
- authority or policy blocks retrieval;
- a versioned deterministic stop rule matches.

“Model thinks enough context exists” is not a stop rule unless translated into a bounded Candidate signal and independently verified.

## 12. Recall channels and deterministic fusion

Channels:

- exact ref;
- metadata;
- keyword;
- vector;
- graph;
- archive.

Vector and graph are optional. Their absence produces a declared degraded result rather than a hidden provider substitution.

Default fusion is weighted Reciprocal Rank Fusion:

```text
fusion_score(candidate)
= Σ channel_weight / (60 + channel_rank)
```

Default weights:

- exact ref: `100`;
- metadata: `4`;
- keyword: `3`;
- vector: `2`;
- graph: `1`;
- archive: `1`.

Exact-ref precedence still requires current authorization and effective state.

Scores are rounded to 12 decimal places. Deterministic ties are broken by:

1. exact-ref match;
2. number of contributing channels;
3. lifecycle priority;
4. creation time;
5. canonical Namespace;
6. Memory ref.

Fusion score cannot grant access or create authority.

## 13. Retrieval plan and result

### 13.1 Plan

A replayable plan includes:

- request digest;
- actor/authority digest;
- authorized Namespace handles;
- filter, channel and fusion versions;
- stage/budget plan;
- stop rules;
- index snapshots;
- primary snapshot;
- cursor binding digest.

### 13.2 Result

A result includes:

- status: `COMPLETE`, `COMPLETE_WITH_LIMITS`, `DEGRADED`, `INSUFFICIENT_EVIDENCE` or `BLOCKED`;
- stage reached;
- released refs and Revision hashes;
- release reasons;
- omitted channel/layer reasons;
- budget consumption;
- channel contributions;
- primary/index snapshot refs;
- filter/fusion versions;
- evidence bundle ref.

Unauthorized candidate counts and similarity values are not exposed.

## 14. Cursor and pagination

The cursor is opaque, integrity-protected and bound to:

- actor identity digest;
- authorized Namespace digest;
- request digest and read mode;
- filter/fusion versions;
- primary/index snapshots;
- stage/channel cursors;
- last sort key;
- ACL epoch;
- Forget barrier epoch.

A different actor, authority set, query or epoch makes it invalid. Raw Memory content is never embedded in a cursor.

## 15. Index and cache contract

### 15.1 Indexes

Every candidate carries:

- exact Memory/Revision ref;
- Namespace partition;
- source Revision hash;
- source sequence;
- index/profile version.

Rebuild is replayable from the primary Revision/event/outbox history. Tombstones, ACL and state streams are applied before content/index entries.

Duplicate outbox delivery is idempotent. Poisoned or tampered index partitions are quarantined.

### 15.2 Cache

Cache keys bind actor authority, Namespace set, read mode, request, filter/fusion versions, primary snapshot and ACL/lifecycle/Forget epochs.

An unknown or stale epoch is a miss. Cache failure is bypassed. No cache entry may remain releasable after a Forget barrier advances.

## 16. Revoke, expire and Forget consistency

Revoke, Expire and Forget advance a query barrier.

Every query checks the current barrier before content release, including cache hits and stale index candidates.

Forget acknowledgement requires:

- durable Tombstone;
- primary content inaccessible;
- invalidation outbox durable;
- cache barrier advanced;
- index barrier advanced;
- audit committed.

After acknowledgement, content release must be impossible even if physical deletion, backup expiry or index cleanup continues.

Restore and rebuild apply Tombstone/state/ACL streams before enabling reads. A backup cannot resurrect forgotten content.

## 17. Degraded modes

| Failure | Required behavior |
|---|---|
| Primary Store unavailable | block content release; return metadata-free error and retry guidance |
| Index unavailable | bounded authorized-partition primary fallback, Hot only, `DEGRADED` |
| Vector unavailable | omit vector, continue declared channels, `DEGRADED` |
| Graph unavailable | omit graph, continue, `DEGRADED` |
| Keyword unavailable | exact + metadata only, `DEGRADED` |
| Cache unavailable | bypass cache, `COMPLETE_WITH_LIMITS` |
| Index stale | primary revalidate every candidate, `DEGRADED` |
| ACL/Forget epoch unknown | block content release |
| Time budget exhausted | only already-primary-validated results, `COMPLETE_WITH_LIMITS` |

At most one retry per channel is allowed by the default profile. Authority failures are never retried. Retry storms are forbidden.

## 18. Observability and evidence

Required metrics include:

- latency by stage;
- candidate/release counts after authorization;
- channel latency/errors;
- primary revalidation rejection;
- index lag;
- cache hit after epoch validation;
- retrieval false positive/negative;
- exact-ref recall;
- token budget;
- degraded-mode count;
- Forget barrier latency.

Forbidden metrics include unauthorized candidate counts, unauthorized similarity and raw Secret/personal content.

Replay evidence includes:

- request/authority digests;
- primary/index snapshots;
- all profile versions;
- stage/budget/stop decisions;
- authorized candidate reference sets;
- per-candidate filter/release decisions;
- channel ranks and fusion scores;
- released Revision hashes;
- cursor digest;
- degraded/omission reasons;
- final manifest hash.

Replay evidence never contains unauthorized raw content.

## 19. Benchmark and acceptance thresholds

Scenario families cover:

- exact refs and Heads;
- Namespace/ACL isolation;
- lifecycle, retention and compatibility;
- keyword/vector/graph recall;
- fusion and deterministic ties;
- stale indexes/caches;
- revoke/expire/forget;
- poisoning/tamper;
- outage/degraded modes;
- cursor/pagination;
- latency/token/result budgets;
- migration/rebuild.

Required thresholds:

```text
Critical unauthorized release count = 0
Forgotten content release count = 0
Exact-ref recall = 100%
Required authority Memory recall = 100%
Noncritical labeled recall >= 95%
Noncritical labeled precision >= 90%
Replay equivalence = 100%
Deterministic ordering = 100%
Default p95 latency <= 3,000 ms
Hot p95 latency <= 250 ms
```

Each deterministic scenario runs at least three times. A provider-dependent profile runs at least five repetitions.

Hidden ground truth is verifier-only and cannot enter Memory formation or actor context.

## 20. Migration and rollback

A Store/profile migration must:

- preserve IDs, hashes and event history;
- apply ACL/Tombstone/state before content;
- produce backfill count/hash manifests;
- shadow-read and diff before cutover;
- replay required scenarios;
- keep dual writes idempotent through the outbox;
- retain the prior read path until the new path is verified;
- preserve Forget barriers during rollback;
- avoid destructive migration.

Rollback restores the previous read path and quarantines unverified derived partitions. It cannot remove a Tombstone or re-enable forgotten content.

## 21. Threat model and independent test design

- Threat model: `docs/security/m1b-store-progressive-retrieval-threat-model.md`
- Test design: `docs/testing/m1b-store-progressive-retrieval-test-design.md`

The threat model treats primary Store, derived indexes, caches, cursors, migrations, backups and ranking inputs as separate trust surfaces.

## 22. Implementation gate

This SPEC PR contains no runtime implementation.

After SPEC approval and merge, a separate implementation Work Item may choose a concrete reference profile and implement the M1A Ports, retrieval contracts, benchmarks and failure injection.

The selected vendor/profile is not domain authority and must remain replaceable behind the approved contracts.

The implementation must not enter M1C Memory formation, shared coordination or autonomous promotion.

## 23. SPEC merge eligibility

The SPEC is mergeable only when:

- Markdown, YAML, threat model and test design agree;
- no vendor is selected normatively;
- M1A invariants are preserved;
- budgets and failure behavior are deterministic;
- dedicated SPEC gate, full CI, Secret Scan and CodeQL are green;
- Review Threads and blockers are zero;
- runtime implementation remains absent;
- the final diff remains inside Goal #62.
