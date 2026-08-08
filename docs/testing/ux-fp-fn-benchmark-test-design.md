# UX False-Positive / False-Negative Benchmark Test Design

> SPEC: `SPEC-UX-FP-FN-BENCHMARK@0.1.0`  
> Goal: Issue #60  
> Profile: `DEV3 / UX2`  
> Phase: SPEC verification and future implementation obligations

## 1. Purpose

Prove that the benchmark contract can detect both evaluator error directions, fail safely on missing or conflicting evidence, resist expected-answer leakage and preserve Human UAT and release-policy boundaries.

This document separates:

- **SPEC-phase evidence** — validates the current documentation and machine contract;
- **future implementation evidence** — mandatory before any runtime benchmark or UX Gate promotion.

## 2. Test obligations

| ID | Obligation | Failure mode | Oracle | Minimum evidence |
|---|---|---|---|---|
| O1 | Healthy controls produce no defect finding | evaluator invents a defect | approved healthy Business/Experience Oracle | paired healthy runs, FP scorer tests, three-run stability |
| O2 | Seeded defects are detected | evaluator declares mutated behavior healthy | verifier-only mutation and Oracle | canonical mutation matrix, FN scorer tests, real Playwright boundary evidence |
| O3 | Critical defects cannot be averaged away | aggregate score hides a critical miss | critical false-green invariant | independent hard-zero assertion and critical scenario report |
| O4 | Findings bind to the actual mutation | unrelated noise is counted as a hit | mutated Oracle and causal step | finding-to-Oracle binding contract test |
| O5 | Missing evidence fails safely | absent trace/state probe receives pass | evidence obligations | negative missing-evidence scenarios |
| O6 | Conflicting authority stops evaluation | stale Oracle is silently selected | authority order | Oracle-conflict contract tests |
| O7 | Expected truth remains hidden | evaluator infers mutation from input | actor/verifier separation | leakage scans, canary fields and opaque aliases |
| O8 | Healthy/mutated pairs differ only as declared | fixture drift makes detection trivial | mutation allowlist | structural diff verifier |
| O9 | All required runs are retained | failures omitted from aggregate | predeclared run matrix | append-only run index and 100% completion coverage |
| O10 | Evidence belongs to the declared revision | passing evidence is reused | content hashes and revision refs | cross-revision rejection tests |
| O11 | Replay is deterministic | recomputation changes verdict/score | normalized deterministic verifier | independent replay 100% |
| O12 | Reset and rollback are reliable | mutation leaks into later runs | fixture reset Oracle | reset proof and post-reset healthy control |
| O13 | AI remains non-authoritative | Candidate Finding changes a gate | UX Assurance SSOT | result-schema and release-effect tests |
| O14 | Sensitive data is excluded | trace contains real data or Secret | synthetic fixture policy | redaction/denylist negative tests |
| O15 | Thresholds cannot move after results | failed result passes by editing policy | approved SPEC revision | immutable threshold reference and change-event test |

## 3. SPEC-phase evidence

The current PR must provide:

1. Markdown and YAML identifiers, authority, profiles and phase agree;
2. every required mutation family exists in both human and machine contracts;
3. verdicts and scoring mappings cover healthy, defect, insufficient-evidence and Oracle-conflict scenarios;
4. zero denominators invalidate the benchmark;
5. `INCONCLUSIVE` cannot improve FP/FN rates;
6. canonical healthy false-positive threshold is exactly zero;
7. critical mutation recall, completion coverage, replay and reset are exactly one;
8. critical false green, unsafe overconfidence, authority violation and evaluator leakage are zero;
9. release effect is `NONBLOCKING_SHADOW` and AI-only blocker is forbidden;
10. runtime implementation is explicitly deferred to a separate post-merge Work Item;
11. threat controls cover leakage, fixture drift, selective reporting, cross-revision evidence, cache reuse, threshold manipulation and rollback;
12. no touched path belongs to PR #45 or the M1A memory-runtime domain.

The **zero canonical FP threshold** requirement is absolute: the canonical healthy-behavior baseline permits no false-positive verdicts.

## 4. Future canonical scenario matrix

### 4.1 Healthy controls

Each control runs at least three times:

- normal success;
- valid empty state;
- bounded loading;
- recoverable validation error;
- interruption/resume that preserves state;
- route/refresh/persistence behavior;
- keyboard/accessibility path;
- Oracle-preserving presentation variation.

Expected result: `CLEAN`. Any bound Candidate Finding is a false positive.

### 4.2 Mutated controls

Each required mutation family is paired with the closest healthy control:

- `MISSING_FEEDBACK`;
- `VISIBLE_SUCCESS_STATE_LOSS`;
- `KEYBOARD_FOCUS_SEMANTIC_BARRIER`;
- `INTERRUPTED_RESUME_FAILURE`;
- `FILTER_ROUTE_STATE_DRIFT`;
- `FALSE_SUCCESS_SIGNAL`;
- `STALE_OR_MISMATCHED_EVIDENCE`;
- `AUTH_OR_PERMISSION_BYPASS_SIGNAL`;
- `DATA_INTEGRITY_SIGNAL`;
- `RECOVERY_MASKING_FAILURE`.

Expected result: `DEFECT_FOUND` with at least one finding bound to the mutated Oracle and causal journey step.

### 4.3 Insufficient-evidence controls

