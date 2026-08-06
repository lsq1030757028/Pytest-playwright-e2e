# Hourly GitHub Relay Contention Classification Addendum

> Addendum ID: `ADDENDUM-HOURLY-GITHUB-RELAY-CONTENTION@0.1.2`  
> Parent: `ADDENDUM-HOURLY-GITHUB-RELAY-CONCURRENCY@0.1.1`  
> Goal: Issue #49  
> Status: `CANDIDATE / PILOT_APPROVED`

## 1. Purpose

Prevent a Relay Run from claiming that another AI is actively working when GitHub only proves that a lease could not be acquired.

`BUSY` is a control decision, not proof of a live process. The Run must separate:

```text
lock availability
from
activity confirmation
```

## 2. Contention classes

Every non-owner Run records one of:

- `ACTIVE_CONFIRMED`: a foreign unexpired lease exists and recent activity is visible;
- `LEASE_HELD_UNCONFIRMED`: a foreign unexpired lease exists but no recent activity can be confirmed;
- `CAS_LOST_ACTIVE`: acquisition CAS failed and the reread lease is foreign, ACTIVE and unexpired;
- `CAS_LOST_RELEASED`: acquisition CAS failed but the reread lease is IDLE;
- `STALE_REVIEW_REQUIRED`: lease expired, but takeover safety cannot yet be established.

Only `ACTIVE_CONFIRMED` may be described to the user as “another AI is confirmed to be working.” Other classes must use precise wording such as “the lease is currently held” or “activity is not confirmed.”

## 3. Evidence for active confirmation

A foreign lease is `ACTIVE_CONFIRMED` only when at least one of the following is newer than the configured activity window:

- lease heartbeat;
- the holder Run comment update;
- target branch or PR update attributable to the holder Run Token;
- a CI run still queued or running for the holder Run Commit.

Pilot activity window: 15 minutes.

An unexpired lease without that evidence remains `LEASE_HELD_UNCONFIRMED`. It still blocks writes, but the Chat response must not claim that a live AI process is known to exist.

## 4. Bounded conflict reread

When acquisition fails with stale SHA or conflict:

1. reread the lease exactly once;
2. if it is foreign, ACTIVE and unexpired, finish `BUSY` with `CAS_LOST_ACTIVE`;
3. if it is IDLE, retry acquisition exactly once with the new blob SHA;
4. if the bounded retry succeeds, continue as owner;
5. if the bounded retry conflicts again, reread once and finish `BUSY` with the observed class;
6. never loop or create a retry storm.

This prevents a false `BUSY` when another Run released the lease between the contender’s initial read and CAS attempt.

## 5. Inconsistent lease records

Do not classify an inconsistent record as normal concurrency. Examples:

- `ACTIVE` without Run Token;
- missing or unparsable expiry;
- Campaign or target branch mismatch;
- expiry earlier than heartbeat;
- holder token not matching the referenced Run record.

Such states finish as `REPLAN_REQUIRED` or `BLOCKED` with `LEASE_STATE_INVALID`, not as “another AI is working.”

## 6. User-facing BUSY report

A BUSY response must include:

- contention class;
- foreign Run Token when visible;
- heartbeat and expiry;
- activity evidence or explicit `UNCONFIRMED`;
- confirmation that no Campaign, branch, PR comment or CI write was performed.

The wording must match the evidence:

```text
ACTIVE_CONFIRMED: another Relay Run has recent observable activity.
LEASE_HELD_UNCONFIRMED: the lease blocks safe writes, but live activity is not confirmed.
```

## 7. Safety bias

A conservative no-write decision is acceptable when evidence is uncertain. A false statement that another AI is definitely active is not acceptable.

The Pilot optimizes in this order:

1. prevent overlapping writes;
2. report the evidence precisely;
3. minimize unnecessary skipped Runs through one bounded reread/retry;
4. never trade safety for liveness.
