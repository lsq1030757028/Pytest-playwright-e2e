# Hourly GitHub Relay Concurrency Addendum

> Addendum ID: `ADDENDUM-HOURLY-GITHUB-RELAY-CONCURRENCY@0.1.1`  
> Parent SPEC: `SPEC-HOURLY-GITHUB-RELAY@0.1.0`  
> Goal: Issue #49  
> Status: `CANDIDATE / PILOT_APPROVED`

## 1. Why an external lock is required

A Chat or Codex Run cannot directly observe another AI process. It can know that another Run is active only through shared durable state. PR comments alone are useful evidence but are not an atomic lock.

The Pilot therefore uses a dedicated GitHub control branch and a compare-and-swap lease file. GitHub becomes the shared coordination plane for Chat, Codex and future relay-compatible Agents.

## 2. Control branch

```text
branch: ops/hourly-github-relay-control
lease file: .agent/relay/leases/hourly-github-relay.json
```

The control branch is operational state and is never merged into `main`. Product and SPEC branches must not store mutable lease state.

## 3. Atomic acquisition

Before any development write, a Run must:

1. resolve the current Campaign and target authority;
2. fetch the lease file from the control branch and retain the returned blob SHA;
3. evaluate the current lease;
4. if the lease is `ACTIVE` and not expired, exit as `BUSY` without touching the Campaign branch;
5. otherwise replace the lease file using the exact fetched blob SHA;
6. treat a GitHub conflict or stale-SHA failure as another Run winning the lease, then exit as `BUSY`;
7. only after successful lease Commit may the Run write its START comment or modify development assets.

Two Runs reading the same old lease may both try to acquire it, but only the first update with that blob SHA can succeed. The loser must not retry aggressively or use another locking mechanism.

## 4. Lease duration and heartbeat

Hourly cadence does not mean a Run must finish within one hour. To prevent the next hourly trigger from overlapping a long Run:

- lease duration: 90 minutes;
- heartbeat: after every meaningful state transition and at least once before a long CI wait;
- heartbeat updates use the current lease blob SHA;
- every heartbeat extends `expires_at` to 90 minutes after the heartbeat;
- the next hourly Run reads the active lease and returns `BUSY`;
- a normal Run releases the lease in FINAL by setting it to `IDLE` and preserving the last Run summary.

The 90-minute lease deliberately exceeds the one-hour schedule. A new hourly invocation may run while the prior invocation is still active, but it becomes a harmless observer and exits without development writes.

## 5. Stale recovery

An expired lease is not automatically safe to steal. Before takeover, the new Run must verify:

- the previous Run Token and GitHub record;
- the previous target PR, branch and head SHA;
- whether the previous Run comment or branch changed after the recorded heartbeat;
- whether CI is still running for a Commit created by the previous Run.

If recent activity exists, extend or respect the previous lease and exit `BUSY`. If the previous Run is clearly abandoned, acquire a new lease and record `STALE_LEASE_RECOVERED` in START.

No force push, branch reset or deletion is allowed during stale recovery.

## 6. Manual Chat and Codex work

Any Chat or Codex session that opts into the Relay protocol must use the same lease before modifying the active Campaign. Surface and model identity do not grant priority.

Owner-directed emergency or interactive work may supersede the Pilot only through an explicit GitHub state change or user instruction. The scheduled Run must then stop as `BUSY`, `BLOCKED` or `REPLAN_REQUIRED` rather than competing.

## 7. Why not separate hourly stage tasks in the Pilot

Using independent Planner, Developer, Tester and Reviewer schedules would multiply context hydration and race conditions. The Pilot therefore uses one hourly orchestrator that reads the Campaign phase and performs the next valid semantic increment.

Later specialist tasks are allowed only after the single-loop Pilot passes its acceptance criteria. Every specialist must:

- share the same Campaign lease;
- have an explicit allowed input state and output state;
- never overlap writes on the same branch;
- hand off through GitHub state, not private conversation context;
- exit `BUSY` when the lease belongs to another role.

A future staged pipeline may use states such as:

```text
ORIENTING
→ PLAN_READY
→ IMPLEMENTING
→ WAITING_CI
→ REVIEWING
→ CLOSING
```

but stage specialization is an optimization, not the correctness foundation.

## 8. BUSY behavior

A BUSY Run must:

- perform no development write;
- not rerun CI owned by the active Run;
- not create a competing PR or branch;
- generate the mandatory Chat final response;
- optionally record a lightweight BUSY Run on Goal #49, without modifying the active Campaign PR;
- report the active Run Token, lease expiry and last heartbeat when visible.

