# Hourly GitHub Relay Agent SPEC

> SPEC ID: `SPEC-HOURLY-GITHUB-RELAY@0.1.0`  
> Status: `CANDIDATE / PILOT_APPROVED`  
> Goal: Issue #49  
> Owner authority: repository owner instruction recorded in Issue #49  
> Assurance: `DEV3 / UX0`  
> Product runtime effect: none  
> Pilot effect: a bounded scheduled ChatGPT Run may perform governed GitHub development writes  
> Auto-merge: forbidden in the Pilot

## 1. Effective protocol bundle

This base SPEC is interpreted together with the versioned addenda in the same PR:

- `ADDENDUM-HOURLY-GITHUB-RELAY-CONCURRENCY@0.1.1`;
- `ADDENDUM-HOURLY-GITHUB-RELAY-CONTENTION@0.1.2`;
- `ADDENDUM-HOURLY-GITHUB-RELAY-TERMINATION@0.1.1`;
- `ADDENDUM-HOURLY-GITHUB-RELAY-WORK-ITEM-LIFECYCLE@0.1.0`;
- `ADDENDUM-HOURLY-GITHUB-RELAY-CONVERSATION-ISOLATION@0.1.0`.

When an addendum is more specific or newer than a statement in this base document, the addendum controls. The machine-readable YAML files must express the same effective rules. A contradiction between Markdown, YAML, the scheduled-task entrypoint and the operational Lease is `REPLAN_REQUIRED`; it must not be silently resolved by model preference.

## 2. Purpose and unit model

The Relay lets a temporary scheduled AI restore durable development state from GitHub, advance the current authorized work and leave consistent runtime and GitHub evidence.

The effective unit hierarchy is:

```text
Program
→ Campaign
→ Work Item
→ Run / Checkpoint
```

- **Program**: the currently authorized M1–M3 delivery scope and terminal gates.
- **Campaign**: a coherent Goal or module spanning multiple Runs.
- **Work Item**: a semantic objective with explicit completion criteria; it may span many Runs.
- **Run**: one scheduled execution window that advances the active Work Item to a durable natural checkpoint.

An hourly Run is not a roadmap phase and is not a promise to finish a Work Item in one hour. Execution is cut; context is not.

## 3. Authority and boundaries

Issue #49 is the Owner-approved Goal for the design and Pilot. The Pilot does not extend `MANDATE-AUTONOMY-M1-M3@1.0.0` to M4, M5 or M6 and does not claim a durable runtime product.

The Pilot may:

- read repository rules, status, Goals, SPECs, issues, PRs, branches, commits, reviews, CI and artifacts;
- maintain one authoritative Run record;
- modify code, tests or documentation only inside an already authorized Goal, approved SPEC and current authoritative branch;
- commit and push to an existing authorized branch;
- create a branch or Draft PR only when repository authority requires it;
- inspect or rerun CI when the available tools and current preconditions justify it.

The Pilot must not:

- merge a PR or enable auto-merge;
- write directly to `main`;
- change Oracle, Experience Oracle, Policy, Permission, production invariants or release protection;
- touch production or personal data, Secrets, real devices or irreversible external resources;
- bypass failed CI, Review, Evidence, Replay, Mutation, Benchmark, Release or Human UAT gates;
- invent work outside a recorded Goal and approved SPEC;
- create parallel competing authority for one Campaign.

## 4. Durable context

GitHub is the durable state and audit plane. Chat history is not authoritative state and is not a supported handoff channel.

Every Run restores:

1. `AGENTS.md` and all mandatory SSOT files;
2. current roadmap, status, mandate and safety boundaries;
3. the authoritative Goal, SPEC, Issue, PR, branch and head SHA;
4. the active Campaign and Work Item checkpoint;
5. decisions, rejected alternatives, failed attempts and retry preconditions;
6. recent Run records, CI, Review, Artifact and release evidence;
7. current Human UAT and closure truth.

Recommended Campaign assets after a separately approved implementation include:

```text
.agent/relay/campaigns/<campaign-id>/
├── state.yaml
├── handoff.md
├── decisions.yaml
├── failed-attempts.yaml
└── runs/
    └── <run-token>.json
```

A Work Item handoff preserves objective, status, completion criteria, current checkpoint, completed evidence, unresolved questions, candidate and rejected options, next valid action and Run history.

The Human Control Session and Relay Runtime Session exchange durable context only through GitHub. A missing Goal, decision or checkpoint must be externalized before a scheduled Run mutates the repository.

