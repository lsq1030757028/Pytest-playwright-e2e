# Hourly GitHub Relay Agent SPEC

> SPEC ID: `SPEC-HOURLY-GITHUB-RELAY@0.1.0`  
> Status: `CANDIDATE / PILOT_APPROVED`  
> Goal: Issue #49  
> Owner authority: repository owner instruction recorded in Issue #49  
> Assurance: `DEV3 / UX0`  
> Product runtime effect: none  
> Pilot effect: hourly ChatGPT task may perform bounded GitHub development writes  
> Auto-merge: forbidden in the pilot

## 1. Purpose

Define a durable relay control loop in which an hourly ChatGPT scheduled task wakes a temporary AI, restores the current development Campaign from GitHub, advances the authoritative work without losing project context, and leaves consistent progress in both the Chat conversation and GitHub.

The system is not a collection of unrelated micro-tasks. It follows:

```text
long-lived Project
→ long-lived Campaign
→ short-lived Run
```

Each Run has global project and Campaign understanding, but performs only a bounded, semantically complete increment before a natural checkpoint.

## 2. Authority and boundaries

Issue #49 is the durable Owner-approved Goal for this design and pilot. This Goal does not extend `MANDATE-AUTONOMY-M1-M3@1.0.0` to M4 or M5 and does not claim that a durable runtime product has been implemented.

The pilot may:

- read repository rules, status, issues, PRs, branches, commits, reviews and CI;
- update one authoritative PR or Issue execution record;
- modify code, tests or documentation only inside an already authorized Goal, approved SPEC and current authoritative branch;
- create commits and push to an existing authorized branch;
- create a new branch or Draft PR only when the current repository authority explicitly requires it;
- rerun or inspect CI when permitted by available tools.

The pilot must not:

- merge a PR or enable auto-merge;
- write directly to `main`;
- change Oracle, Experience Oracle, Policy, Permission, production invariants or release protection;
- touch production data, personal data, Secrets, real devices or irreversible external resources;
- bypass failed CI, Review, Evidence, Replay, Mutation, Benchmark, Release or Human UAT gates;
- start work outside a recorded Goal and approved SPEC;
- create parallel competing authority for the same Campaign.

## 3. Core principles

### 3.1 GitHub is durable state

Chat history is useful context but is not authoritative. Durable state is reconstructed from:

- `AGENTS.md` and mandatory SSOT files;
- the current Goal, SPEC, mandate or Owner authority;
- the authoritative Issue, PR, branch and head SHA;
- Campaign handoff and decision records;
- CI, Review, Commit, Artifact and release evidence;
- previous Run records.

### 3.2 Cut execution, not context

A Run must not receive only an isolated task sentence. It must restore the whole Campaign first, then choose one continuous work increment.

A valid increment may include diagnosis, implementation, tests, commit, CI observation and handoff. It ends at a natural checkpoint such as:

- a verified semantic capability increment;
- a real CI result that requires a later Run;
- an external blocker;
- a phase or authority transition;
- an approaching lease or execution boundary.

### 3.3 Chat is the reading channel; GitHub is the audit channel

Every Run must generate a final Chinese Chat response. GitHub must independently retain START and FINAL evidence, because conversation delivery and task execution are separate reliability layers.

### 3.4 Fail closed

Unknown authority, concurrent ownership, missing model visibility, failed gates or unavailable tools must be recorded truthfully. They must never be converted into fabricated progress.

## 4. Context model

### 4.1 Project context

Stable repository-wide context:

- product purpose and roadmap;
- architecture and protected invariants;
- GitHub development SSOT;
- user communication SSOT;
- active mandates and Owner approvals;
- safety and release boundaries.

### 4.2 Campaign context

A Campaign spans multiple Runs and represents a coherent Goal or module. Recommended assets after implementation:

```text
.agent/relay/campaigns/<campaign-id>/
├── state.yaml
├── handoff.md
├── decisions.yaml
├── failed-attempts.yaml
├── lease.json
└── runs/
    └── <run-token>.json
```

Campaign state must include:

