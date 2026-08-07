# M1B Store & Progressive Retrieval Threat Model

> Threat Model: `TM-M1B-STORE-PROGRESSIVE-RETRIEVAL@0.1.0`  
> SPEC: `SPEC-M1B-STORE-PROGRESSIVE-RETRIEVAL@0.1.0`  
> Goal: Issue #62  
> Assurance: `DEV3 / UX0`

## 1. Protected assets

- immutable Memory Revisions and canonical hashes;
- Head compare-and-swap state;
- State, ACL and Audit Event streams;
- idempotency reservations and original results;
- Namespace and Principal isolation;
- Requirement, Oracle, Policy and Permission authority;
- provenance, compatibility and retention;
- Forget Tombstones and release barriers;
- primary Store snapshot and outbox sequence;
- keyword/vector/graph/archive index integrity;
- cache entries and epochs;
- retrieval plans, cursors, budgets and evidence;
- hidden benchmark truth;
- cross-project and shared-scope isolation.

## 2. Actors

- authenticated user/Agent/service Principal;
- delegated Principal;
- Memory writer;
- query caller;
- Store adapter;
- index/cache worker;
- migration/backfill operator;
- verifier/benchmark evaluator;
- stale worker or duplicated outbox consumer;
- compromised provider or dependency;
- malicious Memory candidate;
- accidental operator.

Relevance providers, embeddings, graph edges, repository content and model output are untrusted signals.

## 3. Trust boundaries

1. caller → query/mutation service;
2. service → primary Store transaction;
3. primary Store → outbox;
4. outbox → derived indexes;
5. service → cache;
6. query planner → recall providers;
7. candidate refs → primary revalidation;
8. cursor → resumed query;
9. backup/migration → restored Store;
10. evidence bundle → independent verifier.

## 4. Threats and required controls

| ID | Threat | Required control | Failure result |
|---|---|---|---|
| M1B-T01 | Search occurs before Namespace authorization | exact authorized partition handles before any channel | `BLOCKED` |
| M1B-T02 | Global vector search leaks cross-project similarity | partitioned vector query; no global post-filter pattern | `BLOCKED` |
| M1B-T03 | Unauthorized candidate count/timing leaks scope facts | suppress unauthorized counts/scores and normalize failure output | `BLOCKED` |
| M1B-T04 | Stale ACL cache grants removed access | ACL epoch in cache/cursor and primary permission revalidation | filtered |
| M1B-T05 | Stale State index returns Revoked/Expired content | primary Head/effective-state revalidation | filtered |
| M1B-T06 | Forget races cache/index reads | durable release barrier checked before every release | `BLOCKED` |
| M1B-T07 | Backup restore resurrects forgotten content | replay Tombstones/state/ACL before enabling reads | restore rejected |
| M1B-T08 | Partial Revision transaction creates content without audit | all-or-nothing mutation transaction | invalid transaction |
| M1B-T09 | Lost update silently changes Head | atomic expected-Head CAS | explicit conflict |
| M1B-T10 | Idempotency key is rebound to another actor/request | authenticated request fingerprint and original-result replay | rejected |
| M1B-T11 | Duplicate outbox event creates duplicate/incorrect index state | event identity and idempotent sequence handling | idempotent |
| M1B-T12 | Missing outbox event leaves permanent false negative | lag reconciliation, sequence gap detection and replay | degraded/rebuild |
| M1B-T13 | Poisoned keyword tokens dominate ranking | tokenizer/profile pinning, per-channel limits and primary validation | candidate filtered |
| M1B-T14 | Poisoned vector embedding promotes malicious Memory | embedding profile pin, non-authority score and benchmark mutation | candidate only |
| M1B-T15 | Graph cycle or high-degree node exhausts budget | edge allowlist, depth/fanout/visited limits | limited result |
| M1B-T16 | Exact ref bypasses current lifecycle/ACL | exact ref gets precedence only after all authority filters | filtered |
| M1B-T17 | Compatibility is evaluated after content release | compatibility before ranking/content release | filtered |
| M1B-T18 | Cursor reused by another actor or query | integrity-protected actor/query/epoch binding | cursor invalid |
| M1B-T19 | Cursor exposes raw Memory content | opaque cursor containing refs/digests only | rejected |
| M1B-T20 | Nondeterministic ties change context and verdict | versioned fusion, rounding and canonical tie-breakers | run invalid |
| M1B-T21 | Provider drift changes vector/keyword results silently | provider/profile version in plan, result and replay | degraded/replan |
| M1B-T22 | Budget bypass loads unbounded history | hard cumulative candidate/result/token/latency budgets | limited result |
| M1B-T23 | Retry storm amplifies outage and cost | at most one bounded channel retry; no authority retry | blocked/degraded |
| M1B-T24 | Primary outage releases cache-only content | primary unavailable blocks content release | `BLOCKED` |
| M1B-T25 | Index outage silently changes authoritative verdict | declared degraded mode and omission evidence | `DEGRADED` |
| M1B-T26 | Cache key misses authority/profile epoch | required digests/epochs in key; unknown epoch is miss | bypass |
| M1B-T27 | Index rebuild indexes forgotten/superseded revisions | Tombstone/state/ACL streams before content | rebuild rejected |
| M1B-T28 | Migration changes IDs or canonical hashes | backfill manifest and byte/hash equivalence | cutover blocked |
| M1B-T29 | Rollback removes a Tombstone or Forget barrier | Tombstones are monotonic and replayed on every path | rollback blocked |
| M1B-T30 | Hidden benchmark truth enters Memory/query context | verifier-only ground truth and contamination invalidation | run invalid |
| M1B-T31 | Audit/evidence omits rejected or degraded paths | append-only plan/stage/channel/filter evidence | run invalid |
| M1B-T32 | Similar Memory is treated as Oracle/Policy/Permission | authority ordering and non-authority score contract | `ORACLE_CONFLICT` |