## 5. Pilot schedule and termination

The current Pilot has eight intended hourly invocations from `2026-08-06 02:00` through `09:00` in `Asia/Shanghai`. This cap validates the control plane only; it is not the M1–M3 product budget and is not tied to roadmap-step count.

Before selecting work, evaluate:

```text
OWNER_STOP_OR_REVOCATION
→ PILOT_ABORTED
→ PILOT_ACCEPTED
→ PROGRAM_COMPLETE
→ ACTIVE_WORK_ITEM_OR_CAMPAIGN
→ BLOCKED / WAITING / NO_ACTION
```

Three consecutive lease-acquiring Runs must satisfy all acceptance criteria before `PILOT_ACCEPTED_STOP_REQUESTED`. Later Pilot invocations then perform no Campaign, CI, branch or PR mutation.

Program completion requires truthful closure of M1, M2, M3, the Global Safety Gate, `TEST_AGENT_RUNTIME_BETA`, all required Goals/PRs/main-release evidence/ledgers/cleanup and required Human UAT. M4–M6 never start automatically.

## 6. Run lifecycle

The effective lifecycle is:

```text
WAKE
→ ATTEST_RUNTIME
→ LOCATE_AUTHORITY
→ EVALUATE_TERMINATION
→ ACQUIRE_LEASE
→ VERIFY_HOLDER
→ WRITE_START
→ HYDRATE_CONTEXT
→ SELECT_INCREMENT
→ WORKING / VERIFYING
→ PRE_FINAL
→ RELEASE_CAS
→ RELEASE_ATTESTED_FINAL
→ CHAT_FINAL
```

Runtime identity is self-reported only from actually visible information:

```text
surface: CHAT | CODEX | UNKNOWN
model: visible name | UNKNOWN
reasoning_mode: visible mode | UNKNOWN
attestation: SELF_REPORTED
```

Do not infer identity from the prompt or tool availability.

## 7. Atomic Lease and fencing

Operational state is stored only on:

```text
branch: ops/hourly-github-relay-control
path: .agent/relay/leases/hourly-github-relay.json
```

Before every other mutation, acquire the Lease through GitHub Contents blob-SHA compare-and-swap. Acquisition atomically increments the monotonic sequence and establishes:

```text
relay-<campaign-id>-<sequence>-<UTC-start-time>
```

Effective Lease duration is **90 minutes**. Heartbeats occur after meaningful transitions and before long CI observation, extending expiry by 90 minutes.

Before every mutation, reread the Lease and require:

```text
status == ACTIVE
run_token == current Run Token
current time < expires_at
target_branch == current authoritative branch
```

Before every development Commit, also require actual branch Head to equal Lease `target_head_sha`. After a self-created Commit, update the Lease Head through CAS before another mutation. Unexpected movement is `REPLAN_REQUIRED`; force push, reset and overwrite are forbidden.

An old or delayed Run stops immediately with `LOST_LEASE` when fencing no longer matches.

## 8. Contention truth

`BUSY` is a no-write control decision, not proof that another AI is alive.

A foreign unexpired Lease is `ACTIVE_CONFIRMED` only when there is activity within 15 minutes through a heartbeat, holder Run-comment update, token-attributable branch/PR update or queued/running CI for the holder Commit. Otherwise use `LEASE_HELD_UNCONFIRMED` and state that live activity is not confirmed.

After an acquisition conflict, reread once. If the Lease is already `IDLE`, retry acquisition exactly once with the new blob SHA. Never loop.

Malformed Lease state such as ACTIVE without token, invalid expiry, Campaign/branch mismatch or expiry before heartbeat is `LEASE_STATE_INVALID`, not normal concurrency.

## 9. Increment selection and stagnation

Select the next bounded semantic increment in this priority order:

```text
safety or authority conflict
→ real CI failure
→ blocking Review finding
→ missing approved behavior
→ missing trustworthy test or evidence
→ closure and release verification
→ next approved SPEC step
```

Do not create code churn when failure occurs before repository code executes. External waiting is not implementation failure.

A lease-holding Run should reserve time for verification, FINAL, handoff and release. Up to roughly 45 minutes may be used for active work, but the earliest safe natural checkpoint controls when runtime time remaining is not visible.

Three consecutive lease-holding Runs without new evidence, decision, checkpoint or blocker change trigger `REORIENT`. Six trigger `REPLAN_REQUIRED`. Repeating the same failed action without a changed precondition is forbidden.