- Goal and business objective;
- authority references;
- current phase and lifecycle status;
- authoritative Issue, PR, branch and head SHA;
- completed capabilities;
- unresolved findings and blockers;
- decisions and rejected alternatives;
- failed attempts and do-not-repeat conditions;
- next valid actions and completion criteria;
- current Human UAT and release truth.

### 4.3 Run context

A Run is one scheduled execution. It records:

- Run Token;
- schedule, start and end timestamps;
- Chat or Codex surface visibility;
- model and reasoning-mode visibility;
- selected Campaign and authority snapshot;
- lease state;
- actions, files, commits, tests and CI;
- final status and next handoff.

## 5. Hourly schedule

The pilot runs once per hour, beginning at the next whole hour in `Asia/Shanghai`.

The schedule is fixed, not a condition watch. Every invocation must generate a final response, including `NO_ACTION`, `WAITING_CI`, `BUSY`, `BLOCKED` or `OUT_OF_MANDATE`.

## 6. Run lifecycle

```text
WAKE
→ ATTEST_RUNTIME
→ LOCATE_AUTHORITY
→ ACQUIRE_LEASE
→ WRITE_START
→ HYDRATE_CONTEXT
→ SELECT_INCREMENT
→ WORKING / VERIFYING
→ WRITE_FINAL
→ RELEASE_LEASE
→ CHAT_FINAL
```

### 6.1 WAKE and runtime attestation

The Run declares only information actually visible to the runtime:

```text
surface: CHAT | CODEX | UNKNOWN
model: visible model name | UNKNOWN
reasoning_mode: visible mode | UNKNOWN
attestation: SELF_REPORTED
```

The task must not infer the surface from tool availability or infer the model from the prompt.

### 6.2 Authority location

Read `AGENTS.md` and mandatory SSOT files. Resolve the active Campaign using repository truth, not hard-coded PR numbers. A configured preferred PR is only a starting hint.

If repository truth conflicts with the handoff, first repair or report the state mismatch. Do not implement against stale authority.

### 6.3 Lease and concurrency

Before any development write, acquire a Campaign lease using GitHub compare-and-swap semantics.

Recommended lease fields:

```yaml
token: relay-<campaign>-<sequence>-<started-at-utc>
status: ACTIVE
owner_surface: CHAT | CODEX | UNKNOWN
started_at: RFC3339
heartbeat_at: RFC3339
expires_at: RFC3339
target_issue: integer | null
target_pr: integer | null
branch: string | null
head_sha: string | null
```

Pilot rules:

- lease duration: 55 minutes;
- heartbeat after each meaningful write or CI transition;
- another Run with an unexpired lease exits as `BUSY` and performs no development write;
- a stale lease may be replaced only after verifying the previous branch, PR and Run record;
- lease acquisition failure is a safe stop, not a retry storm.

Until repository lease files are implemented, the Pilot must use the unique GitHub START marker as a best-effort lock and stop when another active hourly Run is visible.

### 6.4 Run Token

A Run Token must be unique and durable:

```text
relay-<campaign-id>-<monotonic-sequence>-<UTC-start-time>
```

Every commit created by the Run contains:

```text
[RELAY:<run-token>]
```

Every GitHub execution comment contains:

```html
<!-- scheduled-relay:<run-token> -->
```

### 6.5 Three-stage GitHub record

Use one top-level comment on the authoritative PR, or the authoritative Issue when no PR exists.

#### START

Write immediately after minimum authority resolution and before code or test mutation.

Required fields:

- `STARTED`;
- Run Token;
- scheduled and visible start time;
- Chat/Codex/UNKNOWN;
- model and reasoning mode or UNKNOWN;
- Campaign, Issue, PR, branch and head;
- lease result;
- intended semantic increment.

#### WORKING

Update the same comment after meaningful changes:

- action and rationale;
- modified files;
- test command and result;
- commit SHA;
- branch and PR;
- CI run ID and status;
- heartbeat timestamp.

Do not create a new progress comment for the same Run.

#### FINAL

