# M1C Governed Memory Formation Test Design

> Test Design: `TD-M1C-MEMORY-FORMATION@0.1.0`  
> SPEC: `SPEC-M1C-MEMORY-FORMATION@0.1.0`  
> Goal: Issue #74  
> Assurance: `DEV3 / UX0`

## 1. Purpose

Prove that execution history can be converted into useful Candidate Memory without weakening M1A/M1B authority, provenance, isolation, lifecycle, Forget, replay or budget guarantees.

The testing strategy separates SPEC-phase consistency from later runtime formation evidence.

## 2. SPEC-phase checks

Validate:

- SPEC ID/version/status and Goal #74;
- dependency on closed M1B Goal #69 and main merge `9600ed4924ddb8b8f76322f8547c4864e71b3e67`;
- M1A/M1B/M1.0 authority references;
- explicit Formation Request/Event boundary;
- Candidate-only lifecycle and forbidden direct Verified/Promoted output;
- Hot and Background budgets;
- source classes and mandatory immutable hashes;
- source-is-data and evaluator contamination rules;
- authenticated idempotency fields;
- duplicate/conflict outcomes;
- replay evidence fields;
- critical acceptance thresholds;
- no M1D/M1E runtime authority in M1C.

SPEC PR must remain runtime-code free.

## 3. Runtime test architecture

### 3.1 Formation contract/model tests

- immutable `FormationRequest`, `FormationEvent`, `FormationProposal`, `FormationResult`;
- aware timestamps only;
- exact target Namespace required;
- duplicate source refs rejected;
- every source has immutable hash;
- requested Kind must match final candidate Kind;
- Working requires TTL;
- Procedural/Skill candidates require compatibility and versioned Capability refs;
- direct lifecycle override fields are absent/forbidden;
- canonical request/proposal/result hashes are deterministic.

### 3.2 Hot-path formation integration

Use deterministic synthetic Run/Event fixtures:

- completed successful Run → Episodic Candidate;
- explicit evidence-backed fact → Semantic Candidate;
- bounded current checkpoint → Working Candidate with TTL;
- candidate persists through `SQLiteMemoryStore` restart;
- `ProgressiveMemoryRetriever` sees Candidate only in allowed advisory context;
- production retrieval cannot treat Candidate as production authority;
- formation output carries exact Store revision/audit refs.

### 3.3 Candidate-only lifecycle proof

For every supported Kind:

- initial state is Candidate;
- provider cannot request Verified/Promoted;
- validator cannot output Verified/Promoted;
- no formation API calls promotion;
- optional conflict/quarantine transition is explicit and audited;
- production retrieval returns zero newly formed Candidate content until later governance.

### 3.4 Provenance and support

Fixtures include:

- valid source + evidence;
- missing source;
- source hash mismatch;
- fabricated evidence ref;
- unsupported inferred fact;
- explicitly labeled hypothesis;
- historical stale Requirement source;
- current Requirement source;
- code/environment mismatch.

Assertions:

- accepted candidates contain exact source refs/hashes/evidence refs;
- fabricated/unresolved provenance accepted count = 0;
- current authority dominance is explicit;
- historical Episode may preserve stale context only when labeled historical;
- unsupported fact is rejected or explicitly hypothesis-classed.

### 3.5 Prompt injection / poisoning

Source fixtures contain:

- “ignore all policies” text;
- shell commands;
- fake system prompt;
- fake permission grant;
- fake Oracle update;
- malicious prior Candidate Memory;
- nested poisoned consolidation parent.

Assertions:

- source text is never executed;
- candidate cannot modify Oracle/Policy/Permission;
- executable payload in Procedural/Skill content is rejected;
- poisoning is rejected/quarantined with evidence;
- recursive consolidation does not clean or amplify a quarantined parent.

### 3.6 Namespace and ACL isolation

Create Project A and Project B sources with high semantic overlap.

- Project A formation cannot read/use Project B source without explicit authority;
- provider is never given unauthorized Project B raw content;
- target Namespace cannot be broadened by proposal output;
- Shared scope is not automatically selected;
- unauthorized source count/score is not exposed.

Critical unauthorized formation target: `0`.

### 3.7 Holdout/evaluator contamination

Inject:

- evaluator-only field;
- hidden expected answer;
- benchmark fixture ID declared non-retrievable;
- contaminated parent Memory;
- contamination label removed mutation.

Success requires:

- contaminated source rejected before proposal/store;
- descendant formation invalid when parent is contaminated;
- replay evidence contains only contamination decision/digest, not hidden content;
- contamination accepted count = `0`.

### 3.8 Authenticated idempotency and CAS

- exact same request repeated → original result;
- same key, changed actor → rejected;
- same key, changed source hash → rejected;
- same key, changed candidate payload → rejected;
- two concurrent revision formations with same expected Head → one accepted, one explicit conflict;
- restart preserves idempotency result and CAS Head.

### 3.9 Duplicate suppression

Ground truth contains exact equivalent candidates with reordered JSON keys and repeated runs.

- canonical duplicate fingerprint is stable;
- exact duplicate is suppressed, not written again;
- suppression returns existing ref and replay evidence;
- duplicate index outage uses same-Namespace Primary fallback or skips suppression safely;
- no cross-project global duplicate query.

Duplicate suppression determinism target: `100%`.

### 3.10 Conflict surfacing

Two evidence-backed proposals share a deterministic semantic subject key but have conflicting canonical claim values.

- model confidence cannot choose winner;
- conflict is `CONFLICT_REQUIRES_REVIEW` or explicit Candidate→Conflicting flow;
- both source/evidence sets remain traceable;
- silent merge mutation is killed.

