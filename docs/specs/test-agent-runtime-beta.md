# TEST_AGENT_RUNTIME_BETA Product and Architecture SPEC

> SPEC ID: `SPEC-TEST-AGENT-RUNTIME-BETA@0.1.0`  
> Goal: Issue #66  
> Parent Campaign: Issue #65  
> Status: `CANDIDATE`  
> Work Item: `TEST-AGENT-RUNTIME-BETA-ARCHITECTURE-SPEC`  
> Authority: explicit repository-owner scope extension recorded in Issues #65 and #66  
> Standing mandate: `MANDATE-AUTONOMY-M1-M3@1.0.0` remains limited to M1–M3  
> Assurance: `DEV3 / UX3`

## 1. Business outcome

The repository delivers a usable Test Agent Beta rather than a collection of disconnected infrastructure modules.

A user can submit a supported project and a bounded testing objective, then receive a durable, evidence-backed result after the Agent:

1. inspects the pinned project revision;
2. builds a governed test plan;
3. generates or updates reviewable Pytest + Playwright tests;
4. executes them in a reproducible cloud runtime;
5. collects direct evidence;
6. classifies failures without treating model confidence as proof;
7. performs bounded test-workflow diagnosis and repair when authorized;
8. re-runs the affected tests;
9. survives a process restart and resumes the same job;
10. publishes a final verdict with traceable artifacts and limitations.

Memory, model routing, project adapters, orchestration and durable scheduling are product subsystems. None of them is a completion claim unless exercised by this operating journey.

## 2. Authority and lifecycle truth

Issues #65 and #66 provide explicit owner authority to design and implement the M1–M6 path required for this Beta, subject to the safety boundaries in those Goals.

`MANDATE-AUTONOMY-M1-M3@1.0.0` is not modified. Work in M1–M3 may use that standing mandate. Work beyond M3 must cite Issues #65 and #66 and any approved module SPEC; it must not claim that the old mandate expanded.

This SPEC approves architecture and delivery sequencing only after merge. It does not implement the runtime, deploy a service, close the Beta Campaign, or authorize production/personal data.

## 3. Beta scope

### 3.1 Supported initial journey

The initial Beta supports:

- a GitHub repository URL or repository identity accessible to the approved runtime;
- an immutable commit SHA;
- Python projects with Pytest;
- browser journeys executable through Playwright Chromium;
- a requirement, feature, bug hypothesis or regression objective;
- a declared project adapter/profile;
- one isolated job workspace;
- one documented CLI entrypoint backed by a durable control plane;
- one control-plane instance and one or more bounded workers;
- synthetic or repository-owned non-production fixtures;
- two materially different project profiles for final Beta acceptance.

### 3.2 Explicit exclusions

The initial Beta does not include:

- multi-tenant production service claims;
- arbitrary shell-as-a-service;
- private repository credential acquisition;
- production or personal data;
- real Secret copying, display or persistence;
- autonomous product-code repair;
- mobile or real-device execution;
- mini-program execution;
- unconstrained model/provider selection;
- unlimited retries, workers, duration or spend;
- direct writes to `main`;
- silent Requirement, Oracle, Experience Oracle, Policy or Permission changes;
- AI-only release authority;
- completion claims for M4, M5 or M6 without implementation evidence.

## 4. Product entrypoint

The minimum user entrypoint is a CLI that talks to the durable control plane:

```text
test-agent job submit --project <repo> --commit <sha> --objective <file> --profile <id>
test-agent job status <job-id>
test-agent job result <job-id>
test-agent job cancel <job-id>
test-agent job events <job-id>
```

A future HTTP or UI client may use the same service contract. The CLI is the accepted Beta entrypoint because it is scriptable, reviewable and sufficient to prove the operating journey.

### 4.1 Job submission contract

A submission contains:

