# BETA-A Durable Governed Pack Threat Model

> Threat Model: `TM-BETA-A-DURABLE-GOVERNED-PACK@0.1.0`  
> SPEC: `SPEC-BETA-A-DURABLE-GOVERNED-PACK@0.1.0`  
> Goal: Issue #95  
> Parent Campaign: Issue #65  
> Parent Architecture Goal: Issue #66  
> Assurance: `DEV3 / UX3`

## 1. Scope

This threat model narrows the parent `TEST_AGENT_RUNTIME_BETA` threat model to BETA-A: submit a pinned project and an existing governed Pytest/Playwright pack, execute it as a durable bounded job, collect evidence, produce a deterministic verdict, support truthful cancellation, and reconcile durable truth after a control-process restart.

BETA-A does not generate tests, repair tests, use governed Memory, or claim active execution resume. Those remain later slices.

## 2. Protected assets

- immutable project repository identity and commit SHA;
- governed-pack manifest, exact node IDs and Oracle bindings;
- submission idempotency key and request fingerprint;
- durable job/event/attempt state;
- job revision, worker lease token and Run Token;
- command-started marker and attempt uncertainty state;
- sandbox and product-source read-only boundary;
- bounded/redacted stdout and stderr;
- JUnit and selected Playwright artifacts;
- evidence manifest, artifact hashes and replay data;
- deterministic verifier output and final verdict;
- cancellation request, process-tree termination and cleanup evidence;
- state-directory schema/version and migration/rollback evidence;
- user-visible status, events, result and cancellation truth.

## 3. Actors and trust boundaries

Actors:

- submitting CLI user;
- runtime operator starting the single-node service;
- control plane;
- execution worker;
- project adapter;
- deterministic verifier;
- malicious or broken repository test code;
- stale/duplicated worker;
- interrupted/crashed control process;
- accidental operator;
- compromised dependency or browser runtime.

Trust boundaries:

1. CLI input → durable control plane;
2. control plane → SQLite job store;
3. governed-pack manifest → collection/execution selector;
4. scheduler → worker lease;
5. worker → sandboxed project workspace;
6. untrusted tests → host/runtime boundary;
7. worker → content-addressed artifact store;
8. artifact bundle → deterministic verifier;
9. cancellation request → process-tree controller;
10. persisted state/evidence → restart reconciliation;
11. packaged runtime → release smoke journey.

Repository code, tests, test output, logs and any model text are untrusted inputs. They cannot redefine Oracle, Policy, Permission or final verdict rules.

## 4. Threat catalog

| ID | Threat | Required control | Fail-closed result |
|---|---|---|---|
| BA-T01 | Floating project ref changes tested code | immutable commit SHA + checkout verification | `POLICY_BLOCKED` |
| BA-T02 | Submission idempotency key is rebound to another request | fingerprint every required field; same key/different fingerprint conflicts | explicit conflict |
| BA-T03 | Governed-pack manifest changes after submission | immutable content hash + pack/version binding | `POLICY_BLOCKED` |
| BA-T04 | User injects shell/Pytest flags through pack or CLI | exact node IDs, argv-list launch, no free-form args/interpolation | `POLICY_BLOCKED` |
| BA-T05 | Required node disappears during collection | exact collection manifest and required-node completeness gate | `TEST_DEFECT` or blocked execution |
| BA-T06 | Required node is skipped/xfail/deselected but process exits green | verifier requires every required node executed and passed | `INSUFFICIENT_EVIDENCE` / no success |
| BA-T07 | Exit code alone is used as success | deterministic evidence-completeness verifier | critical false-green gate |
| BA-T08 | JUnit/artifact belongs to another project/pack/environment | bind all revisions/hashes in evidence manifest | `INSUFFICIENT_EVIDENCE` |
| BA-T09 | Artifact is changed after collection | SHA-256 content addressing + immutable manifest verification | `INSUFFICIENT_EVIDENCE` |
| BA-T10 | Artifact manifest references a file not durably written | temp-write + fsync + hash + atomic finalize before manifest publication | `INSUFFICIENT_EVIDENCE` |
| BA-T11 | Malicious test modifies product source | read-only product tree + post-attempt diff verifier | `POLICY_BLOCKED` |
| BA-T12 | Malicious test escapes workspace by path/symlink | canonical root + traversal/symlink escape rejection | `POLICY_BLOCKED` |
| BA-T13 | Malicious test reads host secrets or sockets | isolated worker, no host-secret inheritance, no host control sockets | `POLICY_BLOCKED` |
| BA-T14 | Test exfiltrates data over network | deny-by-default network + profile evidence | `POLICY_BLOCKED` |
| BA-T15 | Stale worker writes after lease loss | lease-token + expected-revision fencing before mutations | explicit conflict |
| BA-T16 | Two workers launch the same BETA-A command | one worker/job + one durable command-start marker + launch fencing | `BLOCKED` |
| BA-T17 | Crash after command launch causes automatic duplicate re-run | durable `command_started` before spawn; uncertain launch never auto-reruns | `BLOCKED` / `ABANDONED_UNCERTAIN` |
| BA-T18 | Crash before command launch permanently loses accepted work | reclaim pre-launch lease only after expiry | safe continuation |
| BA-T19 | Crash after evidence durability but before result durability loses verdict | deterministic reverify from immutable evidence | safe finalization |
| BA-T20 | Cancellation is reported before child processes stop | durable cancel + process-tree kill + cleanup proof before `CANCELLED` | `FAILED`/`BLOCKED` |
| BA-T21 | Worker starts another step after cancellation | cancellation checked before every new execution step | `CANCELLED` path |
| BA-T22 | Partial evidence from cancelled attempt is discarded | preserve partial attempt bundle and terminal cancellation evidence | run invalid if lost |
| BA-T23 | Timeout/retry loop becomes unbounded | one attempt, zero automatic retries, hard wall-clock/artifact limits | `TIMED_OUT` |
| BA-T24 | Only passing attempts/evidence are retained | append-only attempt/event history + full bundle retention | run invalid |
| BA-T25 | Assertion failure is mislabeled test defect to avoid product defect | valid Oracle binding + deterministic failure classification | `PRODUCT_DEFECT` |
| BA-T26 | Collection/import/fixture defect is mislabeled product defect | deterministic structural failure classification | `TEST_DEFECT` |
| BA-T27 | Browser/runtime failure is mislabeled product defect or success | environment failure classifier + required evidence | `ENVIRONMENT_FAILURE` |
| BA-T28 | Missing/conflicting Oracle is silently resolved | explicit authority validation | `ORACLE_CONFLICT` |
| BA-T29 | Model confidence becomes final verdict | model output Candidate-only; verifier exclusive authority | `INSUFFICIENT_EVIDENCE` |
| BA-T30 | State schema upgrade loses active jobs | version check, backup, migration journal, compatibility check, rollback | intake closed |
| BA-T31 | Runtime package looks healthy but entrypoint cannot run a job | package/container smoke through documented CLI | release failed |
| BA-T32 | User confuses `ACCEPTED` or `EXECUTING` with successful verification | UX3 status language and journey evidence | Beta-A UX gate failed |
| BA-T33 | Restart hides uncertain execution and displays success | explicit `ABANDONED_UNCERTAIN`/blocked truth | critical false-green gate |
| BA-T34 | Cancellation hides unresolved cleanup | no terminal `CANCELLED` without cleanup proof | blocked/failure truth |
| BA-T35 | BETA-A silently expands into generation/repair/Memory | slice-scope tests and Program Delivery boundary | `OUT_OF_SCOPE` / replan |
| BA-T36 | BETA-A authority is laundered into standing M1–M3 mandate | #65/#66/#95 explicit authority refs; mandate remains unextended | `OUT_OF_MANDATE` claim rejected |
| BA-T37 | Scheduled Relay is re-enabled because SPEC merged | Relay enablement remains separate and false in this SPEC | Relay stays disabled |