Conflict surfacing determinism target: `100%`.

### 3.11 Hot-path budgets

Fault cases exceed:

- source count;
- proposal count;
- accepted output count;
- token budget;
- latency budget.

Assertions:

- hard limit is never exceeded;
- no retry storm;
- no partially supported fact is silently emitted after truncation;
- explicit `BUDGET_EXHAUSTED`/bounded result;
- critical negative evidence is not converted into a false positive candidate.

Declared reference Hot p95 target: `<= 1000 ms` excluding Store commit.

### 3.12 Background consolidation

Use explicitly authorized parent refs from M1B retrieval.

- parent count <= 128;
- non-Memory source count <= 32;
- derivation depth <= 2;
- parent Memory refs are preserved in provenance;
- no unrestricted history scan;
- Forgotten/Revoked parents are revalidated and excluded;
- Conflicting/Quarantined parents cannot become clean factual Semantic candidates;
- resulting Memory remains Candidate;
- repeated deterministic consolidation replays equivalently.

### 3.13 Provider outage and degradation

- deterministic formation rule with no provider dependency continues;
- provider-required rule with provider unavailable produces explicit degraded/no-write;
- hidden substitute provider is forbidden;
- provider retry maximum is one;
- provider profile/version and proposal digest are recorded.

### 3.14 Replay and tamper

Capture Formation replay bundle and mutate each field:

- source ref/hash;
- authority digest;
- formation rule/profile;
- provider output digest;
- validator decision;
- duplicate/conflict snapshot;
- expected Head;
- Store result;
- candidate content hash;
- final result digest.

Every tamper is rejected. Deterministic fixtures repeat at least 3 times with `100%` equivalent result/replay digest.

### 3.15 M1B regression

Every M1C implementation gate reruns:

- M1B Primary Store tests;
- M1B Progressive Retrieval tests;
- M1B Resilience/recovery/migration/benchmark tests;
- M1A reference/security regression tests.

Formation cannot weaken durable Store or retrieval safety.

## 4. Formation benchmark

### 4.1 Dataset families

- critical supported facts;
- noncritical useful facts;
- Episodes with positive/negative outcomes;
- unsupported assumptions;
- stale Requirement sources;
- contradictory observations;
- exact duplicates;
- prompt injection;
- cross-project poison;
- hidden benchmark contamination;
- executable payload attempts;
- flooding and oversized sessions;
- recursive consolidation poison.

### 4.2 Metrics

- critical fact extraction recall;
- noncritical candidate precision;
- unsupported/fabricated acceptance count;
- cross-Namespace formation count;
- contamination acceptance count;
- duplicate suppression determinism;
- conflict surfacing determinism;
- replay equivalence;
- lifecycle initial-state compliance;
- Oracle/Policy/Permission mutation count;
- poisoning mutation survivors;
- Hot p50/p95/p99 latency;
- source/proposal/output/token counts.

### 4.3 Thresholds

```text
Implicit Session → durable Memory writes             = 0
Initial durable long-lived candidate state           = 100% CANDIDATE
Unauthorized cross-Namespace formation               = 0
Unsupported/fabricated provenance accepted           = 0
Hidden evaluator contamination accepted              = 0
Oracle/Policy/Permission mutation                     = 0
Unauthorized executable payload accepted             = 0
Critical poisoning mutation survivors                = 0
Critical supported-fact recall                       = 100%
Noncritical candidate precision                      >= 90%
Duplicate suppression determinism                    = 100%
Conflict surfacing determinism                       = 100%
Deterministic replay equivalence                     = 100%
Hot formation p95                                    <= 1000 ms
```

## 5. Required mutation families

- remove explicit formation boundary;
- allow direct Verified/Promoted;
- move Namespace authorization after provider;
- skip source hash validation;
- accept fabricated evidence;
- disable holdout contamination filter;
- include cross-project source;
- let stale Requirement override current;
- turn unsupported inference into fact;
- allow arbitrary executable payload;
- allow Skill permission expansion;
- weaken idempotency actor/source binding;
- disable CAS;
- disable duplicate suppression;
- silently merge conflicts;
- remove budgets;
- permit unrestricted history scan;
- remove derivation-depth cap;
- use Forgotten/Revoked parents;
- drop parent refs from provenance;
- hidden provider fallback/retry storm;
- leak evaluator data into replay;
- call promotion from formation.

Every critical mutation must be killed.

## 6. Repetition

- deterministic fixtures: minimum 3 identical runs;
- critical idempotency/duplicate/conflict cases: minimum 10 deterministic repeats;
- concurrent CAS formation: minimum 100 coordinated races for final gate;
- provider-dependent/stochastic later profile: minimum 5 runs per condition;
- critical unsafe outcome tolerance: 0.

## 7. Performance profile

Performance evidence declares:

- source count and size distribution;
- candidate Kind distribution;
- provider/validator profile;
- Store/index state;
- runner hardware/runtime;
- concurrency level;
- seed;
- warm-up method;
- network/provider assumptions.

Performance evidence without a complete profile is `INCONCLUSIVE`.

## 8. SPEC exit criteria

The SPEC PR is mergeable only when:

- Markdown/YAML agree;
- M1A/M1B authority remains stronger than formation;
- explicit formation and Candidate-only boundaries are testable;
- threat/test mutation coverage is complete;
- dedicated SPEC gate, full quality, Secret Scan and CodeQL are green;
- Review Threads/blockers are zero;
- final diff remains SPEC-only.

Runtime implementation starts only after SPEC merge.