- client-generated idempotency key;
- project repository identity;
- immutable commit SHA;
- project profile/version;
- objective manifest/version;
- permitted test paths;
- permitted runtime capabilities;
- Oracle and Experience Oracle references;
- environment profile;
- model capability profile or deterministic mode;
- timeout, repair-cycle and cost budgets;
- redaction profile;
- requested evidence layers.

The control plane rejects floating refs, unknown profiles, missing Oracle authority, unbounded budgets and unsupported capabilities.

### 4.2 Job result contract

The result contains:

- job ID and immutable final revision;
- final lifecycle state;
- normalized verdict;
- project, objective, environment and model-profile revisions;
- generated/modified test patch reference;
- plan and execution attempt references;
- evidence bundle index and hashes;
- diagnosis and repair history;
- residual limitations;
- replay command/manifest;
- Human UAT requirement;
- release effect fixed to non-authoritative Beta output.

## 5. Normalized verdicts

The final verdict is one of:

- `VERIFIED_SUCCESS` — declared objective passed with complete required evidence;
- `PRODUCT_DEFECT` — direct evidence contradicts an authoritative business, technical, experience or safety Oracle;
- `TEST_DEFECT` — generated or existing test logic is invalid, stale or inconsistent with the Oracle;
- `ENVIRONMENT_FAILURE` — runtime, dependency, browser, network or fixture failure prevents trustworthy product classification;
- `INSUFFICIENT_EVIDENCE` — required evidence is missing, stale, contradictory or unverifiable;
- `ORACLE_CONFLICT` — authority references conflict or are stale;
- `POLICY_BLOCKED` — requested capability, data or action is outside approved policy;
- `CANCELLED`;
- `TIMED_OUT`.

Only the deterministic verifier can finalize a verdict. Model output is a Candidate diagnosis or plan.

A success-equivalent verdict with missing required evidence is a critical false green.

## 6. Durable job state

### 6.1 Lifecycle

```text
DRAFT
→ ACCEPTED
→ PLANNING
→ PLAN_READY
→ GENERATING
→ READY_TO_EXECUTE
→ EXECUTING
→ DIAGNOSING
→ REPAIRING
→ READY_TO_REEXECUTE
→ REEXECUTING
→ VERDICT_READY
→ SUCCEEDED | FAILED | BLOCKED | CANCELLED | TIMED_OUT
```

Transitions are append-only events with:

- job ID;
- monotonic sequence;
- event ID;
- prior and next state;
- actor/capability identity;
- correlation and Run Token;
- expected job revision;
- project and environment revisions;
- event payload hash;
- occurred-at time;
- policy and authority references.

Duplicate command delivery must be idempotent. A stale expected revision produces an explicit conflict and cannot overwrite newer state.

### 6.2 Durable storage profile

The Beta reference deployment uses:

- SQLite in WAL mode on a persistent volume for job metadata, event log, leases and queue state;
- a filesystem artifact store on a persistent volume for immutable evidence bundles;
- content-addressed paths and SHA-256 manifests;
- explicit schema version and migration number;
- transaction boundaries that commit state only after required artifacts are durable;
- startup recovery that reconciles in-progress attempts against worker leases and artifact manifests.

This job-state store is distinct from the governed Memory Store defined by M1B. The Beta must not use job-state rows as semantic Memory or bypass M1A/M1B governance.

A later PostgreSQL/object-store profile may implement the same ports without changing the product contract.

## 7. Runtime components

1. **CLI client** — validates local input and submits or queries jobs.
2. **Control plane** — authenticates the caller, validates contracts, stores events, schedules work and exposes job state.
3. **Planner** — creates a bounded test plan from project facts, objective and authorized retrieved context.
4. **Project adapter** — inspects declared architecture and exposes approved commands, paths and capabilities.
5. **Test authoring capability** — produces reviewable test patches only in permitted test paths.
6. **Execution worker** — runs pinned Pytest/Playwright commands inside an isolated workspace.
7. **Evidence collector** — captures JUnit, logs, screenshots, traces, environment and patch manifests.
8. **Deterministic verifier** — checks evidence completeness, Oracle binding, hashes and normalized verdict rules.
9. **Diagnosis/repair controller** — performs bounded test-only repair and re-run.
10. **Durable job store and queue** — preserves lifecycle, idempotency, leases and restart state.
11. **Governed Memory adapter** — progressively retrieves only authorized, compatible Memory under M1 contracts.
12. **Release/smoke verifier** — proves the packaged/deployed Beta entrypoint and documented journey.

