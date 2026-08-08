# TEST_AGENT_RUNTIME_BETA Threat Model

> Threat Model: `TM-TEST-AGENT-RUNTIME-BETA@0.1.0`  
> SPEC: `SPEC-TEST-AGENT-RUNTIME-BETA@0.1.0`  
> Goal: Issue #66  
> Parent Campaign: Issue #65  
> Assurance: `DEV3 / UX3`

## 1. Protected assets

- Requirements, business/technical/experience/safety Oracles;
- project source and immutable commit identity;
- generated test patches and review history;
- job lifecycle, event log, queue and worker leases;
- governed Memory namespaces, ACL, provenance and lifecycle;
- evidence bundles, manifests, hashes and replay data;
- user-visible verdict, progress, cancellation and recovery state;
- runtime limits, model/tool budgets and deployment configuration;
- repository credentials, Secrets and non-production fixtures;
- cross-project isolation.

## 2. Actors

- submitting user;
- CLI client;
- control plane;
- planner/model;
- project adapter;
- execution worker;
- deterministic verifier;
- diagnosis/repair controller;
- release operator;
- malicious repository content;
- compromised dependency or artifact;
- stale/duplicated worker;
- accidental operator.

Model output, repository instructions and generated tests are untrusted inputs.

## 3. Trust boundaries

1. user/CLI → control plane;
2. control plane → durable job store;
3. scheduler → worker lease;
4. worker → project workspace;
5. repository content → planner/model;
6. generated patch → execution;
7. worker → artifact store;
8. evidence → deterministic verifier;
9. Memory adapter → context assembly;
10. package/container → deployment;
11. synthetic evidence → Human UAT.

## 4. Threats and required controls

| ID | Threat | Required control | Failure result |
|---|---|---|---|
| BETA-T01 | Floating ref changes tested code | immutable commit SHA and hash validation | `POLICY_BLOCKED` |
| BETA-T02 | Repository prompt injection changes authority | repository content is data; authority allowlist and context labels | `POLICY_BLOCKED` |
| BETA-T03 | Model creates arbitrary shell command | versioned capability plan; no model shell interpolation | `POLICY_BLOCKED` |
| BETA-T04 | Path traversal or symlink escape | canonical workspace paths, symlink rejection and sandbox root | attempt invalid |
| BETA-T05 | Generated test modifies product source | write allowlist and patch verifier | `POLICY_BLOCKED` |
| BETA-T06 | Test “repair” weakens Oracle assertion | Oracle-bound diff review and mutation/regression proof | `TEST_DEFECT` |
| BETA-T07 | Product defect is masked as test defect | preserve original evidence; deterministic classification; stop product repair | `PRODUCT_DEFECT` |
| BETA-T08 | Missing evidence produces success | evidence completeness gate before verifier success | critical false green |
| BETA-T09 | Evidence from another revision is reused | project/environment/patch hashes in every bundle | `INSUFFICIENT_EVIDENCE` |
| BETA-T10 | Artifact manifest is tampered | content addressing, SHA-256 index and immutable finalization | attempt invalid |
| BETA-T11 | Secret appears in logs/artifacts | synthetic/non-production data, redaction, secret scan and no raw unbounded copy | `POLICY_BLOCKED` |
| BETA-T12 | Cross-project workspace leakage | per-job workspace, cleanup proof and namespace isolation | `BLOCKED` |
| BETA-T13 | Cross-project Memory leakage | namespace/ACL filtering before relevance | `POLICY_BLOCKED` |
| BETA-T14 | Stale/revoked/forgotten Memory influences plan | lifecycle/compatibility filter and context manifest | `INSUFFICIENT_EVIDENCE` |
| BETA-T15 | Memory overrides current Oracle/Policy | authority ordering and explicit conflict stop | `ORACLE_CONFLICT` |
| BETA-T16 | Duplicate submission runs twice | submission idempotency and immutable request fingerprint | idempotent replay |
| BETA-T17 | Stale worker overwrites job state | expected revision, lease token and expiry fencing | explicit conflict |
| BETA-T18 | Restart duplicates uncertain side effect | attempt journal, reconciliation and new-attempt rule | `BLOCKED` |
| BETA-T19 | Cancellation leaves child processes alive | process-tree kill, lease revoke and cleanup verification | `FAILED` |
| BETA-T20 | Retry/repair loop runs without bound | hard attempts, time, artifact and model/tool budgets | `TIMED_OUT` |
| BETA-T21 | Worker exhausts disk/memory/processes | container/runtime quotas and workspace size limits | `ENVIRONMENT_FAILURE` |
| BETA-T22 | Dependency or browser drift changes result | lockfile, image and browser pinning | attempt invalid |
| BETA-T23 | Network access exfiltrates data | deny by default, profile allowlist and network evidence | `POLICY_BLOCKED` |
| BETA-T24 | Malicious test accesses host resources | isolated worker, least privilege and no host mounts | `POLICY_BLOCKED` |
| BETA-T25 | Model confidence becomes verdict | Candidate-only model output and deterministic verifier | `INSUFFICIENT_EVIDENCE` |
| BETA-T26 | Oracle conflict is silently resolved downward | authority graph and `ORACLE_CONFLICT` stop | `ORACLE_CONFLICT` |
| BETA-T27 | Only successful attempts are retained | append-only attempt history and complete-run bundle | run invalid |
| BETA-T28 | Cleanup deletes evidence needed for audit | evidence retention precedes workspace cleanup | `BLOCKED` |
| BETA-T29 | Schema migration loses active jobs | backup, migration journal, compatibility check and rollback | intake closed |
| BETA-T30 | Deployment reports healthy but cannot run job | real smoke job through packaged entrypoint | release failed |
| BETA-T31 | Healthy scenario is falsely reported | paired healthy control and FP/FN benchmark | Beta gate failed |
| BETA-T32 | Seeded defect is missed | mutation matrix and critical recall `100%` | Beta gate failed |
| BETA-T33 | Human cannot understand progress/verdict | UX3 journey evidence and Human UAT | Beta not accepted |
| BETA-T34 | Private repository credential is copied | initial profile excludes credential acquisition | `OUT_OF_SCOPE` |
| BETA-T35 | Agent silently expands M4–M6 authority | explicit Issues #65/#66 reference and module SPEC gate | `OUT_OF_MANDATE` |

