# UX FP/FN Benchmark Threat Model

> SPEC: `SPEC-UX-FP-FN-BENCHMARK@0.1.0`  
> Goal: Issue #60  
> Profile: `DEV3 / UX2`  
> Status: `CANDIDATE`

## 1. Security objective

The benchmark must measure evaluator quality without leaking the expected answer, altering the tested Oracle, hiding failed runs or converting model confidence into release authority.

The protected result is not merely a score. It is an auditable statement that:

- the tested code and environment are the declared revisions;
- healthy and mutated scenarios differ only by the declared mutation;
- the evaluator did not receive the hidden truth label;
- every required run, including failures and invalid runs, is retained;
- scoring is deterministic and independently replayable;
- no Candidate Finding silently changes a product gate.

## 2. Assets

Protected assets:

- Business, Technical, Experience and Safety Oracle references;
- scenario and mutation manifests;
- actor-visible evaluator input;
- verifier-only expected truth;
- target, fixture, environment and evaluator revisions;
- Playwright trace, screenshot, DOM, accessibility and state-probe evidence;
- normalized evaluator output;
- deterministic verifier result and aggregate metrics;
- benchmark thresholds and policy mode;
- complete run index, including failed and invalid runs;
- rollback and reset evidence.

## 3. Trust boundaries

### 3.1 Authoring boundary

Scenario authors may define Oracles and mutations, but the final actor-visible package must be mechanically checked for expected-answer leakage.

### 3.2 Actor / verifier boundary

The evaluator receives only the real task and permitted evidence. Mutation identity, expected verdict, scoring label and hidden Oracle assertions remain verifier-only.

### 3.3 Target / evidence boundary

Evidence must bind to the exact target, fixture and environment revisions. Evidence from another commit, browser, seed or fixture cannot satisfy the scenario.

### 3.4 Model / deterministic policy boundary

Models produce Candidate Findings. Deterministic code validates provenance, computes labels and applies thresholds. A model cannot assign its own authoritative score or release effect.

### 3.5 Benchmark / release boundary

The initial benchmark is `NONBLOCKING_SHADOW`. Any Advisory or Blocking use requires a separate versioned Policy Event, qualifying evidence and verified rollback.

## 4. Threat actors and failure sources

The model covers intentional attackers and accidental failure sources:

- scenario author who unintentionally encodes the expected answer;
- evaluator or prompt that overfits filenames, IDs or mutation wording;
- implementation that reuses cached verdicts;
- CI or artifact collection that associates evidence with the wrong revision;
- result aggregator that omits failures or invalid runs;
- threshold editor who changes acceptance after seeing results;
- stale Oracle or fixture revision;
- model/provider drift;
- malicious or corrupted benchmark fixture;
- Agent attempting to turn a Candidate Finding into an authoritative blocker;
- reviewer relying on a high aggregate score while a critical scenario failed.

## 5. Threat scenarios and controls

### T1 — Expected verdict leakage

**Attack:** actor-visible scenario text, filename, environment variable or artifact contains the mutation name or expected label.

**Impact:** inflated true-positive rate and meaningless benchmark.

**Controls:**

- separate actor and verifier manifests;
- opaque actor-visible aliases;
- denylist and structural scan for verifier-only fields;
- adversarial canary labels that must not be recoverable from actor input;
- record actor-input digest in the evidence bundle.

### T2 — Healthy/mutated fixture drift

**Attack:** the mutated fixture differs in unrelated ways, making detection easier or changing the Oracle.

**Impact:** invalid causal attribution.

**Controls:**

- one primary mutation per canonical scenario;
- structural diff against the healthy control;
- allowlisted mutation paths;
- explicit interacting-fault declaration;
- invalid scenario on unexplained drift.

### T3 — Evidence revision substitution

**Attack:** screenshots, traces or probes from a passing run are attached to a failing revision.

**Impact:** false green and broken audit.

**Controls:**

- target, environment, fixture and evidence hashes;
- code SHA embedded in manifests and artifacts;
- verifier rejects cross-revision evidence;
- immutable run ID and bundle digest.

### T4 — Selective reporting

**Attack:** failed, invalid, slow or inconclusive runs are omitted from the aggregate.

**Impact:** biased metrics and hidden instability.

**Controls:**

- append-only required run index;
- expected run matrix generated before execution;
- completion coverage fixed at 100%;
- missing runs fail the benchmark;
- retain invalid runs with reason.

### T5 — Cached verdict reuse

**Attack:** repeated runs reuse a previous model verdict without executing the current target.