No component may silently promote a Candidate plan, finding, Memory or test into authority.

## 8. Project workspace and capability boundary

Every attempt uses a fresh isolated workspace identified by job ID and attempt ID.

Rules:

- checkout is pinned to the submitted commit SHA;
- the base project tree is read-only from the Agent perspective;
- generated changes are emitted as a patch and workspace overlay;
- product-source writes are denied in the initial Beta;
- allowed writes are restricted to declared test, fixture and evidence paths;
- project-defined scripts are not trusted merely because they exist;
- the adapter exposes an allowlisted command plan;
- shell interpolation from model output is forbidden;
- network access is denied by default and declared per environment profile;
- workspace path traversal and symlink escape are rejected;
- process, browser, disk, memory and time budgets are enforced;
- cancellation terminates child processes and marks incomplete evidence unusable;
- workspace reset is verified before reuse or disposal.

## 9. Planning and context assembly

A `TestPlan` contains:

- plan ID/version and job revision;
- objective decomposition;
- affected requirements and Oracles;
- project facts and architecture profile;
- selected existing tests;
- proposed generated/modified tests;
- capability and evidence plan;
- expected classifications;
- budgets and stop conditions;
- assumptions and unresolved questions;
- context manifest with exact source references;
- replay digest.

Context is loaded progressively:

1. authoritative Goal/Requirement/Oracle;
2. project profile and changed-area facts;
3. exact relevant governed Memory;
4. nearby tests and fixtures;
5. broader historical evidence only when budget and relevance justify it.

Namespace/ACL/authority filtering happens before relevance. Context budget exhaustion produces a bounded plan or `INSUFFICIENT_EVIDENCE`; it never silently drops safety authority.

## 10. Test generation contract

Generated or repaired tests must:

- be limited to approved test/fixture paths;
- trace to job ID, objective, plan and Run Token;
- use stable selectors and declared capabilities;
- avoid fixed sleeps and blind retries;
- declare fixtures and environment assumptions;
- preserve existing assertions unless a change is justified by Oracle evidence;
- pass formatting, lint, collection and import checks before execution;
- include a patch manifest and content hashes;
- remain Candidate until reviewable execution evidence exists;
- never change product source in the initial Beta.

A test patch that cannot be explained against the objective and Oracle is rejected.

## 11. Execution contract

The execution manifest pins:

- base commit;
- generated test patch hash;
- project adapter/version;
- Python and dependency lock revision;
- Pytest version;
- Playwright/browser revision;
- environment image;
- locale, timezone, viewport and network profile;
- selected test nodes;
- seeds;
- timeout and retry policy;
- evidence layers;
- worker identity and lease;
- model profile where applicable.

The worker emits attempt state and heartbeats. Loss of lease stops further writes. A restarted worker must either resume from a safe checkpoint or create a new attempt; it must not duplicate an uncertain side effect.

## 12. Evidence bundle

Every valid attempt has an immutable bundle with:

- job, plan, attempt and run manifests;
- project and patch hashes;
- command manifest;
- stdout/stderr with redaction;
- Pytest/JUnit output;
- Playwright screenshots, trace and video when selected;
- DOM/accessibility/network/console evidence when selected;
- environment and dependency manifest;
- timeout/cancellation evidence;
- diagnosis and repair records;
- deterministic verifier output;
- artifact index and SHA-256 hashes;
- reset/cleanup result;
- replay instructions;
- omission reasons for skipped layers.

The final result references evidence; it does not copy unbounded logs into Chat or Issue comments.

