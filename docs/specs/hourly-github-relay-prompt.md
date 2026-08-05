# Hourly GitHub Relay Pilot Prompt

This is the minimal ChatGPT scheduled-task entrypoint for `SPEC-HOURLY-GITHUB-RELAY@0.1.0` and Goal #49.

```text
Execute one hourly GitHub Relay Pilot Run for repository lsq1030757028/Pytest-playwright-e2e.

Authority and design:
- Goal: Issue #49
- Candidate SPEC: docs/specs/hourly-github-relay.md
- Machine policy: docs/specs/hourly-github-relay.yaml
- Design PR: {{DESIGN_PR}}
- Pilot is Owner-approved, DEV3 / UX0, and does not extend MANDATE-AUTONOMY-M1-M3@1.0.0 to M4/M5.

First read AGENTS.md and every mandatory SSOT it names. Then read the relay SPEC and YAML from main if merged; otherwise read them from Design PR {{DESIGN_PR}} and treat them only as the Owner-approved Pilot operating protocol. Restore the current Project and Campaign from GitHub truth. The current Issue #43 / PR #45 pair is only an authority hint; verify the actual authoritative Goal, PR, branch and head before acting.

Run one globally informed, bounded semantic increment and stop at a natural checkpoint. Do not reduce the work to an isolated micro-task and do not continue code churn when the real blocker is infrastructure, authority, CI, Review, Evidence, Release or Human UAT.

Runtime declaration:
- State whether the visible execution surface is Chat, Codex or UNKNOWN.
- State the actual visible model and reasoning mode, or UNKNOWN.
- Mark all runtime identity as self-reported; never infer it from this prompt or tool availability.

Concurrency and identity:
- Generate a unique Run Token in the form relay-<campaign>-<sequence>-<UTC-start-time>.
- Before development writes, detect any active hourly Relay Run on the same Campaign. If one exists, finish as BUSY without development writes.
- Until durable CAS lease files are implemented, use the unique START comment marker as the best-effort lock.
- Every new Commit message created by this Run must contain [RELAY:<run-token>].

GitHub three-stage record:
1. After minimum authority resolution and before code/test mutation, create or update exactly one top-level comment on the authoritative PR, or authoritative Issue when no PR exists. Include <!-- scheduled-relay:<run-token> --> and status STARTED.
2. Update the same comment for meaningful WORKING/VERIFYING changes, including files, tests, Commit SHA, branch, PR, CI run IDs and heartbeat.
3. Before finishing, update the same comment to one of SUCCESS, WAITING_CI, NO_ACTION, BUSY, BLOCKED, FAILED, REPLAN_REQUIRED, MODEL_UNVERIFIED or OUT_OF_MANDATE. Include the actual end time, actual errors, next valid action and lease-release truth.
4. Search for the marker before creating the comment. Never create duplicate comments for the same Run Token.
5. If the START comment cannot be written, perform no further GitHub writes and report the actual tool/system error in Chat.

Safety:
- Never push directly to main.
- Never merge a PR or enable auto-merge during this Pilot.
- Never bypass failed CI, Review, Evidence, Replay, Mutation, Benchmark, Release or Human UAT gates.
- Never modify production data, personal data, Secrets, Oracle, Policy, Permission, release settings, devices or irreversible external resources.
- Work only inside a recorded Goal, approved SPEC and current authoritative branch.

Mandatory Chat response:
- Every invocation must produce a Chinese final response; silence is forbidden, including NO_ACTION, WAITING_CI, BUSY or BLOCKED.
- First line: Run Token：<token>；状态：<status>
- Include business progress and lifecycle status, actual work, files and Commit SHA or explicit 无, Issue/PR/branch, CI, blocker or actual error, next valid action, GitHub record location/comment ID, surface/model/reasoning mode.
- The Chat response and GitHub FINAL record must agree.

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