**Impact:** fabricated stability and missed regressions.

**Controls:**

- distinct run IDs and execution evidence;
- target/environment/evidence digest included in replay key;
- cache hit recorded and prohibited for canonical execution;
- no-model replay verifies stored evidence independently.

### T6 — Threshold manipulation

**Attack:** acceptance thresholds are changed after results are known.

**Impact:** passing by policy drift rather than quality.

**Controls:**

- thresholds versioned in the approved SPEC;
- result bundle records threshold revision;
- no threshold edit inside a run;
- changes require a new SPEC or Policy Event;
- safety thresholds cannot be lowered for progress.

### T7 — Ambiguity laundering

**Attack:** difficult or contradictory scenarios are marked non-scorable after failure.

**Impact:** lower measured false-negative rate.

**Controls:**

- scoring eligibility declared before execution;
- insufficient-evidence and Oracle-conflict controls are first-class required scenarios;
- `INCONCLUSIVE` does not improve FP/FN metrics;
- required inconclusive results fail completion coverage unless the safe abstention is the declared Oracle.

### T8 — Provider or prompt overfit

**Attack:** evaluator prompt is tuned to exact scenario wording or a provider-specific behavior.

**Impact:** benchmark does not generalize.

**Controls:**

- model-neutral normalized contract;
- versioned capability profiles;
- opaque scenario aliases and wording variants;
- deterministic verifier independent of provider;
- future cross-model repetition before gate promotion.

### T9 — Candidate finding authority escalation

**Attack:** an AI finding directly blocks merge, changes an Experience Oracle or marks a release unsafe without deterministic authority.

**Impact:** unauthorized Policy/Oracle change and false positive harm.

**Controls:**

- result schema fixes findings as Candidates;
- release effect fixed to `NONBLOCKING_SHADOW`;
- AI-only blockers forbidden;
- Human UAT retained;
- promotion requires a versioned Policy Event and rollback proof.

### T10 — Critical defect hidden by aggregate score

**Attack:** strong performance on many low-severity cases masks one critical false green.

**Impact:** unsafe release.

**Controls:**

- critical false-green count is an independent hard invariant of zero;
- critical recall is 100%;
- aggregate score cannot compensate for a critical failure;
- report critical scenarios individually.

### T11 — Sensitive data capture

**Attack:** traces or screenshots contain real customer data, credentials or Secrets.

**Impact:** privacy or security incident.

**Controls:**

- synthetic fixtures only;
- no production accounts or personal data;
- artifact redaction and denylist checks;
- fail closed before upload when a prohibited value is detected.

### T12 — Reset or rollback failure

**Attack:** mutated state leaks into the next scenario or a promoted gate cannot be disabled.

**Impact:** cross-test contamination and persistent false decisions.

**Controls:**

- reset/rollback reference required for every mutable fixture;
- reset result included in each bundle;
- reset success rate must be 100%;
- gate rollback restores `NONBLOCKING_SHADOW` and preserves evidence.

## 6. Abuse cases

The implementation must reject:

- scenario identifiers containing `healthy`, `broken`, `expected-fail` or an equivalent answer signal in actor-visible input;
- actor manifests containing verifier-only fields;
- scoring with no healthy or no defect denominator;
- aggregate success when any critical false green exists;
- evidence whose code/environment digest differs from the manifest;
- deletion of failed run records;
- direct use of evaluator confidence as a score;
- Advisory/Blocking release effect without a qualifying Policy Event;
- real account, Secret, production data or unbounded external browsing.

## 7. Residual risks

Residual risks after the initial design:

- Experience Oracles may still be incomplete or subjective;
- the canonical scenario set may underrepresent real product diversity;
- models may learn benchmark patterns over time;
- deterministic evidence can prove the declared Oracle but not undiscovered user needs;
- browser and environment nondeterminism may require additional stabilization evidence;
- zero canonical false positives does not prove zero false positives in all future products.

These risks require transparent coverage reports, periodic scenario refresh, Human UAT and later cross-model/cross-project evidence. They do not justify lowering the initial thresholds.

## 8. Security acceptance

The SPEC package is security-reviewable only when:

- all threats above map to explicit controls and tests;
- actor/verifier separation is machine-validated;
- cross-revision evidence and selective reporting fail closed;
- critical false green remains an uncompensated zero invariant;
- production/personal data and Secrets remain excluded;
- release effect remains `NONBLOCKING_SHADOW`;
- rollback and reset are explicit and testable;
- no change touches PR #45 or the M1A memory-runtime domain.
