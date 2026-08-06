Execute one Production Hourly GitHub Relay Run for repository `lsq1030757028/Pytest-playwright-e2e`.

Runtime declaration:
- session_class: RELAY_RUNTIME
- durable_context: GITHUB_ONLY
- conversation_history_authoritative: false
- execution_profile: PARALLEL_WORK_CLAIMS

Do not use prior Chat prose as project state, authority, checkpoint or evidence. Restore everything from GitHub.

Read `main:AGENTS.md` and every required SSOT. Read Issue #49, Issue #55, `docs/product-work-map.yaml`, `docs/specs/parallel-work-claims.md`, `docs/specs/hourly-github-relay.md`, and `docs/specs/hourly-github-relay-parallel-claims.md` with their YAML companions.

Read control state from branch `ops/hourly-github-relay-control`:
- `.agent/relay/leases/hourly-github-relay.json`
- `.agent/relay/work-claims.json`
- `.agent/relay/leases/integration.json`

Fail closed before development writes when session binding is uncertain, the claim registry is disabled or malformed, or the compatibility Lease is ACTIVE for exclusive maintenance. Report the exact status and stop.

Work Item behavior:
1. Resume the unexpired claim owned by `RELAY_RUNTIME` when one exists.
2. Recover an expired claim only after branch, PR and CI activity prove it abandoned.
3. Otherwise select the highest-priority `READY` Work Item whose dependencies are closed, authority and approved SPEC exist, and Work Item/domain/branch/PR conflicts are absent.
4. Allocate through one GitHub blob-SHA / registry-revision CAS and reread to verify ownership.
5. When no safe item exists, make no development mutation and return `NO_CLAIMABLE_WORK`, `BLOCKED` or `WAITING`.

Create a unique Run Token after the allocation or resume heartbeat using:
`relay-<work-item-id>-r<resulting-registry-revision>-<UTC-start-time>`.
Record both Run Token and Claim Token in the authoritative GitHub Run comment. Every development Commit contains `[RELAY:<run-token>]`.

Before every mutation, reread the registry and verify: registry enabled, claim token, active state, expiry, exclusive domain, target branch, target PR and actual branch Head equal to the claim's expected Head. After a self-created Commit, update the expected Head through registry CAS before another mutation. On mismatch stop as `LOST_CLAIM` or `REPLAN_REQUIRED`. Never force push, reset or overwrite.

Different non-conflicting Work Items may run concurrently. Never mutate a foreign claim or create a competing branch/PR to evade a conflict.

An incomplete Work Item keeps its claim across Runs. End at a durable checkpoint with completed evidence, unresolved questions and next valid action recorded, then heartbeat and extend the claim. The next scheduled Run resumes that claim.

Only `EVIDENCE_READY` work enters the integration queue. Merge, `main`, release evidence and final status closure require the single ACTIVE holder of `.agent/relay/leases/integration.json`. A Work Item claim alone never authorizes integration.

Operate only within `MANDATE-AUTONOMY-M1-M3@1.0.0`. Do not enter M4/M5/M6, bypass failed gates, touch production/personal data or Secrets, alter Oracle/Policy/Permission, or perform irreversible or unbounded external actions.

Maintain exactly one GitHub comment per Run:
`START → WORKING/VERIFYING → PRE_FINAL → FINAL`.
The full audit remains on GitHub.

Reply only with a bounded Chinese receipt, normally no more than 500 Chinese characters:

Run Token：<token or UNACQUIRED>；状态：<status>
GitHub：<authoritative PR or Issue>；Work Item：<id or NONE>；Checkpoint：<short checkpoint>；下一动作：<short next action>

When a GitHub write fails, include the actual platform error required for recovery.

If this scheduled reply appears in a human collaboration conversation, report `SESSION_ISOLATION_FAILED`, perform no further scheduled development write, and keep the task disabled until recreated or repaired in a dedicated Relay Runtime conversation.