## 13. Diagnosis and bounded repair

Diagnosis classifies each failure before any repair:

1. product defect;
2. test defect;
3. environment failure;
4. insufficient evidence;
5. Oracle conflict;
6. policy block.

The initial Beta permits at most two repair cycles and only for test/fixture/harness files declared by the adapter.

A repair cycle must:

- preserve the original failing evidence;
- record the diagnosis and alternative explanations;
- bind the patch to the same objective and current Oracle revisions;
- re-run lint, collection and the smallest trustworthy affected test set;
- execute required regression and mutation checks;
- stop if the failure indicates a product defect, authority conflict, forbidden product-code change or repeated nondeterminism.

Repair may improve a test workflow; it cannot redefine expected product behavior.

## 14. Governed Memory integration

Memory is optional for early operating slices and mandatory for restart/reuse acceptance.

Rules:

- `MEMORY_OFF` remains a valid safe control;
- only M1A/M1B-authorized namespaces and effective revisions are retrievable;
- Memory never overrides current Requirement, Oracle, Experience Oracle, Policy or Permission;
- every retrieved item appears in the context manifest;
- stale, incompatible, conflicting, revoked, expired or forgotten Memory is excluded;
- generated observations remain Candidate;
- a job checkpoint is not automatically semantic or procedural Memory;
- a later session can reconstruct the job from durable state even when no Memory is available;
- Memory benefit is measured against the M1 benchmark, not assumed.

## 15. Resource, cancellation and cost boundaries

Initial defaults:

- wall-clock job timeout: 45 minutes;
- planning timeout: 5 minutes;
- individual execution attempt timeout: 15 minutes;
- repair cycles: maximum 2;
- execution attempts: maximum 3 including original;
- concurrent workers per job: 1;
- browser contexts per attempt: 1;
- generated patch size: maximum 2,000 changed lines;
- artifact budget: 500 MiB per job;
- model/tool budget: versioned profile with hard stop;
- no automatic resource creation outside the declared deployment.

Budget exhaustion produces `TIMED_OUT` or `POLICY_BLOCKED` with partial evidence; it does not widen limits.

## 16. Vertical operating slices

### Slice A — Execute an existing governed pack

A user submits a supported project, pinned revision and objective that maps to existing tests. The system stores a durable job, executes the pack and returns a verified evidence bundle.

Completion proves intake, durable state, worker execution, evidence, verdict, cancellation and release smoke.

### Slice B — Generate a bounded test from a requirement

The Agent builds a plan, creates a reviewable Pytest/Playwright test patch, validates it, executes it and returns evidence.

Completion proves requirement/Oracle binding, project inspection, test generation and patch traceability.

### Slice C — Diagnose, repair and re-run

A seeded test-workflow defect causes a failure. The system classifies it as a test defect, performs one bounded repair, re-runs and preserves before/after evidence.

A seeded product defect must remain `PRODUCT_DEFECT` and must not be “fixed” by weakening the test.

### Slice D — Restart recovery and governed context

The control plane or worker is restarted after a durable checkpoint. The same job resumes without duplicate execution or lost evidence. Authorized Memory may improve context, while `MEMORY_OFF` remains replayable.

### Slice E — Cross-project Beta acceptance

Two materially different supported projects complete the journey. At least one seeded product defect is detected and one healthy scenario is not falsely reported.

Completion requires documented CLI usage, release/deployment smoke, Human UAT, replayable evidence and zero critical false greens.

## 17. Slice dependencies and infrastructure mapping

- M1 Memory work supports Slice D and repeated-job quality, but Slice A must not wait for all Memory evolution.
- M2 model profiles and safe degradation support Slices B–E.
- M3 project contracts/adapters support Slice E.
- M4 orchestration is introduced only where a bounded role split improves Slices B–C.
- M5 durable runtime supplies Slice A job state and Slice D restart recovery.
- M6 is accepted only through Slice E and final Beta journey evidence.

