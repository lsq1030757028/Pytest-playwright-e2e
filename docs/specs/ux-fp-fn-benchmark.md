# UX False-Positive / False-Negative Benchmark SPEC

> SPEC ID: `SPEC-UX-FP-FN-BENCHMARK@0.1.0`  
> Goal: Issue #60  
> Parent Campaign: Issue #59  
> Parallel-control Goal: Issue #55  
> Status: `CANDIDATE`  
> Standing mandate: `MANDATE-AUTONOMY-M1-M3@1.0.0`  
> Assurance: `DEV3 / UX2`  
> Work Item: `UX-FP-FN-BENCHMARK-SPEC`

## 1. Business outcome

The Harness can prove that a Synthetic User or UX evaluator distinguishes real user-visible defects from healthy behavior instead of merely producing persuasive findings.

The benchmark must measure both error directions:

- **false positive** — healthy behavior is reported as a defect;
- **false negative** — a seeded defect is missed or declared healthy;
- **critical false green** — a critical defect receives a passing, releasable, or otherwise success-equivalent result;
- **unsafe overconfidence** — evidence is missing or contradictory but the evaluator emits an authoritative verdict.

This SPEC defines the benchmark contract only. It does not implement the runtime, promote the UX Gate beyond `SHADOW`, or replace Human UAT.

## 2. Authority and scope

Authority comes from Goal #60, Campaign #59, Goal #55 and the active M1–M3 mandate.

In scope:

- benchmark scenario and task taxonomy;
- authoritative business and technical Oracle references;
- deterministic mutation families;
- scoring and acceptance thresholds;
- repeated-run and replay rules;
- evidence bundle and provenance requirements;
- model/provider-neutral evaluator inputs and outputs;
- benchmark-poisoning, leakage and selective-reporting controls;
- UX2 review and Human UAT boundary;
- rollback of any later Advisory or Blocking promotion.

Out of scope:

- runtime benchmark implementation before this SPEC is approved and merged;
- changes to Requirement, Oracle, Experience Oracle, Policy or Permission;
- production or personal data;
- Secrets, real devices, deployment or irreversible writes;
- direct writes to `main`;
- M4, M5 or M6 product capability claims;
- promotion of Synthetic User findings to authoritative blockers.

## 3. Protected invariants

The benchmark and any later implementation must preserve:

```text
AI-only authoritative blocker = 0
Critical False Green = 0
Unauthorized Oracle / Policy / Permission change = 0
Evaluator access to hidden expected verdict = 0
Production or personal data use = 0
Human UAT replacement = 0
Direct main write = 0
```

A benchmark result cannot lower an existing functional, security, release, privacy or Human UAT gate.

## 4. Benchmark unit

A benchmark unit is an immutable `BenchmarkScenario` with:

- stable scenario ID and version;
- task and journey reference;
- persona and pinned `ExperienceEnvironment` reference;
- target code, fixture, browser, evaluator and step revisions;
- scenario class;
- severity;
- authoritative Oracle references;
- mutation reference when applicable;
- evidence obligations;
- expected safe outcome;
- scoring eligibility;
- deterministic seed and time controls;
- rollback or reset action.

A benchmark run is invalid when any pinned revision, fixture, target hash, Oracle reference or required evidence item is absent or mismatched.

## 5. Scenario taxonomy

### 5.1 Healthy controls

Healthy scenarios exercise correct product behavior and must not produce defect findings.

Required healthy-control classes:

- normal success path;
- valid empty state;
- expected loading and latency within the declared budget;
- expected recoverable validation error;
- supported interruption and resume;
- supported route, refresh and persistence behavior;
- supported keyboard and accessibility interaction;
- intentional copy or presentation variation that does not change the Oracle.

### 5.2 Seeded defects

Defect scenarios introduce one declared mutation into an otherwise identical healthy control. A scenario should contain one primary causal mutation unless the scenario explicitly measures interacting faults.

Required mutation families:

1. `MISSING_FEEDBACK` — an accepted action provides no observable confirmation;
2. `VISIBLE_SUCCESS_STATE_LOSS` — success is reported but the visible state or persisted result disappears;
3. `KEYBOARD_FOCUS_SEMANTIC_BARRIER` — a required task cannot be completed or understood through the declared keyboard/accessibility path;
4. `INTERRUPTED_RESUME_FAILURE` — interruption causes loss, duplication or an unrecoverable state;
5. `FILTER_ROUTE_STATE_DRIFT` — route/filter state and visible business state diverge;
6. `FALSE_SUCCESS_SIGNAL` — the UI reports success while the authoritative business state failed;
7. `STALE_OR_MISMATCHED_EVIDENCE` — screenshots, traces or state probes do not correspond to the tested code/environment;
8. `AUTH_OR_PERMISSION_BYPASS_SIGNAL` — the visible journey exposes an action or result outside the declared authority;
9. `DATA_INTEGRITY_SIGNAL` — duplication, loss, corruption or cross-scope leakage is user-visible or evidence-visible;
10. `RECOVERY_MASKING_FAILURE` — retry, refresh or fallback hides the original defect without restoring the Oracle.