## 10. GitHub Run record

Use exactly one top-level comment on the authoritative PR, or authoritative Issue when no PR exists. The marker is:

```html
<!-- scheduled-relay:<run-token> -->
```

### START

After Lease acquisition and holder verification, before code/test/CI mutation, record Run Token, visible start time, runtime attestation, Campaign, Work Item, Issue/PR/branch/head, Lease result and intended increment.

### WORKING / VERIFYING

Update the same comment after meaningful progress with actions, rationale, files, tests, Commits, CI, checkpoint and heartbeat. Never create a second comment for the same Run Token.

### PRE_FINAL

While ACTIVE and normally fenced, record the final business verdict, lifecycle status, actual actions/files/Commits/tests/CI, blocker or error, next valid action and:

```text
lease_release: PENDING
```

PRE_FINAL must not claim release success.

### RELEASE_ATTESTED FINAL

Release the Lease to IDLE using the latest blob SHA, preserving the current Run as `last_run_token`, final status, end time and summary. The returned control Commit is authoritative release evidence.

Exactly one audit-only post-release update may then change only `PENDING` to `CONFIRMED`, add the release Commit SHA and record use of post-release attestation. It grants no development ownership. If attestation cannot be proven or updated, report `RELEASE_ATTESTATION_INCOMPLETE`; the Run does not count toward Pilot acceptance.

## 11. Commit attribution and idempotency

Every development Commit created by a Run contains:

```text
[RELAY:<run-token>]
```

Search for the Run marker before creating a comment. Never duplicate a Run record or Run Token. Preserve partial Commit/PR evidence after failure. Never force-update a branch.

## 12. Runtime receipt

Every invocation returns a Chinese receipt, including `BUSY`, `NO_ACTION`, `WAITING_CI`, `BLOCKED` and terminal states.

First line:

```text
Run Token：<token or UNACQUIRED>；状态：<status>
```

For an isolated Relay Runtime Session, the normal second line is:

```text
GitHub：<authoritative PR or Issue>；Checkpoint：<short checkpoint>；下一动作：<short next action>
```

The complete actions, files, Commits, tests, CI, blocker, audit and Lease truth live in the authoritative GitHub Run record. The runtime receipt normally remains under 500 Chinese characters and must not duplicate the full audit. When a GitHub write or receipt-critical platform action fails, include the actual platform error required for recovery.

A human collaboration conversation must not receive scheduled Relay replies. If it does, fail closed as `SESSION_ISOLATION_FAILED` and disable the scheduled task.

## 13. Pilot acceptance and promotion

The Pilot is accepted only after three consecutive successful lease-acquiring Runs have:

- unique monotonic Run Tokens;
- CAS acquisition, fencing, heartbeat and release success;
- correct START and release-attested FINAL with no duplicate comments;
- generated runtime receipts;
- no overlapping ownership;
- all created Commits traceable to Run Tokens;
- Campaign restoration without private prior-chat dependency;
- no failed gate bypass;
- truthful runtime fields or `UNKNOWN`;
- no unresolved Lease, lost-ownership or audit inconsistency.

Promotion beyond the Pilot requires separate Owner authority and an approved implementation plan for durable Campaign/Work-Item state, schemas, tests and operational monitoring. This SPEC does not authorize auto-merge or an M5 completion claim.

## 14. Conversation isolation and production migration

The Relay uses two separate ChatGPT conversations:

```text
HUMAN_CONTROL
  interactive design, decisions, change requests and direct work

RELAY_RUNTIME
  scheduled execution only and bounded receipts
```

They share GitHub SSOT and the same Lease, but they never share a conversation as the scheduled-task target.

A production task is enable-eligible only when:

- it was created from a dedicated Relay Runtime conversation;
- the human collaboration conversation receives no scheduled reply;
- the prompt declares `session_class: RELAY_RUNTIME` and `durable_context: GITHUB_ONLY`;
- one read-only binding probe proves the receipt location and GitHub record;
- unknown or ambiguous binding fails closed.

The previously created production task associated with the human collaboration conversation remains disabled. The available task tool does not expose a target-conversation migration field, so a new isolated task requires one Owner UI action in the dedicated Relay Runtime conversation. This is an operational binding action, not approval to bypass GitHub Gates.

The full normative rules, migration sequence, failure modes, prompt budget and acceptance criteria are defined by `ADDENDUM-HOURLY-GITHUB-RELAY-CONVERSATION-ISOLATION@0.1.0`.
