# M1C Governed Memory Formation SPEC

> SPEC ID: `SPEC-M1C-MEMORY-FORMATION@0.1.0`  
> Status: `CANDIDATE`  
> Goal: Issue #74  
> Parent Campaign: Issue #59  
> Depends on: M1A governed Memory contracts and M1B durable Store / progressive retrieval  
> Assurance: `DEV3 / UX0`  
> Machine contract: `docs/specs/m1c-memory-formation.yaml`

---

## 1. Purpose

M1C defines the boundary that turns raw execution history into **governed Candidate Memory**.

M1A answered what a valid Memory is. M1B made governed Memory durable and retrievable. M1C answers a different question:

> Given a completed Run, Event, Tool result, Artifact, Requirement revision, Code revision or previously governed Memory, when may the system create a new Memory candidate, what must it prove, and what must it refuse to remember?

The critical invariant is:

```text
Observation / Session / Tool Data
!= Memory Authority

Source Evidence
→ Explicit Formation Request
→ Candidate Proposal
→ Deterministic Validation
→ Governed Candidate Revision
```

Formation creates evidence-bearing **candidates**, never truth by fiat.

---

## 2. Authority and dependencies

M1C preserves every M1A and M1B invariant.

Authoritative dependencies:

- `SPEC-M1A-MEMORY-CONTRACTS-NAMESPACES@1.0.0`;
- `SPEC-M1B-STORE-PROGRESSIVE-RETRIEVAL@0.1.0`;
- `SPEC-M1.0-MEMORY-BENCHMARK@1.0.0`;
- M1B implementation Goal #69, closed on main;
- active Requirement / Oracle / Policy / Permission / development SSOT remain above Memory.

M1C may not:

- change Requirement, Oracle, Policy, Permission or production invariant;
- emit a `VERIFIED` or `PROMOTED` Memory as the direct result of formation;
- grant Capability permissions;
- treat model confidence as authority;
- bypass Namespace, ACL, retention, provenance or content-hash rules;
- perform M1D shared-memory governance or M1E controlled promotion.

---

## 3. Explicit formation boundary

Session history is not Memory. Tool output is not Memory. A model summary is not Memory.

Every durable formation write requires a versioned `FormationRequest` and immutable `FormationEvent`.

Normative pipeline:

```text
1. Authenticate formation actor
2. Resolve exact target Namespace and APPEND authority
3. Pin source refs and source hashes
4. Resolve evidence refs and current authority refs
5. Classify source trust / contamination
6. Select versioned formation rule and provider profile
7. Produce Candidate proposal(s)
8. Validate schema / provenance / executable-data boundary
9. Check currentness / conflict / duplicate / budget
10. Create immutable Memory Revision
11. Persist through M1B Store with CAS + authenticated idempotency
12. Record formation decision and replay evidence
13. Return Candidate-only result
```

There is no implicit `Session → Store` shortcut.

---

## 4. Formation modes

### 4.1 Hot-path formation

Purpose: capture a small number of useful candidates at the end of a current execution or bounded checkpoint.

Default cumulative budget:

- source refs: `16`;
- candidate proposals: `8`;
- accepted candidates: `4`;
- proposal input/output tokens: `4,000`;
- wall-clock formation budget: `1,000 ms` excluding durable Store commit;
- no recursive background scan;
- no automatic shared-scope write.

Hot-path formation must not delay a critical release verdict beyond its declared budget. Budget exhaustion produces an explicit partial/no-formation result rather than silently dropping safety evidence.

### 4.2 Background consolidation

Purpose: consolidate explicitly selected, already-authorized Candidate/Episodic inputs into fewer or more useful Candidate revisions.

Default cumulative budget:

- source Memory refs: `128`;
- source non-Memory refs: `32`;
- candidate proposals: `32`;
- accepted candidates: `16`;
- proposal input/output tokens: `16,000`;
- wall-clock budget: `10,000 ms` excluding durable Store commit;
- maximum derivation depth per run: `2`;
- no unrestricted history scan;
- source Memory must be retrieved through M1B authority filters or supplied as exact authorized refs.

Background consolidation never upgrades lifecycle authority. A summary of Candidate data is still Candidate data.

---