Update the same comment before ending. Allowed statuses:

```text
SUCCESS
WAITING_CI
NO_ACTION
BUSY
BLOCKED
FAILED
REPLAN_REQUIRED
MODEL_UNVERIFIED
OUT_OF_MANDATE
```

Required fields:

- visible end time;
- final runtime attestation;
- actual actions and files;
- commits and CI;
- blocker or failure with the actual tool/system error;
- next valid action;
- lease release or expiry truth.

If START cannot be written, perform no further GitHub write and report the actual error in Chat.

## 7. Campaign hydration and drift control

Every Run reads:

1. Project rules and status;
2. current Campaign state and handoff;
3. authoritative Issue, PR and branch;
4. recent Run records;
5. current CI and Review evidence.

The Run must preserve decision reasons, not only outcomes. Handoff must contain:

- current objective;
- completed and verified facts;
- unresolved items;
- decisions and rejected alternatives;
- failed attempts and retry preconditions;
- do-not-do rules;
- next valid action and completion standard.

Perform a Reorientation instead of normal implementation when any condition is true:

- five Runs since the last Reorientation;
- Campaign phase changed;
- authoritative PR merged, closed or superseded;
- handoff conflicts with GitHub truth;
- a major architecture or requirement change occurred;
- repeated failed attempts indicate plan drift.

Reorientation rereads the relevant architecture and SPEC, validates the Campaign summary and rewrites the handoff without inventing new authority.

## 8. Increment selection

The Run has full Campaign context but chooses one bounded semantic increment.

Priority order:

```text
safety or authority conflict
→ real CI failure
→ blocking Review finding
→ missing approved behavior
→ missing trustworthy test/evidence
→ closure and release verification
→ next approved SPEC step
```

Do not create code churn to make an infrastructure failure look active. When CI fails before repository code executes, record `BLOCKED` or `WAITING_CI` and stop unless there is independent evidence of a repository defect.

## 9. Mandatory Chat final response

Every invocation must produce one user-visible Chinese final response. Silence is forbidden.

The first line must be:

```text
Run Token：<token>；状态：<status>
```

The response must include:

1. business progress and current lifecycle state;
2. actual work performed;
3. modified files and Commit SHA, or explicit `无`;
4. authoritative Issue/PR/branch and CI status;
5. blocker or actual tool/system error;
6. next valid action;
7. GitHub execution record location and comment ID when available;
8. runtime surface, model and reasoning mode, with UNKNOWN when unavailable.

The Chat response and GitHub FINAL record must agree. The task must still generate the Chat response even when it cannot verify client notification delivery.

## 10. Idempotency and recovery

- Search for the Run marker before creating a comment;
- update the existing comment when the marker exists;
- never create two Run records with the same Token;
- verify branch head before committing;
- do not force-update branches;
- on partial failure, preserve created Commit/PR evidence and record the incomplete state;
- on task disablement, no later GitHub write is permitted;
- rollback is disabling the scheduled task and reverting or closing Pilot-only governance assets.

## 11. Pilot target and behavior

Initial Pilot behavior:

- inspect the current authoritative repository Campaign, currently expected near Issue #43 and PR #45 but never hard-code authority without verification;
- continue only approved existing work;
- no automatic merge;
- no production or release-setting changes;
- one run per hour;
- Chat response every Run;
- GitHub START and FINAL every Run when GitHub writes are available.

## 12. Acceptance and promotion

The Pilot is accepted only after at least three consecutive hourly Runs satisfy:

- unique Run Tokens;
- START and FINAL records on the correct authority;
- no duplicate comments;
- a final Chat response generated each Run;
- no overlapping development ownership;
- all commits trace to Run Tokens;
- new AI restores the Campaign without depending on prior Chat history;
- failed gates are not bypassed;
- Chat/Codex, model and reasoning fields are truthful or UNKNOWN;
- disabling the task stops future writes.

Promotion beyond Pilot requires a separate approved implementation plan for durable lease files, schemas, tests and operational monitoring. This SPEC does not authorize auto-merge or M5 completion claims.
