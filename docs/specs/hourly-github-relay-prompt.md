# Hourly GitHub Relay Pilot Prompt

This is the scheduled-task entrypoint for `SPEC-HOURLY-GITHUB-RELAY@0.1.0`, its concurrency, contention, termination and Work Item lifecycle addenda, and Goal #49.

```text
Execute one Hourly GitHub Relay Pilot Run for repository lsq1030757028/Pytest-playwright-e2e.

Read AGENTS.md and every mandatory SSOT it names. Then read Goal #49, Design PR #51 and all hourly-relay Markdown/YAML assets in docs/specs/ from PR #51 until they are merged.

The effective Pilot window is eight hourly invocations. It validates the Relay control plane only; it is not the M1–M3 product-development budget. Use Program → Campaign → Work Item → Run. A complex Work Item may span multiple Runs and must resume from its durable checkpoint.

Before selecting work, restore the authoritative Goal, PR, branch, head, CI, Review, Campaign, active Work Item and recent Run evidence. Evaluate terminal conditions before new work. If active, select REORIENT, PLAN, IMPLEMENT, VERIFY, WAIT or CLOSE from repository state, not from clock position. Advance one semantically coherent increment to a durable natural checkpoint. Do not force a Work Item to finish within an hour.

Use the operational control branch ops/hourly-github-relay-control and lease file .agent/relay/leases/hourly-github-relay.json. Acquire with GitHub Contents blob-SHA compare-and-swap before every other mutation. Increment sequence and derive the Run Token in the same acquisition. Revalidate status, holder token, expiry and target branch before every mutation. Verify target branch head before every development Commit. Never force-push, reset or overwrite. A contender that cannot acquire exits BUSY without Campaign, PR-comment, branch or CI writes.

Maintain one authoritative START → WORKING/VERIFYING → FINAL comment containing <!-- scheduled-relay:<run-token> -->. Every created Commit contains [RELAY:<run-token>]. Release the Lease using the latest blob SHA and report release truth.

Never write directly to main, merge or enable auto-merge during the Pilot, bypass a failed Gate, modify production/personal data or Secrets, change Oracle/Policy/Permission, operate devices, or perform irreversible external writes.

Every invocation produces a Chinese final Chat response, including BUSY, NO_ACTION, WAITING_CI, BLOCKED and terminal states. First line: Run Token：<token or UNACQUIRED>；状态：<status>. Include Campaign, Work Item, checkpoint, actual actions, files/Commit or 无, Issue/PR/branch, CI, blocker/error, next action, GitHub record and actual visible Chat/Codex/UNKNOWN, model and reasoning mode. Chat and GitHub FINAL must agree.
```

## Schedule

```ical
BEGIN:VEVENT
DTSTART;TZID=Asia/Shanghai:20260806T020000
RRULE:FREQ=HOURLY;COUNT=8
END:VEVENT
```

Timing mode: `exact_schedule`.

Intended Beijing-time window: `2026-08-06 02:00` through `2026-08-06 09:00`.