## 5. Source classes and trust

Supported source classes:

- `RUN_EVENT`;
- `TOOL_RESULT`;
- `ARTIFACT`;
- `REQUIREMENT_REVISION`;
- `CODE_REVISION`;
- `ENVIRONMENT_REVISION`;
- `MEMORY_REVISION`;
- `HUMAN_ASSERTION` when explicitly classified as an assertion rather than confirmed authority.

Every source ref must bind a canonical content hash or a versioned external immutable digest.

Source content is data, not control. Embedded instructions such as “ignore policy”, shell commands, prompt injection, copied system prompts or tool directives remain untrusted content. Formation cannot execute them.

Evaluator-only or hidden benchmark fields are forbidden source material.

---

## 6. Formation Request

A `FormationRequest` requires:

- `request_id`;
- authenticated `actor_context`;
- `formation_mode`;
- exact `target_namespace`;
- requested `memory_kind`;
- source descriptors with ref, class, content hash and sensitivity/contamination labels;
- evidence refs;
- current Requirement / Oracle / Policy / Permission authority refs or digests relevant to the claim;
- `formation_rule_ref` and version;
- deterministic validator profile;
- optional model/provider profile;
- retention profile;
- budget profile;
- `now`;
- authenticated idempotency key;
- optional expected logical Memory / Head for revision append;
- optional deterministic semantic subject key for duplicate/conflict checks.

Forbidden request fields:

- wildcard cross-project Namespace;
- lifecycle override to Verified/Promoted;
- model-declared permission;
- unversioned executable capability;
- hidden benchmark answer/evaluator payload;
- raw Secret acquisition request;
- automatic shared-scope expansion.

---

## 7. Formation proposal and deterministic validator

A provider/model may propose candidate content, Kind hints, extraction labels or conflict hints. Provider output is always untrusted.

A deterministic validator owns admission.

The validator checks, in order:

1. request and actor integrity;
2. exact Namespace authorization;
3. source hash completeness;
4. evidence ref existence and binding;
5. holdout/evaluator contamination;
6. forbidden sensitive/Secret profile;
7. schema and Memory Kind contract;
8. executable-data boundary;
9. current Requirement / authority dominance;
10. unsupported/fabricated claim rules;
11. duplicate/idempotency binding;
12. conflict identity;
13. formation and Store budgets;
14. M1A canonical hash / provenance validity.

Relevance or model confidence is never evaluated before authority/provenance admission.

---

## 8. Candidate-only lifecycle

Every newly formed durable Memory revision is created in effective `CANDIDATE` state.

Allowed immediate post-formation safety actions are limited to:

- remain `CANDIDATE`;
- transition to `CONFLICTING` when a deterministic conflict is proven;
- transition to `QUARANTINED` when contamination, poisoning or unresolved integrity risk is discovered after append.

M1C cannot transition a newly formed revision to:

- `VERIFIED`;
- `PROMOTED`.

Verification and promotion require later explicit governance outside the formation decision.

Formation of Working Memory also begins Candidate and requires a TTL.

---

## 9. Memory Kind rules

### Working

May capture bounded current work state. TTL is mandatory. Working Memory cannot be automatically converted to durable production authority.

### Episodic

May capture what happened in a Run: context refs, action summary, outcome, failure classification and evidence. Raw full logs are not copied by default; references and bounded summaries are preferred.

### Semantic

May capture structured claims only when every factual element is traceable to source/evidence. Unsupported inference is labeled as hypothesis or rejected; it cannot be serialized as a confirmed fact.

### Procedural

M1C may create only a **proposal Candidate**. It must carry compatibility metadata and may reference only versioned governed Capabilities. Embedded arbitrary code/shell is forbidden. M1E owns evaluation/promotion.

### Skill

M1C may create only a **proposal Candidate** referencing an existing governed Capability ID/version/schema/permission requirements. It cannot create new Capability authority or permission. M1E owns evaluation/promotion.

---

## 10. Provenance contract

Every accepted Candidate Revision must preserve M1A `Provenance` and additionally bind its formation event.

Required formation evidence:

- exact ordered source refs;
- exact source hashes;
- evidence refs;
- actor principal;
- formation rule ref/version;
- provider/model profile ref when used;
- deterministic validator profile;
- Requirement/code/environment revision refs when applicable;
- parent Memory refs for consolidation;
- transformation kind;
- formation request digest;
- formation decision digest.

A fabricated or unresolved source/evidence ref results in rejection, not a best-effort candidate.

---

## 11. Currentness and authority dominance

Formation must pin the current known Requirement/Oracle/Policy/Permission authority refs relevant to the proposed claim.

Rules:

- a stale Requirement-derived source cannot be presented as the current approved requirement;
- Memory from an older code/environment revision may be formed as an Episode but must preserve compatibility/currentness context;
- conflicts with current approved authority are not merged away;
- no Candidate may redefine correctness to make a failing test pass;
- authority mismatch produces `STALE_AUTHORITY`, `ORACLE_CONFLICT`, `POLICY_CONFLICT` or equivalent explicit rejection/quarantine evidence.

---

## 12. Duplicate, idempotency and conflict handling

### 12.1 Authenticated idempotency

An idempotency key binds:

- actor;
- target Namespace;
- mode;
- ordered source hash set;
- formation rule/profile;
- requested Kind;
- expected logical Memory/Head;
- candidate canonical payload digest.

Same authenticated request returns the original result. Rebinding the key to another actor/source/payload is rejected.

### 12.2 Exact duplicate

A deterministic duplicate fingerprint is computed after authorization and canonical validation.

If an identical effective candidate already exists under the same semantic identity and scope, the formation result may be `DUPLICATE_SUPPRESSED` and return the existing ref. Suppression must still emit replay/audit evidence.

### 12.3 Conflict

If a deterministic subject key matches but canonical claim content conflicts, M1C cannot choose a winner by model confidence.

The result is one of:

- `CONFLICT_REQUIRES_REVIEW` without a new write; or
- create Candidate then explicitly mark `CONFLICTING` when the approved formation rule requires preserving both observations.

Silent merge is forbidden.

---

## 13. Poisoning and contamination controls

The following are critical formation threats:

- prompt injection embedded in Tool/Artifact text;
- malicious Memory instructing the Agent to ignore policy;
- fabricated citation/evidence ID;
- hidden benchmark answer or evaluator-only field;
- cross-project source mixed into a Project candidate;
- stale requirement treated as current;
- untrusted assumption serialized as fact;
- arbitrary executable payload in Procedural/Skill candidate;
- candidate flood that crowds out current authority;
- recursive consolidation amplifying an earlier poisoned candidate.

Controls:

- source is data only;
- exact Namespace authorization precedes proposal processing;
- evaluator/holdout contamination labels fail closed;
- provenance and hashes are mandatory;
- bounded derivation depth;
- candidate count/token/time budgets;
- deterministic validator after model proposal;
- no autonomous lifecycle promotion;
- M1B retrieval remains authority-first for all later use.

---

## 14. Formation Result

Result status is one of:

- `CREATED_CANDIDATE`;
- `APPENDED_CANDIDATE_REVISION`;
- `DUPLICATE_SUPPRESSED`;
- `CONFLICT_REQUIRES_REVIEW`;
- `QUARANTINED`;
- `REJECTED`;
- `BUDGET_EXHAUSTED`;
- `DEGRADED` only for optional proposal-provider loss when deterministic non-provider formation can continue.

A result records:

- request digest;
- formation event ref;
- status;
- candidate revision ref/hash when any;
- effective lifecycle after formation;
- source/evidence digests;
- duplicate/conflict refs;
- omitted/rejected reasons;
- budget consumption;
- provider/validator profile versions;
- Store result/audit refs;
- replay evidence digest.

Unauthorized source counts, hidden evaluator values and raw Secrets are not exposed.

---

## 15. Replay and evidence

Deterministic formation must be replayable from approved evidence without hidden model state.

Replay bundle contains:

- canonical FormationRequest digest;
- exact source refs/hashes;
- authority refs/digests;
- formation rule/version;
- provider profile and deterministic provider output digest when used;
- validator profile/version;
- proposal digest;
- every admission/rejection decision;
- duplicate/conflict lookup refs and snapshot;
- Store expected Head and result;
- resulting revision content hash;
- final FormationResult digest.