The first five families preserve compatibility with the existing UX mutation proof. New families extend the benchmark to critical false-green risks.

### 5.3 Ambiguous and insufficient-evidence controls

These scenarios intentionally remove or contradict evidence. The safe expected outcome is `INCONCLUSIVE` or `BLOCKED_INSUFFICIENT_EVIDENCE`, never `PASS` or an authoritative defect verdict.

### 5.4 Oracle-conflict controls

These scenarios present conflicting or stale Oracle references. The evaluator must stop as `ORACLE_CONFLICT` and identify the conflict without choosing a lower-authority source.

## 6. Oracle model

Each scenario declares separate authorities:

- **Business Oracle** — expected user-visible business outcome;
- **Technical Oracle** — deterministic state, trace, API, DOM, persistence or artifact fact used to observe the outcome;
- **Experience Oracle** — approved interpretation of whether the observed outcome satisfies the user journey;
- **Safety Oracle** — any auth, privacy, integrity, destructive-action or release-protection invariant.

Authority order follows `AGENTS.md` and the GitHub development SSOT. The evaluator sees only the task, target, declared observation capabilities and evidence it would have in a real run. Hidden mutation identity and expected verdict remain verifier-only.

An Oracle revision change creates a new scenario version. Historical results are preserved and marked `REQUIRES_RERUN`; they are never silently reinterpreted.

## 7. Evaluator output contract

A normalized evaluator result contains:

- scenario ID/version and run ID;
- target, environment, evaluator and Oracle revisions;
- verdict: `CLEAN`, `DEFECT_FOUND`, `INCONCLUSIVE`, `BLOCKED_INSUFFICIENT_EVIDENCE`, `ORACLE_CONFLICT`, or `INVALID_SCENARIO`;
- candidate findings with journey step, observation, expected Oracle, actual evidence and severity;
- alternative explanations and uncertainty;
- evidence references and hashes;
- release effect fixed to `NONBLOCKING_SHADOW` in the initial implementation;
- runtime statistics and model/provider profile reference;
- replay digest.

The evaluator may produce only Candidate Findings. The deterministic verifier computes benchmark labels and scores.

## 8. Scoring contract

For a valid, scoring-eligible run:

| Scenario truth | Evaluator result | Label |
|---|---|---|
| healthy | `CLEAN` | true negative |
| healthy | `DEFECT_FOUND` | false positive |
| seeded defect | `DEFECT_FOUND` and finding binds to the mutated Oracle | true positive |
| seeded defect | `CLEAN` | false negative |
| seeded defect | `DEFECT_FOUND` only for unrelated noise | false negative plus extraneous finding |
| insufficient evidence | `INCONCLUSIVE` or `BLOCKED_INSUFFICIENT_EVIDENCE` | safe abstention |
| insufficient evidence | `CLEAN` or authoritative `DEFECT_FOUND` | unsafe overconfidence |
| Oracle conflict | `ORACLE_CONFLICT` | safe authority stop |
| Oracle conflict | any authoritative pass/fail verdict | authority violation |

`INCONCLUSIVE` cannot be used to improve false-positive or false-negative rates. A required scorable scenario that returns `INCONCLUSIVE` fails completion coverage and must be diagnosed.

A **critical false green** occurs when a critical seeded defect receives `CLEAN`, a success-equivalent release effect, or any downstream state that treats the journey as safe to release.

Metrics:

```text
false_positive_rate = FP / (FP + TN)
false_negative_rate = FN / (FN + TP)
precision = TP / (TP + FP)
recall = TP / (TP + FN)
completion_coverage = scored_required_runs / required_runs
replay_match_rate = byte-equivalent normalized verifier results / replayed_results
critical_false_green_count = count of critical mutations with success-equivalent outcome
```

Zero denominators make the benchmark invalid rather than producing a perfect score.

## 9. Required run matrix

Every canonical scenario runs at least three times with identical pinned inputs and distinct run IDs. The baseline matrix must include:

- every healthy control paired with its corresponding mutation when one exists;
- all required mutation families;
- at least two declared personas;
- keyboard and pointer input modes where the journey supports both;
- one declared recovery path;
- one ambiguous/insufficient-evidence scenario;
- one Oracle-conflict scenario;
- deterministic no-model verifier replay.

Model/provider experiments may be added, but the benchmark contract cannot depend on a provider name. Each result records a versioned capability profile.

## 10. Acceptance thresholds

The initial benchmark is acceptable only when:

- canonical healthy controls have `false_positive_rate = 0` across all required repetitions;
- critical mutation recall is `100%`;
- noncritical mutation recall is at least `95%`;
- overall precision is at least `95%`;
- required completion coverage is `100%`;
- normalized independent replay match rate is `100%`;
- critical false-green count is `0`;
- unsafe overconfidence and authority violations are `0`;
- evaluator leakage detections are `0`;
- rollback/reset succeeds for every mutable fixture;
- all result, evidence and configuration hashes verify.

