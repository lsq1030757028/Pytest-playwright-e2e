Execute one Production Hourly GitHub Relay Run for repository `lsq1030757028/Pytest-playwright-e2e`.

Runtime declaration:
- session_class: RELAY_RUNTIME
- durable_context: GITHUB_ONLY
- conversation_history_authoritative: false
- execution_profile: PARALLEL_WORK_CLAIMS

Do not use prior Chat prose as project state, authority, checkpoint or evidence. Restore everything from GitHub.

## Required durable sources

Read `main:AGENTS.md` and every required SSOT. In particular:

- `docs/program-delivery-ssot.yaml` — `AUTHORITATIVE_DELIVERY`; the only source for **SHOULD_DO_NEXT**;
- `docs/program-delivery-ssot.md` — human companion only;
- `docs/github-development-ssot.yaml` and `.md` — process/safety and **MAY_DO** rules;
- `docs/specs/autonomous-execution-mandate.yaml` — standing authority only;
- Issues #65 / #66 — explicit TEST_AGENT_RUNTIME_BETA owner authority when applicable;
- Issues #49 / #55 and `docs/specs/parallel-work-claims.{md,yaml}` — Relay/claim ownership protocol;
- `docs/specs/hourly-github-relay.md` and `docs/specs/hourly-github-relay-parallel-claims.md` with YAML companions.

`docs/product-work-map.yaml` is `SUPERSEDED_DELIVERY_MAP_OR_COMPATIBILITY_VIEW`. It may be inspected for migration/history compatibility but **must never select or reorder work**. `docs/implementation-status.md`, horizontal roadmaps and the Beta roadmap are generated/reference/input views according to Program Delivery `source_roles`; they cannot override the Program Delivery execution pointer or selection policy.

Read control state from branch `ops/hourly-github-relay-control`:
- `.agent/relay/leases/hourly-github-relay.json`
- `.agent/relay/work-claims.json` — `OPERATIONAL_EXECUTION_STATE_ONLY`, answers **WHO_DOES_IT**;
- `.agent/relay/leases/integration.json`

Fail closed before development writes when session binding is uncertain, Program Delivery is absent/invalid/split-brain, the claim registry is disabled or malformed, or the compatibility Lease is ACTIVE for exclusive maintenance. Report the exact status and stop.

## Authority before execution

Program Delivery desirability never grants permission.

For every candidate before allocation or mutation:

1. resolve Goal and required SPEC from Program Delivery;
2. evaluate authorization independently;
3. M1–M3 work may use `MANDATE-AUTONOMY-M1-M3@1.0.0` when its Goal/SPEC are covered;
4. M4–M6 or other work outside that mandate requires explicit recorded owner authority (for the Beta program, Issues #65/#66) **and an approved relevant SPEC**;
5. if authorization is missing, return `OUT_OF_MANDATE` or `BLOCKED`; do not silently fall back to another roadmap or broaden the mandate.

Never bypass failed gates, touch production/personal data or Secrets, alter Oracle/Policy/Permission, or perform irreversible or unbounded external actions without separate explicit authority.

## Work Item behavior

The ordering question and the ownership question are separate:

### SHOULD_DO_NEXT

Use `docs/program-delivery-ssot.yaml` only. Apply its deterministic `selection_policy.classes_in_order`, then its explicit priority and stable Work Item ID tie-break. Do not infer priority from milestone number, PR number, file age, discussion volume or claim sequence.

### WHO_DOES_IT

1. If an unexpired `RELAY_RUNTIME` claim exists for a still-valid Program Delivery Work Item, revalidate its product state and authorization, then resume it.
2. Recover an expired claim only after branch, PR and CI activity prove it abandoned; recovery changes ownership only, not product state.
3. Otherwise take the ordered Program Delivery candidate set, remove candidates that are not authorized, not `READY`, have open dependencies, are already owned, or conflict by domain/branch/PR, and select the first remaining candidate **without reordering the Program Delivery list**.
4. Allocate through one GitHub blob-SHA / registry-revision CAS and reread to verify ownership.
5. When no safe item exists, make no development mutation and return `NO_CLAIMABLE_WORK`, `BLOCKED`, `OUT_OF_MANDATE`, `REPLAN_REQUIRED` or `WAITING` according to the actual reason.

A Claim Registry entry can remove an ownership candidate but cannot make a blocked Work Item ready, cannot create product priority and cannot close a Product Slice.

If Program Delivery and Relay selection disagree, stop as `REPLAN_REQUIRED`; do not use `docs/product-work-map.yaml` as fallback.

Create a unique Run Token after the allocation or resume heartbeat using:
`relay-<work-item-id>-r<resulting-registry-revision>-<UTC-start-time>`.
Record both Run Token and Claim Token in the authoritative GitHub Run comment. Every development Commit contains `[RELAY:<run-token>]`.

Before every mutation, reread the registry and verify: registry enabled, claim token, active state, expiry, exclusive domain, target branch, target PR and actual branch Head equal to the claim's expected Head. Also reread Program Delivery when the mutation changes product state or when another integration may have changed dependencies. After a self-created Commit, update the expected Head through registry CAS before another mutation. On mismatch stop as `LOST_CLAIM` or `REPLAN_REQUIRED`. Never force push, reset or overwrite.

Different non-conflicting Work Items may run concurrently. Never mutate a foreign claim or create a competing branch/PR to evade a conflict.

An incomplete Work Item keeps its claim across Runs only while Product Delivery and authorization remain valid. End at a durable checkpoint with completed evidence, unresolved questions and next valid action recorded, then heartbeat and extend the claim. The next scheduled Run resumes that claim after revalidation.

Only `EVIDENCE_READY` work enters the integration queue. Merge, `main`, release evidence and final Program Delivery/status closure require the single ACTIVE holder of `.agent/relay/leases/integration.json`. A Work Item claim alone never authorizes integration or product closure.

Maintain exactly one GitHub comment per Run:
`START → WORKING/VERIFYING → PRE_FINAL → FINAL`.
The full audit remains on GitHub.

Reply only with a bounded Chinese receipt, normally no more than 500 Chinese characters:

Run Token：<token or UNACQUIRED>；状态：<status>
GitHub：<authoritative PR or Issue>；Work Item：<id or NONE>；Checkpoint：<short checkpoint>；下一动作：<short next action>

When a GitHub write fails, include the actual platform error required for recovery.

If this scheduled reply appears in a human collaboration conversation, report `SESSION_ISOLATION_FAILED`, perform no further scheduled development write, and keep the task disabled until recreated or repaired in a dedicated Relay Runtime conversation.

**This prompt migration does not enable the scheduled task.** `Pytest GitHub Relay` remains disabled until `docs/program-delivery-ssot.yaml:relay_enablement.reenable_requires` is fully satisfied and a separate bounded acceptance/re-enable action completes.