Raw hidden benchmark answers, unauthorized content and model chain-of-thought are forbidden in replay evidence.

Deterministic fixtures require `100%` equivalent replay across at least three repetitions.

---

## 16. Failure and degraded behavior

| Failure | Required behavior |
|---|---|
| Primary M1B Store unavailable | block durable formation write |
| Namespace/ACL unknown | reject/block; never widen authority |
| Source hash missing/mismatch | reject |
| Evidence unresolved/fabricated | reject |
| Current Requirement authority unknown | reject current-fact formation or preserve only explicitly historical Episode |
| Hidden benchmark/evaluator contamination | reject and invalidate descendant formation |
| Proposal provider unavailable | deterministic-only rule may continue; otherwise `DEGRADED`/no write |
| Budget exhausted | return explicit bounded result; no unbounded retry |
| Duplicate index unavailable | safe Primary fallback or no duplicate suppression; never cross Namespace |
| Conflict resolver unavailable | preserve conflict, do not pick winner |

Formation does not retry authority failures. Default proposal-provider retry maximum is one.

---

## 17. Observability

Required metrics/events:

- formation requests by mode and Kind;
- candidates proposed / accepted / rejected after authorization;
- rejection reason family;
- duplicate suppression count;
- conflict/quarantine count;
- source/evidence integrity failures;
- contamination/poisoning rejection count;
- budget consumption and latency;
- Store CAS conflicts;
- replay-equivalence failures.

Forbidden observability:

- raw Secret/personal content;
- hidden benchmark answer;
- unauthorized candidate/source counts before authorization;
- model chain-of-thought.

---

## 18. Security and privacy boundaries

M1C implementation proof uses synthetic or repository-owned non-production fixtures.

Forbidden:

- Secret acquisition or validation;
- personal/sensitive production data;
- raw environment credential persistence;
- copying unrestricted Session/chat history;
- storing hidden evaluator answers;
- direct main write;
- autonomous shared-memory publication;
- autonomous Procedure/Skill promotion or permission expansion.

---

## 19. Acceptance thresholds

Critical thresholds:

```text
Implicit Session → durable Memory write              = 0
New durable long-lived candidate initial state       = 100% CANDIDATE
Unauthorized cross-Namespace formation               = 0
Unsupported/fabricated provenance accepted           = 0
Hidden benchmark/evaluator contamination accepted    = 0
Oracle/Policy/Permission mutation by formation       = 0
Executable payload admitted outside approved ref     = 0
Critical poisoning mutation survivors                = 0
Deterministic replay equivalence                      = 100%
Authenticated idempotency equivalence                = 100%
M1B Store/retrieval critical safety regressions      = 0
```

Quality targets for declared formation datasets:

- required fact extraction recall: `100%` for explicitly labeled critical facts;
- noncritical candidate precision: at least `90%`;
- duplicate suppression determinism: `100%`;
- conflict surfacing determinism: `100%`;
- Hot formation default p95: at most `1,000 ms` excluding Store commit on the declared reference profile.

Efficiency cannot compensate for an authority, provenance, contamination or safety failure.

---

## 20. Implementation slices and gate

After this SPEC is approved and merged:

### M1C-I1 Hot Formation

Implement deterministic Run/Event → Candidate formation into the durable M1B Store with provenance, idempotency, duplicate/conflict handling and replay evidence.

### M1C-I2 Consolidation

Implement bounded background consolidation over explicitly authorized/retrieved inputs, parent refs, derivation-depth limits and Candidate-only outputs.

### M1C-I3 Poisoning / Replay Gate

Prove prompt-injection, fabricated citation, stale authority, cross-Namespace mixing, evaluator contamination, executable payload, flooding, recursive poison amplification and replay mutations are all detected.

M1C is complete only after I1–I3, full CI/security, main verification and cleanup are green.

---

## 21. Out of scope

- M1D shared-memory visibility and membership policy;
- M1E evidence-driven Procedure/Skill promotion;
- self-modifying Capability runtime;
- production/personal data;
- Secret handling;
- M2 model-tier routing;
- M3 cross-project generalization;
- changing Requirement/Oracle/Policy/Permission authority.