Threshold changes require a versioned SPEC or Policy Event. Safety thresholds may not be lowered to obtain a passing result.

## 11. Evidence bundle

Each run emits an immutable evidence bundle containing:

- scenario manifest and all revision references;
- normalized evaluator input and output;
- deterministic verifier result;
- business, technical, experience and safety Oracle references;
- mutation manifest stored separately from evaluator-visible input;
- Playwright trace, screenshots and video when selected;
- DOM/accessibility snapshots and state probes when selected;
- network/console evidence when selected and redacted;
- target code and fixture hashes;
- timestamps, seeds and environment manifest;
- replay command metadata and digest;
- reset/rollback result;
- omission reasons for skipped evidence layers.

The bundle index must be human-readable and machine-verifiable. Secrets, personal data and evaluator-only expected answers must not appear in actor-visible evidence.

## 12. Threat model and anti-poisoning controls

Threats include:

- evaluator sees the mutation name or expected verdict;
- scenario IDs encode the answer;
- healthy and mutated fixtures drift beyond the declared mutation;
- only successful runs are retained;
- evidence belongs to another code/environment revision;
- repeated runs reuse cached verdicts;
- ambiguous scenarios are excluded after failure;
- model/provider-specific wording overfits the evaluator;
- a Candidate Finding silently becomes a blocker;
- a benchmark result is used to weaken Human UAT or another gate.

Controls:

- separate actor and verifier manifests;
- opaque randomized actor-visible scenario aliases;
- structural diff proving one declared mutation;
- immutable full run index including failures and invalid runs;
- content hashes for target, environment, evidence and results;
- independent verifier and replay;
- deterministic seed registry;
- no result deletion or threshold editing inside a run;
- model-neutral normalized contracts;
- fixed initial release effect `NONBLOCKING_SHADOW`;
- versioned policy promotion with verified rollback.

## 13. Verification layers

Selected for the future implementation:

- schema and policy validation for manifests and result contracts;
- unit/property tests for scoring, zero denominators and threshold boundaries;
- contract tests for Oracle authority and evaluator/verifier separation;
- real Playwright boundary runs for healthy and mutated journeys;
- negative tests for missing, stale and mismatched evidence;
- leakage and benchmark-poisoning adversarial tests;
- three-run stability and independent replay;
- rollback/reset proof;
- full repository CI.

Skipped in the SPEC phase:

- runtime code and production gate integration;
- real customer data or accounts;
- real devices;
- Advisory or Blocking promotion.

## 14. Human UAT boundary

Human UAT remains required for final product judgment. The benchmark may improve confidence and produce a review-ready report, but it cannot:

- approve design quality by itself;
- change an Experience Oracle;
- convert a Candidate Finding into an authoritative blocker;
- waive uncovered personas, environments or journeys;
- promote the UX Gate beyond `SHADOW`.

Any later `ADVISORY` or `BLOCKING` promotion requires the versioned policy conditions in `docs/ux-assurance-ssot.md`, including benchmark pass, mutation proof, independent replay, critical false green zero and rollback verification.

## 15. Implementation boundary

After this SPEC is approved and merged, implementation may create:

- versioned scenario, Oracle, mutation and environment schemas;
- deterministic scorer and verifier;
- Playwright benchmark runner adapters;
- evidence-bundle writer and replay verifier;
- canonical healthy/mutated fixtures;
- dedicated GitHub Actions evidence gate;
- reports for Human UAT readiness.

Implementation must occur in a separate Work Item and PR. This SPEC does not authorize runtime code on the SPEC branch.

## 16. Deployment, rollback and recovery

The SPEC phase has no deployment or production data migration.

Future benchmark runtime rollback is:

1. set the UX release effect to `NONBLOCKING_SHADOW` or disable the benchmark workflow;
2. preserve all scenarios, results and evidence;
3. revoke any later Advisory/Blocking Policy Event through a versioned rollback event;
4. restore the previous known-good benchmark and evaluator revisions;
5. rerun affected evidence before reconsidering promotion.

A failed benchmark blocks promotion, not unrelated functional development unless an independent functional or safety gate also fails.

## 17. SPEC acceptance criteria

The SPEC is ready for approval only when:

- Markdown and machine-readable contracts agree;
- scenario taxonomy covers healthy, mutated, insufficient-evidence and Oracle-conflict cases;
- Oracle and mutation definitions are deterministic and leakage-resistant;
- scoring labels, zero-denominator behavior and thresholds are falsifiable;
- evidence, replay, poisoning controls and rollback are explicit;
- UX2 and Human UAT boundaries are truthful;
- dedicated SPEC checks and full CI pass;
- Review Threads and blockers are zero;
- final diff remains SPEC-only and within Goal #60.
