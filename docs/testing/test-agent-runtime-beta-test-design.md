# TEST_AGENT_RUNTIME_BETA SPEC Test and UAT Design

> Test Design: `TD-TEST-AGENT-RUNTIME-BETA@0.1.0`  
> SPEC: `SPEC-TEST-AGENT-RUNTIME-BETA@0.1.0`  
> Goal: Issue #66  
> Assurance: `DEV3 / UX3`

## 1. Purpose

Prove that the proposed architecture forms a falsifiable path to a user-runnable Test Agent Beta and does not merely rename horizontal infrastructure as a product.

This document defines SPEC-phase evidence and the implementation evidence that later slice Goals must produce.

## 2. SPEC-phase obligations

### 2.1 Identity and authority

- SPEC ID/version/status are consistent across Markdown and YAML.
- Goal #66 and Campaign #65 are referenced.
- M1–M3 standing mandate remains explicitly unextended.
- M4–M6 work requires the explicit owner authority.
- Runtime implementation is absent from the SPEC PR.

### 2.2 Product journey completeness

The machine and Markdown contracts must include:

- submit/status/result/cancel/events CLI;
- pinned project and objective intake;
- durable job state;
- plan, generation, execution, diagnosis, repair/re-run and verdict;
- restart recovery;
- evidence bundles and replay;
- two-project final acceptance;
- Human UAT.

### 2.3 State and concurrency

Validate:

- unique lifecycle states;
- declared terminal states are a subset of lifecycle states;
- stale writes produce explicit conflicts;
- duplicate submission/delivery is idempotent;
- worker lease and restart rules forbid uncertain duplicate effects;
- cancellation and timeout are terminal and evidence-aware.

### 2.4 Safety boundaries

Assert exact zero thresholds for:

- critical false greens;
- unauthorized product-source repair;
- unauthorized Oracle/Policy/Permission changes;
- cross-project data/Memory leakage;
- unbounded retry/spend;
- unverifiable success;
- Secret/personal-data exposure;
- duplicate uncertain restart side effects;
- AI-only release authority.

### 2.5 Vertical delivery

Validate five slices `BETA-A` through `BETA-E`, dependency closure and product outcomes.

Every slice must prove an operational journey. No slice may be named only for a database, queue, model, Memory or framework.

### 2.6 Budget boundaries

Validate finite positive limits for job time, planning, execution attempt, repair cycles, attempts, workers, browser contexts, patch size and artifact size.

## 3. Dedicated SPEC gate

The dedicated Workflow runs:

1. Ruff against the SPEC tests;
2. YAML parse and cross-file assertions;
3. focused Pytest;
4. full repository CI through the normal baseline;
5. repository Secret Scan and CodeQL through existing Workflows.

No runtime artifact is required in the SPEC phase.

## 4. Implementation evidence by slice

## 4.1 Slice A — existing governed pack

Selected evidence:

- real CLI submit/status/result/cancel;
- FastAPI/control-plane contract test if HTTP is used internally;
- SQLite WAL persistence and restart test;
- queue/lease idempotency and stale-worker race test;
- real Pytest + Playwright execution;
- JUnit, logs, screenshot/trace where selected;
- evidence bundle hash/replay;
- process-tree cancellation;
- package/container smoke job.

Mutation/negative evidence:

- duplicate submit;
- stale expected revision;
- worker lease expiry;
- missing artifact;
- cancellation during browser execution;
- restart before/after durable checkpoint;
- budget exhaustion.

## 4.2 Slice B — requirement to generated test

Selected evidence:

- project inspection on a pinned commit;
- authoritative objective/Oracle manifest;
- bounded plan and context manifest;
- generated test patch limited to allowed paths;
- lint/import/collection;
- real browser execution;
- review trace to job/plan/Run Token;
- no product-source diff.

Mutation/negative evidence:

- repository prompt injection;
- model-proposed shell interpolation;
- path traversal;
- fixed sleep/blind retry;
- missing Oracle;
- generated assertion unrelated to objective.

## 4.3 Slice C — diagnosis and repair

Selected evidence:

- seeded test defect correctly classified;
- one bounded test-only repair;
- before/after patch and evidence;
- affected re-run and regression;
- seeded product defect remains product defect;
- mutation proof that assertion weakening is rejected.

Required paired cases:

1. broken selector/test fixture → `TEST_DEFECT` → repaired;
2. real product behavior mutation → `PRODUCT_DEFECT` → no product repair;
3. unavailable browser/dependency → `ENVIRONMENT_FAILURE`;
4. missing evidence → `INSUFFICIENT_EVIDENCE`;
5. stale Oracle → `ORACLE_CONFLICT`.

## 4.4 Slice D — restart and Memory

Selected evidence:

- restart control plane during planning;
- restart worker during a safe checkpoint;
- lease loss during execution;
- no duplicate attempt side effect;
- job reconstructs from durable state without Chat history;
- `MEMORY_OFF` control;
- authorized progressive Memory retrieval;
- stale/revoked/forgotten/cross-project Memory excluded;
- byte-equivalent verifier replay.

## 4.5 Slice E — two projects

At least two materially different projects must vary in architecture or test organization, not only repository name.

Required evidence:

- same entrypoint and normalized contracts;
- project-specific adapters remain bounded;
- one healthy journey produces no defect finding;
- one seeded product defect is detected;
- one test defect is repaired;
- cross-project data/Memory isolation;
- release/deployment smoke;
- user documentation;
- Human UAT.

## 5. UX3 journey evidence

Affected journey:

```text
install/open CLI
→ submit job
→ understand accepted state
→ inspect progress/events
→ see generated test patch
→ inspect evidence
→ understand verdict and limitations
→ cancel or resume
→ repeat after restart
```

Experience environments must pin persona, locale, terminal, accessibility needs, network, project fixture, code, package, evaluator, seed and time.

Synthetic User tests may identify Candidate findings. Human UAT is authoritative for:

- comprehensibility of progress states;
- trustworthiness of verdict language;
- discoverability of evidence;
- cancellation/recovery expectations;
- documentation sufficiency.

## 6. Evidence validity

An implementation run is invalid when:

- project/patch/environment revisions do not match;
- required artifacts are absent;
- evidence hashes fail;
- hidden mutation truth leaks to the actor;
- only passing attempts are retained;
- restart history is incomplete;
- cleanup cannot be proven;
- an Oracle changed without versioning;
- generated product-source changes exist;
- a critical failure is treated as success.

## 7. Selected and skipped layers

Selected in SPEC phase:

- schema and cross-file consistency;
- threat-model coverage;
- lifecycle, budget and vertical-slice validation;
- dedicated CI, full CI, Secret Scan, CodeQL;
- independent review.

Deferred to implementation:

- real CLI/API, database, worker, browser, model and deployment;
- end-to-end Beta UAT.

Skipped from initial Beta:

- private repository credentials;
- production/personal data;
- multi-tenant isolation;
- mobile/real device;
- mini-program;
- autonomous product repair.

## 8. Exit criteria

The SPEC PR is mergeable only when:

- all SPEC assets agree;
- dedicated and full checks are green;
- no runtime implementation exists;
- Review Threads and blockers are zero;
- risks, rollback and Human UAT are explicit;
- the first implementation Goal is constrained to Slice A.

The product is not `BETA` merely because this SPEC merges.
