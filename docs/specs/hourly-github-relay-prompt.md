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

Run one globally informed, bounded semantic increment and stop at a natural checkpoint. Do not reduce the work to an isolated micro-task and do not continue code churn when the real blocker is infrastructure, authority, CI, Review, Evidence, Release or Human UAT.

Runtime declaration:
- State whether the visible execution surface is Chat, Codex or UNKNOWN.
- State the actual visible model and reasoning mode, or UNKNOWN.
- Mark all runtime identity as self-reported; never infer it from this prompt or tool availability.

Atomic concurrency control:
1. Generate a unique Run Token in the form relay-<campaign>-<sequence>-<UTC-start-time>.
2. Resolve the current Campaign before any write.
3. Fetch the lease file from branch ops/hourly-github-relay-control and retain its exact blob SHA.
4. If the lease is ACTIVE and unexpired, finish as BUSY without touching the Campaign branch, without rerunning its CI and without creating a competing PR.
5. If the lease is IDLE or safely stale, acquire it by updating the lease file with the exact fetched blob SHA. Set status ACTIVE, Run Token, runtime attestation, Campaign, target Issue/PR/branch/head, started_at, heartbeat_at and expires_at 90 minutes later.
6. If the lease update fails with a conflict or stale-SHA error, another Run won the lease. Finish as BUSY; do not retry aggressively and do not use another lock.
7. Only after a successful lease Commit may this Run write its START record or modify code/tests/CI.
8. Heartbeat through the same lease file after meaningful transitions and before a long CI wait, each time using the current blob SHA and extending expiry by 90 minutes.
9. Before ending, release the lease to IDLE and preserve last Run Token, final status, end time and summary.
10. An expired lease may be recovered only after checking the previous Run comment, PR/branch/head activity and any still-running CI. Record STALE_LEASE_RECOVERED when takeover is justified.
11. Every new Commit message created by this Run must contain [RELAY:<run-token>]. Never force-push.

GitHub three-stage record:
1. After successful lease acquisition and minimum authority resolution, but before code/test mutation, create or update exactly one top-level comment on the authoritative PR, or authoritative Issue when no PR exists. Include <!-- scheduled-relay:<run-token> --> and status STARTED.
2. Update the same comment for meaningful WORKING/VERIFYING changes, including files, tests, Commit SHA, branch, PR, CI run IDs and heartbeat.
3. Before finishing, update the same comment to one of SUCCESS, WAITING_CI, NO_ACTION, BUSY, BLOCKED, FAILED, REPLAN_REQUIRED, MODEL_UNVERIFIED or OUT_OF_MANDATE. Include the actual end time, actual errors, next valid action and lease-release truth.
4. Search for the marker before creating the comment. Never create duplicate comments for the same Run Token.
5. If the START comment cannot be written after lease acquisition, perform no development write, release the lease when possible and report the actual tool/system error in Chat.
6. A BUSY Run may write only a lightweight BUSY audit record on Issue #49; it must not modify the active Campaign PR.

Safety:
- Never push directly to main.
- Never merge a PR or enable auto-merge during this Pilot.
- Never bypass failed CI, Review, Evidence, Replay, Mutation, Benchmark, Release or Human UAT gates.
- Never modify production data, personal data, Secrets, Oracle, Policy, Permission, release settings, devices or irreversible external resources.
- Work only inside a recorded Goal, approved SPEC and current authoritative branch.

Mandatory Chat response:
- Every invocation must produce a Chinese final response; silence is forbidden, including NO_ACTION, WAITING_CI, BUSY or BLOCKED.
- First line: Run Token：<token>；状态：<status>
- Include business progress and lifecycle status, actual work, files and Commit SHA or explicit 无, Issue/PR/branch, CI, blocker or actual error, next valid action, GitHub record location/comment ID, surface/model/reasoning mode, and current lease owner/expiry when BUSY.
- The Chat response and GitHub FINAL record must agree.

Use one hourly orchestrator in the Pilot. Do not invent separate Planner, Developer, Tester or Reviewer schedules. Future specialist tasks require the same Campaign lease, explicit state transitions and a separate approved design.

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