## 5. Abuse cases

### 5.1 Cross-project vector exfiltration

A caller authorized for Project A sends a vector similar to secret content in Project B. The planner resolves only Project A partitions before vector search. No Project B candidate count, distance or timing is returned.

### 5.2 Forgotten content through stale cache

A cache entry was filled before Forget. Forget advances a release barrier and cache epoch. The cache key no longer validates, and the primary Tombstone prevents release even if the cache bytes still exist physically.

### 5.3 Ranking poison

A Candidate repeats keywords, creates many graph edges and supplies a high-similarity embedding. Channel limits and RRF prevent one channel from granting authority. Lifecycle/provenance filters and primary validation still apply.

### 5.4 Cursor replay after ACL removal

A previously valid cursor is used after membership or ACL changes. The ACL epoch differs, so the cursor is invalid rather than continuing from a stale authorized snapshot.

### 5.5 Backup resurrection

An old backup contains content deleted after a Forget event. Restore applies Tombstone and barrier history before content and indexes. Readiness remains false until a forgotten-content probe proves no release path.

### 5.6 Partial provider outage

The vector provider is unavailable. The result records vector omission and `DEGRADED`; it does not secretly call an unapproved provider or claim full recall.

## 6. Side-channel controls

- no unauthorized partition scans;
- no unauthorized result counts or scores;
- constant-shape authorization failures where practical;
- bounded and versioned channel execution;
- raw vector queries/embeddings are not persisted by default;
- no raw Secret/personal content in metrics, cursors or audit comments;
- shared-scope membership is evaluated before search;
- cold/archive escalation is explicit and audited.

## 7. Integrity controls

- deterministic Canonical JSON and SHA-256;
- immutable Revision/event identity;
- transaction journal and outbox sequence;
- primary/index snapshot refs;
- per-candidate source Revision hash;
- evidence bundle manifest hash;
- signed/integrity-protected cursor;
- rebuild/backfill count and hash manifests;
- independent replay and tamper rejection.

## 8. Availability and degradation

Availability cannot weaken authority.

- primary unavailable → no content release;
- cache unavailable → bypass;
- index/channel unavailable → declared degradation;
- stale index → primary revalidation for every candidate;
- unknown ACL/Forget epoch → block;
- time budget exhausted → return only already validated content;
- retry limits remain finite.

## 9. Privacy and data boundaries

- synthetic or repository-owned non-production fixtures for implementation proof;
- no Secret acquisition or validation;
- no personal data;
- no hidden benchmark answer in actor context or Memory;
- no broad raw content copy into indexes by default;
- evidence retention and deletion are versioned in the implementation profile;
- Forget verification spans primary, index, cache, archive and replay surfaces.

## 10. Residual risks

- approximate vector recall cannot prove perfect semantic recall;
- timing normalization cannot eliminate every side channel;
- a vendor may have hidden persistence outside the adapter contract;
- asynchronous index convergence creates temporary degraded recall;
- no finite benchmark proves universal relevance;
- backup physical deletion may lag logical Forget barriers;
- performance targets depend on the implementation profile and dataset.

Residual risks remain explicit and cannot be converted into authority or an unqualified production claim.
