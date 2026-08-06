# Hourly GitHub Relay Conversation Isolation Addendum

> Addendum ID: `ADDENDUM-HOURLY-GITHUB-RELAY-CONVERSATION-ISOLATION@0.1.0`  
> Parent SPEC: `SPEC-HOURLY-GITHUB-RELAY@0.1.0`  
> Goal: Issue #49  
> Status: `CANDIDATE / OWNER_REQUESTED`  
> Assurance: `DEV3 / UX0`

## 1. Problem

The Relay currently protects GitHub writes with a CAS Lease, but a scheduled task and an interactive human-design conversation can still share one ChatGPT conversation. That creates a second, independent contention surface:

- each scheduled invocation may append a long prompt and a long result to the human collaboration thread;
- long scheduled records may displace or compress recent design discussion from the effective model context;
- a new scheduled Run may hydrate from a conversation snapshot that does not match the human's current reasoning;
- human design discussion may accidentally become an undeclared runtime dependency;
- GitHub can remain concurrency-safe while the conversation still becomes operationally unusable.

Conversation history is therefore not a durable state store and must not be a shared execution bus.

## 2. Architecture

The effective architecture has three planes:

```text
Human Control Session
  architecture, decisions, change requests, interactive work
                 |
                 v
GitHub Truth Plane
  Goal, Change Event, SPEC, Work Item, checkpoint, evidence, Run record, Lease
                 ^
                 |
Relay Runtime Session
  scheduled execution only, GitHub hydration, bounded result
```

The Human Control Session and Relay Runtime Session may use the same repository and the same Lease. They must not be the same ChatGPT conversation.

GitHub is the only supported handoff channel between the two sessions.

## 3. Session classes

### 3.1 Human Control Session

Purpose:

- architecture and product discussion;
- Owner decisions and requirement changes;
- interactive design and implementation;
- review of GitHub evidence and Relay behavior.

Rules:

- must not be the conversation associated with an enabled scheduled Relay task;
- may use the Relay Lease for interactive repository writes;
- must externalize durable decisions, designs and checkpoints to GitHub instead of relying on chat recall;
- may contain exploratory reasoning, but only repository artifacts become durable authority.

### 3.2 Relay Runtime Session

Purpose:

- host the scheduled task;
- execute one production Relay Run per invocation;
- emit only a bounded runtime receipt after GitHub FINAL.

Rules:

- the conversation is dedicated to the Relay task and is not used for human design discussion;
- the Run must ignore prior conversational prose as project authority;
- the fixed task instruction, repository SSOT, Issue #49 authority, PR #51 protocol bundle, Lease, authoritative Goal/PR/branch/CI and durable Work Item state are the only runtime inputs;
- the session may accumulate short receipts, but full progress, evidence and handoff remain on GitHub;
- if the platform cannot prove that the task is bound to a dedicated Relay Runtime Session, the task remains disabled.

## 4. Binding and migration gate

A scheduled task is considered isolated only when all of the following are true:

1. it was created from a dedicated Relay Runtime Session;
2. that session is not used for normal collaboration;
3. the Human Control Session does not receive its scheduled replies;
4. the task prompt declares `session_class: RELAY_RUNTIME` and `durable_context: GITHUB_ONLY`;
5. the task is disabled whenever session binding is unknown or ambiguous.

An existing task must not be assumed to be retargetable. When the platform does not expose a supported conversation-retarget operation, migration is:

```text
DISABLE_OLD_TASK
→ CREATE_DEDICATED_RELAY_RUNTIME_SESSION
→ CREATE_NEW_TASK_FROM_THAT_SESSION
→ RUN_ONE_READ_ONLY_BINDING_PROBE
→ VERIFY_GITHUB_RECORD_AND_RUNTIME_RECEIPT_LOCATION
→ ENABLE_PRODUCTION_WRITES
```

The old task remains disabled after migration and is retained only as historical configuration evidence.

## 5. Durable context ownership

Chat history owns no authoritative runtime field.

The Relay must restore the following from GitHub on every invocation:

- Program and terminal gates;
- Campaign and active Work Item;
- current checkpoint and completion criteria;
- completed evidence;
- unresolved questions;
- candidate and rejected options;
- failed attempts and retry preconditions;
- next valid action;
- authority, mandate and safety boundaries;
- target Issue, PR, branch and Head SHA;
- Lease state, recent Run record, CI, Review, Release, Ledger and Human UAT truth.