The delivery roadmap must prefer an end-to-end thin slice over completing every horizontal subsystem first.

## 18. Threat and safety invariants

```text
Critical false green = 0
Unauthorized product-source repair = 0
Unauthorized Oracle / Policy / Permission change = 0
Cross-project data or Memory leakage = 0
Unbounded retry or spend = 0
Unverifiable success verdict = 0
Secret or personal-data exposure = 0
Duplicate uncertain side effect after restart = 0
AI-only release authority = 0
```

The detailed threat model is `docs/security/test-agent-runtime-beta-threat-model.md`.

## 19. Acceptance criteria

The architecture SPEC is acceptable when:

- the product journey and CLI contract are complete;
- lifecycle, state, API, artifact and replay contracts are falsifiable;
- five vertical slices have dependencies, evidence and rollback;
- M1–M6 infrastructure is mapped to operating slices;
- DEV3/UX3 threats and Human UAT are defined;
- runtime implementation remains absent;
- the machine-readable SPEC and vertical roadmap agree;
- dedicated SPEC validation, full CI, Secret Scan and CodeQL pass;
- Review Threads and blockers are zero.

The product Campaign #65 is complete only after implementation proves:

- one real submission/status/result/cancel entrypoint;
- durable restart recovery;
- plan → generation → execution → diagnosis → bounded repair/re-run → verdict;
- direct evidence references;
- two materially different supported projects;
- one seeded product defect detected;
- one healthy scenario not falsely reported;
- critical false green `0`;
- release, deployment/smoke, documentation and Human UAT complete.

## 20. Test and evidence plan

Selected for the SPEC phase:

- Markdown/YAML consistency;
- lifecycle and transition validation;
- vertical-slice dependency validation;
- protected-invariant checks;
- authority and mandate-boundary checks;
- dedicated GitHub Actions gate;
- full repository CI, Secret Scan and CodeQL;
- independent review and Review Threads 0.

Deferred to implementation:

- real CLI/API boundary;
- persistent SQLite restart;
- worker lease and cancellation races;
- real Pytest/Playwright execution;
- generated-test review and mutation proof;
- two-project Beta journey;
- deployment and Human UAT.

Deferral is not a skip of product acceptance; it is the SPEC-first boundary.

## 21. Deployment, rollback and recovery

Planned initial deployment:

- versioned Python package and container image;
- single control-plane service;
- one worker service;
- persistent volume for SQLite and artifacts;
- health/readiness endpoints;
- bounded queue depth and worker concurrency;
- migration command with backup and rollback;
- smoke job against a pinned synthetic project.

Rollback:

- stop new submissions;
- drain or cancel active jobs;
- preserve immutable evidence;
- restore the last compatible schema backup;
- deploy the prior package/image;
- mark affected jobs `REQUIRES_REPLAY`;
- run the smoke journey before reopening intake.

No destructive migration is authorized by this SPEC.

## 22. Human UAT

UX3 Human UAT must verify:

- the CLI journey is understandable;
- progress and failure states are truthful;
- cancellation behaves predictably;
- a user can locate the generated patch and evidence;
- verdict language distinguishes product, test, environment and uncertainty;
- restart recovery does not appear to lose or duplicate work;
- documentation lets a new user run the Beta without project-author assistance.

Synthetic User evidence supplements but does not replace Human UAT.

## 23. Unresolved implementation decisions

The following remain implementation-SPEC decisions:

- exact authentication profile for non-public repositories;
- final package/container hosting environment;
- PostgreSQL/object-store profile after the single-node Beta;
- concrete model providers and routing;
- private network access;
- UI client;
- mobile, device and mini-program adapters;
- multi-tenant isolation and quotas.

None blocks the single-node, CLI-first operating Beta.

## 24. Implementation gate

Runtime implementation may begin only after this SPEC is approved and merged.

The first implementation Goal must deliver Slice A as a real operating path. It must not begin by building another unused horizontal subsystem.
