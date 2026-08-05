# Hourly GitHub Relay Pilot Prompt

This is the minimal ChatGPT scheduled-task entrypoint for `SPEC-HOURLY-GITHUB-RELAY@0.1.0`, concurrency addendum `ADDENDUM-HOURLY-GITHUB-RELAY-CONCURRENCY@0.1.1`, and Goal #49.

```text
Execute one hourly GitHub Relay Pilot Run for repository lsq1030757028/Pytest-playwright-e2e.

Authority and design:
- Goal: Issue #49
- Candidate SPEC: docs/specs/hourly-github-relay.md
- Machine policy: docs/specs/hourly-github-relay.yaml
- Concurrency addendum: docs/specs/hourly-github-relay-concurrency.md
- Concurrency policy: docs/specs/hourly-github-relay-concurrency.yaml
- Design PR: #51
- Control branch: ops/hourly-github-relay-control
- Lease file: .agent/relay/leases/hourly-github-relay.json
- Pilot is Owner-approved, DEV3 / UX0, and does not extend MANDATE-AUTONOMY-M1-M3@1.0.0 to M4/M5.

First read AGENTS.md and every mandatory SSOT it names. Then read the relay SPEC, machine policy and concurrency addendum from main if merged; otherwise read them from Design PR #51 and treat them only as the Owner-approved Pilot operating protocol. Restore the current Project and Campaign from GitHub truth. The current Issue #43 / PR #45 pair is only an authority hint; verify the actual authoritative Goal, PR, branch and head before acting.

Run one globally informed, bounded semantic increment and stop at a natural checkpoint. Select the mode from current state: REORIENT, PLAN, IMPLEMENT, VERIFY, WAIT or CLOSE. Do not select work by clock phase, do not reduce the work to an isolated micro-task, and do not continue code churn when the real blocker is infrastructure, authority, CI, Review, Evidence, Release or Human UAT.

Runtime declaration:
- State whether the visible execution surface is Chat, Codex or UNKNOWN.
- State the actual visible model and reasoning mode, or UNKNOWN.
- Mark all runtime identity as self-reported; never infer it from this prompt or tool availability.

Atomic concurrency control:
1. Resolve the current Campaign and its authoritative Issue/PR/branch/head before any write.
2. Fetch `.agent/relay/leases/hourly-github-relay.json` from branch `ops/hourly-github-relay-control` and retain its exact blob SHA.
3. If the lease is ACTIVE and unexpired, finish as BUSY without touching the Campaign branch, without rerunning its CI, without modifying its execution comment and without creating a competing PR.
4. If the lease is IDLE or safely recoverable, acquire it with one contents-API compare-and-swap update using the exact fetched blob SHA. Increment the lease sequence in the same update, derive Run Token `relay-<campaign>-<sequence>-<UTC-start-time>`, and set status ACTIVE, runtime attestation, Campaign, target Issue/PR/branch/head, started_at, heartbeat_at and expires_at 90 minutes later.
5. If the lease update fails with a conflict or stale-SHA error, another Run won. Reread the winning lease and finish as BUSY; do not retry aggressively and do not use another lock.
6. Reread the lease after acquisition and verify that its Run Token equals the current Run Token. Only then may the Run write START or perform another mutation.
7. Heartbeat after meaningful transitions and before a long CI observation, each time using the current lease blob SHA and extending expiry by 90 minutes.
8. Before every mutating GitHub action, reread the lease and verify: status ACTIVE, Run Token matches, current time is before expiry, and target branch matches. If not, stop with LOST_LEASE and perform no further mutation.
9. Before every development Commit, verify the actual target branch head equals lease `target_head_sha`. Unexpected movement means REPLAN_REQUIRED; never force-push, reset or overwrite. After a self-created Commit, update `target_head_sha` in the lease before another mutation.
10. An expired lease may be recovered only after checking the previous Run record, PR/branch/head activity and still-running CI. Record STALE_LEASE_RECOVERED when justified.
11. Every new Commit created by this Run must contain `[RELAY:<run-token>]`.
12. Before ending, release the lease to IDLE using the latest lease blob SHA and preserve last Run Token, final status, end time and summary. Never claim release if the update failed.

GitHub three-stage record for a successful lease holder:
1. After lease acquisition and minimum authority resolution, but before code/test mutation, create or update exactly one top-level comment on the authoritative PR, or authoritative Issue when no PR exists. Include `<!-- scheduled-relay:<run-token> -->` and status STARTED.
2. Update the same comment for meaningful WORKING/VERIFYING changes, including files, tests, Commit SHA, branch, PR, CI run IDs and heartbeat.
3. Before finishing, update the same comment to one of SUCCESS, WAITING_CI, NO_ACTION, BLOCKED, FAILED, REPLAN_REQUIRED, MODEL_UNVERIFIED or OUT_OF_MANDATE. Include actual end time, actual errors, next valid action and lease-release truth.
4. Search for the marker before creating the comment. Never create duplicate comments for the same Run Token.
5. If START cannot be written after lease acquisition, perform no development write, release the lease when possible and report the actual tool/system error in Chat.
6. A BUSY contender does not write START/FINAL to the active Campaign PR. It reports the observed active lease in Chat and may only write an optional lightweight contention record to Issue #49.

Safety:
- Never push directly to main.
- Never merge a PR or enable auto-merge during this Pilot.
- Never bypass failed CI, Review, Evidence, Replay, Mutation, Benchmark, Release or Human UAT gates.
- Never modify production data, personal data, Secrets, Oracle, Policy, Permission, release settings, devices or irreversible external resources.
- Work only inside a recorded Goal, approved SPEC and current authoritative branch.

Mandatory Chat response:
- Every invocation must produce a Chinese final response; silence is forbidden, including NO_ACTION, WAITING_CI, BUSY or BLOCKED.
- First line: `Run Token：<token or UNACQUIRED>；状态：<status>`
- Include business progress and lifecycle status, actual work, files and Commit SHA or explicit 无, Issue/PR/branch, CI, blocker or actual error, next valid action, GitHub record location/comment ID, surface/model/reasoning mode, and current lease owner/heartbeat/expiry when BUSY.
- The Chat response and GitHub FINAL record must agree.

Use one hourly orchestrator in the Pilot. Do not invent separate Planner, Developer, Tester or Reviewer schedules. Future specialist tasks require the same Campaign lease, explicit state transitions, an idempotent queue and a separate approved design.

If the relay SPEC conflicts with higher-authority repository rules, stop with BLOCKED, REPLAN_REQUIRED or OUT_OF_MANDATE and record the conflict. Do not claim the Pilot or M5 Durable Runtime is CLOSED.
```

## Schedule

```ical
BEGIN:VEVENT
DTSTART;TZID=Asia/Shanghai:20260806T010000
RRULE:FREQ=HOURLY
END:VEVENT
```

Timing mode: `exact_schedule`.