The authoritative Work Item may live in an approved repository state file, an authoritative Issue/PR body, or a uniquely marked Run/handoff record. Private chat memory is never sufficient.

## 6. Output budget

The Relay Runtime Session is a receipt channel, not the detailed audit channel.

After a successful GitHub `RELEASE_ATTESTED FINAL`, the runtime reply should normally contain:

```text
Run Token：<token>；状态：<status>
GitHub：<authoritative PR or Issue>；Checkpoint：<short checkpoint>；下一动作：<short next action>
```

The reply must remain truthful and include a real blocker or error when present, but it should not duplicate the full GitHub Run comment, file list, CI log or design discussion.

A suggested upper bound is 500 Chinese characters unless a GitHub write failed and the actual platform error must be reported in full.

The Human Control Session reads details from GitHub on demand.

## 7. Prompt budget

The scheduled entry prompt must be a stable bootstrap, not a serialized project state dump.

It should contain only:

- repository identity;
- session class and GitHub-only context rule;
- mandatory SSOT and protocol entrypoints;
- Lease/Fencing requirement;
- scope and safety boundaries;
- bounded receipt format.

It must not embed:

- current Work Item prose;
- current branch Head;
- copied CI results;
- long prior Run summaries;
- private design discussion;
- a manually maintained roadmap snapshot.

Those values are rehydrated from GitHub.

## 8. Interactive and scheduled concurrency

Conversation isolation does not replace GitHub concurrency control.

Both sessions use the same control branch and Lease. The Human Control Session has no automatic priority over the Relay Runtime Session. Owner-directed interactive supersession must be explicit and durably recorded before conflicting writes.

A session that does not hold the Lease may continue read-only analysis, prepare a local draft, or report `BUSY`, but it must not mutate GitHub Campaign resources.

## 9. Failure modes

### 9.1 Scheduled reply appears in Human Control Session

Status: `SESSION_ISOLATION_FAILED`.

Actions:

- disable the task;
- perform no further scheduled development writes;
- preserve the GitHub Run record;
- recreate the task from a dedicated Relay Runtime Session before resuming.

### 9.2 Runtime depends on earlier chat discussion

Status: `CONTEXT_NOT_DURABLE`.

Actions:

- stop before mutation;
- externalize the missing Goal, decision, Work Item or checkpoint to GitHub through an authorized interactive Run;
- resume only after GitHub contains sufficient authority and context.

### 9.3 Task/session binding cannot be inspected

Status: `SESSION_BINDING_UNKNOWN`.

Actions:

- fail closed;
- keep scheduled writes disabled;
- allow only a bounded read-only probe in a dedicated session.

### 9.4 GitHub FINAL succeeds but runtime receipt fails

GitHub remains authoritative. Record `CHAT_RECEIPT_FAILED` in the next observable audit update when safely possible. Do not repeat development writes merely to recreate the receipt.

## 10. Migration of the current task

The task previously titled `GitHub 正式接力` was associated with the human collaboration conversation and was paused by Owner instruction on 2026-08-06.

Required migration:

1. keep the old task disabled;
2. merge or otherwise Owner-approve this addendum and the revised bootstrap prompt;
3. create a new dedicated conversation named, for example, `Pytest-playwright-e2e Relay Runtime`;
4. create the hourly task from that conversation using the approved bootstrap prompt;
5. run one read-only binding probe;
6. verify that its reply appears only in the dedicated runtime conversation and that GitHub contains the expected probe record;
7. enable production GitHub writes only after the binding probe passes.

Because the current tool surface does not expose a supported target-conversation parameter for task creation or update, this conversation migration requires one Owner UI action: create/open the dedicated Relay Runtime conversation and create the task there. That action does not waive any GitHub Gate.

## 11. Acceptance criteria

Conversation isolation is accepted only when:

- the human collaboration conversation receives no scheduled Relay result during the probe window;
- the dedicated Relay Runtime Session receives the bounded receipt;
- the Run restores its Work Item without relying on prior chat discussion;
- GitHub contains complete START, checkpoint and FINAL evidence;
- the runtime receipt is bounded and points to the authoritative GitHub record;
- the same GitHub Lease prevents overlapping interactive and scheduled writes;
- disabling the task stops scheduled GitHub writes;
- no M4/M5/M6 or Durable Runtime product claim is made.

## 12. Rollback

Rollback is:

- disable the isolated task;
- retain GitHub audit evidence;
- continue interactive work through the Human Control Session and shared Lease;
- revert this addendum only through a reviewed governance change.

No production data migration, Secret rotation or irreversible external action is required.
