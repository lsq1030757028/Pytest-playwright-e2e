# Hourly GitHub Relay Termination Addendum

> Addendum ID: `ADDENDUM-HOURLY-GITHUB-RELAY-TERMINATION@0.1.0`  
> Parent SPEC: `SPEC-HOURLY-GITHUB-RELAY@0.1.0`  
> Goal: Issue #49  
> Status: `CANDIDATE / PILOT_APPROVED`

## 1. Purpose

The hourly Relay must be bounded. A recurring task is an execution mechanism, not permission to invent new scope forever.

Two independent limits apply:

1. **Pilot limit** — bounds the current experiment that proves scheduling, context recovery, Chat reporting, GitHub audit and concurrency control.
2. **Program completion limit** — bounds any later production Relay to the currently authorized M1–M3 delivery program.

## 2. Current Pilot hard limit

The current Pilot scheduled task has a maximum of **6 hourly invocations**.

The hard limit exists because ChatGPT scheduled tasks do not expose a reliable condition that can be guaranteed to disable the same recurring task from inside its own Run. A finite RRULE is therefore the authoritative platform-level stop.

The Pilot may be renewed only through a new Owner instruction after reviewing the accumulated Run evidence.

## 3. Pilot logical completion

The Pilot reaches `PILOT_ACCEPTED` when three consecutive lease-acquiring Runs satisfy all of the following:

- unique monotonic Run Tokens;
- successful CAS lease acquisition and release;
- correct fencing checks before mutations;
- START and FINAL on the correct authority with no duplicate Run comment;
- a generated Chinese Chat final response;
- no overlapping development ownership;
- every created Commit traces to its Run Token;
- no failed CI, Review, Evidence, Release, Human UAT or safety gate is bypassed;
- runtime surface/model/reasoning fields are truthful or `UNKNOWN`;
- no unresolved `LEASE_STATE_INVALID`, `LOST_LEASE` or audit inconsistency.

`BUSY`, failed-to-acquire and invalid-state invocations do not count toward the three successful Runs, but they consume the hard invocation cap.

When `PILOT_ACCEPTED` is reached, the Run must:

1. finish the current safe increment and release the Lease;
2. write a terminal summary to Issue #49 and the Pilot PR;
3. set the control Lease last status to `PILOT_ACCEPTED_STOP_REQUESTED` while leaving operational status `IDLE`;
4. perform no further product-development mutation in later Pilot invocations;
5. return a mandatory Chat response asking the Owner to review promotion or closure.

Later invocations before the finite schedule expires are `NO_ACTION / PILOT_TERMINAL` and perform no Campaign, CI, PR or branch mutation.

## 4. Early termination

The Pilot terminates early as `PILOT_ABORTED` when any condition is met:

- Owner explicitly stops or revokes it;
- a safety, authority, production-data, Secret, Permission, Oracle or irreversible-write boundary is encountered;
- two consecutive Runs detect `LEASE_STATE_INVALID` that cannot be safely repaired;
- a Run writes without a valid Lease or violates fencing;
- duplicate Run identity or duplicate active ownership is observed;
- Chat and GitHub FINAL records materially disagree;
- the design PR is closed as rejected or superseded.

On early termination, release the Lease when safely possible, record the reason, perform no further development mutation and rely on task disablement or the finite RRULE for platform shutdown.

## 5. Production Relay program completion

A later production Relay must not interpret “continue the plan” as unlimited roadmap expansion.

Under the current standing mandate, the authorized program completion boundary is:

```text
M1 Memory Gate: PASS / CLOSED
M2 Model Generalization Gate: PASS / CLOSED
M3 Project & Architecture Generalization Gate: PASS / CLOSED
Global Safety Gate: PASS
Stage Delivery: TEST_AGENT_RUNTIME_BETA
all required M1–M3 Goals, PRs, main/release evidence, ledgers and branch cleanup: CLOSED
no blocking Human UAT or unresolved required evidence for that stage
```

When this boundary is reached, the Relay must set `PROGRAM_COMPLETE`, release its Lease, write a final delivery summary and stop selecting further work. M4 task decomposition, M5 durable runtime and M6 later product work require a separate Owner-approved program or mandate extension; they are not automatically started.

## 6. No-work is not completion

The following do not terminate the program by themselves:

- temporary `NO_ACTION`;
- `WAITING_CI`;
- infrastructure outage;
- a single closed module while later approved modules remain;
- no visible change during one hour;
- a Draft PR or unmerged implementation;
- passing PR CI without main/release/ledger/cleanup closure.

These states retain a next valid action or remain blocked. They must not be mislabeled as “all work complete.”

## 7. Operational rule

Every Run must evaluate termination before selecting new work in this order:

```text
OWNER_STOP / REVOCATION
→ PILOT_ABORTED
→ PILOT_ACCEPTED
→ PROGRAM_COMPLETE
→ ACTIVE CAMPAIGN
→ BLOCKED / WAITING / NO_ACTION
```

A terminal state forbids new Campaign scope and development writes.
