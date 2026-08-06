# Hourly GitHub Relay Runtime Bootstrap Prompt

This is the minimal scheduled-task entrypoint for Goal #49 and the effective PR #51 protocol bundle.

The task must be created from a dedicated conversation whose only purpose is the Relay Runtime. Do not create or enable it from the human architecture/design conversation.

## Approved bootstrap

```text
Execute one Production Hourly GitHub Relay Run for repository `lsq1030757028/Pytest-playwright-e2e`.

Runtime declaration:
- session_class: RELAY_RUNTIME
- durable_context: GITHUB_ONLY
- conversation_history_authoritative: false

Do not treat prior Chat messages as project state, authority, checkpoint or evidence. Restore everything from GitHub.

Read `main:AGENTS.md` and every SSOT it requires. Read Issue #49, including `OWNER-AUTH-PRODUCTION-RELAY-M1-M3@1.0.0`. Until PR #51 is merged, read the complete Relay protocol bundle from PR #51 Head, including the conversation-isolation Markdown/YAML addendum and this bootstrap prompt.

Restore the current `Program → Campaign → Work Item → Run / Checkpoint` from authoritative GitHub Goals, SPECs, Issues, PRs, branches, CI, Reviews, Run records and Lease state. Preserve the same Work Item across Runs. Never reconstruct project state from private conversation memory.

Before every GitHub mutation, acquire and verify the CAS Lease on branch `ops/hourly-github-relay-control`, path `.agent/relay/leases/hourly-github-relay.json`. Apply holder-token, expiry, target-branch and branch-Head fencing exactly as specified. A non-holder performs no development, PR-comment or CI mutation.

Operate only within `MANDATE-AUTONOMY-M1-M3@1.0.0`. Do not enter M4/M5/M6, directly push `main`, bypass a failed Gate, modify production/personal data or Secrets, change Oracle/Experience Oracle/Policy/Permission, or perform irreversible or unbounded external actions.

Write the complete START → WORKING/VERIFYING → PRE_FINAL → RELEASE_ATTESTED FINAL audit to the authoritative GitHub PR or Issue. Every development Commit contains `[RELAY:<run-token>]`.

After GitHub FINAL, reply only with a bounded receipt, normally no more than 500 Chinese characters:

Run Token：<token or UNACQUIRED>；状态：<status>
GitHub：<authoritative PR or Issue>；Checkpoint：<short checkpoint>；下一动作：<short next action>

When a GitHub write fails, include the actual platform error required for recovery. Do not duplicate the full GitHub audit in Chat.

If this scheduled reply appears in a human collaboration conversation, or task/session binding is unknown, report `SESSION_ISOLATION_FAILED` or `SESSION_BINDING_UNKNOWN`, perform no further scheduled development write, and keep the task disabled until it is recreated from a dedicated Relay Runtime conversation.
```

## Production schedule safety fuse

```ical
BEGIN:VEVENT
DTSTART;TZID=Asia/Shanghai:<OWNER_SELECTED_START>
RRULE:FREQ=HOURLY;COUNT=720
END:VEVENT
```

Timing mode: `exact_schedule`.

The 720-run count is a 30-day scheduling fuse, not a Work Item or Program completion estimate. Logical termination remains Owner stop/revocation, out-of-mandate or safety abort, or truthful M1–M3 Program completion.

## Migration rule

The previous task associated with the human collaboration conversation remains disabled. The platform surface currently available to this Run does not expose a supported target-conversation parameter, so it cannot be safely retargeted in place.

Migration requires one Owner UI action:

1. create/open a dedicated conversation named, for example, `Pytest-playwright-e2e Relay Runtime`;
2. create the scheduled task in that conversation using the approved bootstrap above;
3. first run one read-only binding probe;
4. enable production writes only after the receipt is confirmed to appear exclusively in the dedicated runtime conversation and the expected GitHub probe record exists.