Remove or corrupt one required evidence item without exposing the expected answer.

Expected result: `INCONCLUSIVE` or `BLOCKED_INSUFFICIENT_EVIDENCE`. `CLEAN` and authoritative defect verdicts are unsafe overconfidence.

### 4.4 Oracle-conflict controls

Provide two incompatible Oracle revisions with the normal authority metadata.

Expected result: `ORACLE_CONFLICT`. The evaluator must identify references and stop without selecting a lower-authority source.

## 5. Scoring tests

Deterministic scorer tests must include:

- healthy + `CLEAN` → true negative;
- healthy + `DEFECT_FOUND` → false positive;
- defect + bound `DEFECT_FOUND` → true positive;
- defect + `CLEAN` → false negative;
- defect + unrelated `DEFECT_FOUND` → false negative with extraneous finding;
- insufficient evidence + safe abstention → safe abstention;
- insufficient evidence + pass/fail authority → unsafe overconfidence;
- Oracle conflict + `ORACLE_CONFLICT` → safe authority stop;
- Oracle conflict + authoritative verdict → authority violation;
- no healthy denominator → invalid benchmark;
- no defect denominator → invalid benchmark;
- critical false green fails independently of aggregate precision/recall;
- missing required run lowers completion coverage and fails acceptance;
- exact threshold boundary passes, one value below fails.

Property tests should generate confusion matrices and prove:

- adding a false positive never improves precision;
- adding a false negative never improves recall;
- adding an unscored inconclusive result never improves FP/FN rates;
- any critical false green keeps the benchmark failed;
- result ordering does not change normalized aggregate output.

## 6. Actor/verifier separation tests

Adversarial cases:

- actor manifest contains `expected_verdict`;
- actor manifest contains mutation family name;
- actor-visible scenario ID contains `healthy`, `broken`, `expected-fail` or equivalent;
- filename or environment variable reveals the answer;
- evaluator prompt contains verifier-only assertions;
- screenshot alt text or fixture copy leaks the mutation label;
- cached model response is supplied without current execution evidence.

Every case must be rejected before scoring.

## 7. Structural mutation tests

The fixture verifier must prove:

- healthy and mutated targets share the declared base revision;
- exactly one primary allowlisted mutation exists for canonical scenarios;
- unrelated file, fixture, copy, timing or environment drift invalidates the scenario;
- interacting faults require an explicit multi-fault declaration;
- reset restores the healthy target digest.

## 8. Evidence and provenance tests

Required negative cases:

- target SHA mismatch;
- fixture revision mismatch;
- environment/browser revision mismatch;
- missing Oracle reference;
- stale screenshot or trace;
- state probe from another run;
- evidence hash mismatch;
- missing failed run in aggregate index;
- duplicate run ID;
- missing reset result;
- prohibited data or Secret-like value in an artifact;
- actor evidence contains verifier-only manifest.

All fail closed with diagnosable reason codes.

## 9. Real boundary evidence

The future implementation must use the real pinned Playwright target and observe the actual user journey. Selected evidence depends on the Oracle and may include:

- Playwright trace and screenshots;
- DOM and accessibility snapshot;
- route and visible-state probes;
- deterministic persistence or API probe;
- redacted console/network records;
- interruption and resume actions;
- keyboard and pointer execution.

Mocks may isolate unrelated infrastructure but cannot replace the Business, Experience or Safety truth boundary.

## 10. Stability and replay

For every canonical scenario:

- execute three independent runs;
- retain each normalized evaluator output and raw evidence bundle;
- replay the deterministic verifier without a model;
- require byte-equivalent normalized verifier results;
- report evaluator variance separately from deterministic replay;
- prohibit cached canonical execution.

Required acceptance: `replay_match_rate = 1.0` and `completion_coverage = 1.0`.

## 11. Rollback and recovery tests

- fixture reset restores the healthy control and its digest;
- failed reset quarantines the environment and prevents the next scenario;
- workflow disablement prevents new benchmark runs while preserving evidence;
- a simulated Policy rollback restores `NONBLOCKING_SHADOW`;
- historical evidence remains addressable after rollback;
- invalidated Oracle revisions mark results `REQUIRES_RERUN` rather than silently changing them.

## 12. Selected and skipped layers

Selected for the SPEC PR:

- YAML parsing and static policy assertions;
- human/machine document consistency;
- required threat and test-design coverage;
- dedicated GitHub Actions SPEC gate;
- full repository CI and security gates;
- final diff and Review Thread inspection.

Skipped until implementation:

- runtime scorer/verifier code;
- Playwright benchmark execution;
- mutation fixtures and evidence bundles;
- model/provider repetition;
- Advisory/Blocking promotion;
- real customer data/accounts and real devices.

Skipping runtime evidence is correct only because this PR is SPEC-only. Runtime work cannot begin until the SPEC is merged.

## 13. Exit criteria

The SPEC Work Item can become `EVIDENCE_READY` only when:

- Markdown, YAML, threat model and this test design are complete and consistent;
- static tests prove all protected invariants and thresholds;
- dedicated SPEC workflow passes on the final Head;
- full CI and repository security gates pass;
- final diff contains only approved SPEC-phase assets;
- Review Threads and blockers are zero;
- Critical False Green remains zero;
- integration queue entry is created only after all evidence is green.