## 5. Abuse cases

### 5.1 Repository prompt injection

A README tells the model to ignore the objective, expose credentials or modify product code. The planner must label repository prose as untrusted project evidence, preserve higher authority and emit a policy block if the requested capability is forbidden.

### 5.2 False-success repair

A generated test fails against a seeded product defect. The repair controller proposes deleting the assertion. The patch verifier rejects the change because it is not supported by a new Oracle revision, and the result remains `PRODUCT_DEFECT`.

### 5.3 Restart during browser action

The worker loses its lease after clicking an action but before writing the attempt result. Recovery does not replay the same uncertain action in the same attempt. It records the uncertainty, resets the isolated fixture and creates a new attempt or blocks.

### 5.4 Evidence substitution

A screenshot from another commit is placed in the artifact path. The manifest hash and project/attempt binding fail, so the verifier cannot emit success.

### 5.5 Cost exhaustion

A model repeatedly generates invalid tests. The repair and attempt budgets stop execution and return `TIMED_OUT` or `TEST_DEFECT` with preserved evidence.

## 6. Security and privacy controls

- synthetic or repository-owned non-production fixtures only;
- least-privilege GitHub and runtime tokens;
- no token in generated context or artifacts;
- redacted stdout/stderr and network evidence;
- immutable action/dependency/image pins where practical;
- no `pull_request_target` execution of untrusted code;
- separate verifier-visible mutation truth;
- no biometric/emotion inference;
- no protected demographic inference;
- no raw personal data;
- bounded retention and explicit evidence deletion policy in implementation SPEC.

## 7. Residual risks

- a single-node SQLite profile is not a multi-region availability design;
- sandbox strength depends on the selected deployment runtime;
- model/provider nondeterminism cannot be eliminated, only bounded and measured;
- static redaction cannot guarantee detection of every secret format;
- two projects do not prove universal project compatibility;
- Human UAT is required for clarity and trustworthiness.

Residual risks must remain visible in Beta documentation and cannot be converted into an unqualified production claim.