## 9. Fencing checks before every mutation

Atomic acquisition prevents two new Runs from holding the same lease, but it does not automatically stop an old delayed Run after expiry or takeover. Therefore the lease Run Token is also a fencing token.

Immediately before every mutating GitHub action, the Run must reread the current lease and verify:

```text
status == ACTIVE
run_token == current Run Token
current time < expires_at
target branch == recorded target branch
```

Mutating actions include:

- source, test, documentation or Campaign-state writes;
- Commit creation or branch-ref movement;
- PR metadata or execution-comment updates;
- CI reruns;
- lease heartbeat and release.

If the token, state or expiry no longer matches, the Run has lost ownership. It must stop further mutation and finish as `BUSY`, `REPLAN_REQUIRED` or `BLOCKED`, with `LOST_LEASE` recorded as the cause.

An old Run must never continue merely because it remembers acquiring the lease earlier.

## 10. Branch-head compare-and-swap

The lease coordinates Relay Agents, but a human or another authorized non-Relay actor may still change the Campaign branch.

Before every development Commit, the Run must verify that the actual branch head equals the lease field `target_head_sha`.

- After a successful self-created Commit, update `target_head_sha` in the lease before the next mutation.
- Unexpected head movement causes `REPLAN_REQUIRED`.
- Do not force-push, reset, overwrite, or silently replay a stale patch.

This protects both Agent-Agent concurrency and Agent-human concurrency.

## 11. Sequence and Run Token

The lease record owns a monotonic `sequence` field. Acquisition increments it atomically in the same compare-and-swap update that changes the lease to `ACTIVE`.

The Run Token is then derived from the acquired sequence:

```text
relay-<campaign-id>-<sequence>-<UTC-start-time>
```

A Run must not invent a sequence before successful acquisition. This prevents two contenders from publishing the same logical Run identity.

## 12. BUSY audit exception

A contender that never acquires the lease does not write START or FINAL to the active Campaign PR, because that would create a second apparent owner.

Its mandatory evidence is:

- a Chinese Chat final response with status `BUSY`;
- the observed active Run Token, target, heartbeat and expiry;
- no development, CI or Campaign-comment write.

A lightweight contention record on Goal #49 is optional and must never modify the active Run's record.

## 13. Finalization and release attestation

A Run cannot truthfully record a successful Lease release in FINAL before the release CAS occurs, but after release it no longer holds an ACTIVE fencing token. The Pilot therefore uses a bounded two-phase finalization protocol:

```text
PRE_FINAL while ACTIVE
→ RELEASE CAS to IDLE
→ RELEASE_ATTESTED FINAL update
→ CHAT_FINAL
```

### 13.1 PRE_FINAL

While the Lease is still ACTIVE and all normal fencing checks pass, update the existing Run comment with:

- final business and lifecycle outcome;
- actions, files, Commits, tests and CI;
- blocker or error and next valid action;
- `lease_release: PENDING`;
- the exact intended release summary.

PRE_FINAL is not the final audit claim and must not say that release succeeded.

### 13.2 RELEASE

Release the Lease using the latest Lease blob SHA. The release record must set operational status to `IDLE`, clear active ownership fields, and preserve:

- `last_run_token` equal to the current Run Token;
- `last_final_status`;
- `last_ended_at`;
- `last_summary`;
- `last_release_error`, null only when the release update succeeded.

The returned control-branch Commit SHA is the authoritative release evidence.

### 13.3 RELEASE_ATTESTED FINAL exception

After the release CAS succeeds, exactly one post-release mutation is allowed: update the already-existing comment identified by the current Run marker and comment ID. This exception is audit-only and does not grant development ownership.

Before that update, reread the Lease and require all of:

```text
operational status == IDLE or a later Run is ACTIVE
last_run_token == current Run Token
sequence >= current Run sequence
last_release_error == null
```

The update may change only the Lease-release fields from `PENDING` to `CONFIRMED`, add the release Commit SHA and record that post-release attestation was used. It must not change the business verdict, actions, files, tests, CI, next action, Campaign state, branch, PR metadata or any other repository resource.

If the Lease reread does not prove the current Run's release, or the one bounded comment update fails, do not retry in a loop. The control Lease remains authoritative; Chat must report `RELEASE_ATTESTATION_INCOMPLETE` and the actual error. Such a Run does not count toward Pilot acceptance.

A later Run may acquire the Lease before this audit-only comment update. That does not invalidate the exception because it touches only the prior Run's uniquely marked comment and cannot mutate the new Run's record or development state.