## 5. Critical abuse cases

### 5.1 Green process with incomplete governed pack

The governed pack contains ten required nodes. A plugin deselects two nodes and Pytest exits `0`. The deterministic verifier compares the collection manifest, required-node set and JUnit execution set. It cannot emit `VERIFIED_SUCCESS`.

### 5.2 Idempotency-key request swap

A client submits key `K` for commit `A`, then reuses `K` for commit `B` or a different governed pack. The stored request fingerprint no longer matches. The second request is rejected as an explicit conflict and cannot reuse the original job identity.

### 5.3 Crash after launch, before result

The worker durably records `command_started`, launches Chromium/Pytest, then the control process dies before terminal evidence is committed. On restart the job is not automatically re-executed. The attempt becomes uncertain and the job is blocked/non-success unless immutable complete evidence can independently prove a safely finalizable result.

This is intentionally weaker than BETA-D resume capability and safer than blind retry.

### 5.4 Cancellation with surviving process

The user cancels while a browser child process remains alive after graceful termination. The runtime force-kills the process tree and verifies cleanup. If any child/cleanup uncertainty remains, it must not publish `CANCELLED` as if cancellation were complete.

### 5.5 Malicious existing test

An existing test tries to read a host token, mount socket, write product source, escape via symlink, or reach the network. The worker sandbox blocks the capability. A repository-governed test is trusted for test intent, not trusted as host code.

### 5.6 Evidence substitution

An attacker replaces JUnit or a screenshot with content from another run. The artifact hash or project/pack/environment binding fails. The verifier emits no success verdict.

## 6. Security and privacy controls

- synthetic or repository-owned non-production fixtures only;
- initial profile excludes private-repository credential acquisition;
- no real Secret copied into project context or artifacts;
- isolated worker and least privilege;
- no inherited host Secret environment;
- no host Docker/control socket mount;
- deny-by-default network;
- bounded/redacted logs;
- exact project/pack/environment/evidence revisions;
- SHA-256 content addressing;
- no raw unbounded logs in default CLI output;
- no direct `main` write;
- no product source write;
- no Oracle/Policy/Permission mutation;
- no model-only verdict authority.

## 7. Recovery and rollback threats

Recovery must distinguish:

- durable state recovery;
- safe re-verification from immutable evidence;
- safe reclaim before command start;
- unsafe uncertain execution after command start.

Rollback must not overwrite or reinterpret newer durable evidence. If a binary downgrade cannot understand the stored schema, intake stays closed until a compatible runtime is restored. Evidence remains preserved.

## 8. Residual risks

- the single-node SQLite profile does not claim multi-node/high-availability semantics;
- exact host isolation strength depends on the implementation runtime/container boundary and must be proven in implementation evidence;
- deny-by-default network may require explicitly versioned project exceptions later;
- redaction cannot guarantee detection of every possible secret pattern, so production/personal data remains excluded;
- BETA-A does not resume an uncertain active browser/test execution; it blocks rather than duplicate it;
- one governed pack does not prove cross-project generalization;
- Human UAT remains required before the full Beta is accepted.

These residual risks are product limits, not reasons to relax the protected invariants.