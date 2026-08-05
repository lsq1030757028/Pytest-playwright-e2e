# Hourly GitHub Relay Work Item Lifecycle Addendum

> Addendum ID: `ADDENDUM-HOURLY-GITHUB-RELAY-WORK-ITEM-LIFECYCLE@0.1.0`  
> Parent SPEC: `SPEC-HOURLY-GITHUB-RELAY@0.1.0`  
> Goal: Issue #49  
> Status: `CANDIDATE / PILOT_APPROVED`

## 1. Correct unit model

An hourly Run is an execution window, not a roadmap step and not a promise that one Work Item will finish within one hour.

```text
Program
→ Campaign
→ Work Item
→ Run / Checkpoint
```

- **Program**: the approved M1–M3 delivery scope and its terminal gates.
- **Campaign**: one coherent Goal or module spanning multiple Runs.
- **Work Item**: one semantic objective with explicit completion criteria; it may span many Runs.
- **Run**: one scheduled execution window that advances the active Work Item to a durable checkpoint.

No Run-count limit may be inferred from the number of roadmap phases or Work Items.

## 2. Run timebox

The hourly cadence means a new invocation is attempted every hour. It does not require the active Work Item to finish within that hour.

A lease-holding Run should reserve enough time for final evidence and handoff. Recommended operational budget:

- up to 45 minutes of active investigation or implementation;
- reserve the remaining execution budget for verification, GitHub FINAL, Campaign handoff and lease release;
- stop earlier at a natural checkpoint, external wait, authority boundary or safety boundary;
- never rush acceptance, skip evidence or split a semantic change merely to fit a timer.

If the runtime does not expose a reliable remaining-time signal, stop at the earliest safe natural checkpoint after meaningful progress.

## 3. Multi-Run Work Items

A complex Work Item remains active across Runs. The next Run restores it from GitHub and continues rather than creating a new unrelated task.

Recommended persisted fields:

```yaml
work_item:
  id: string
  objective: string
  status: PLANNED | ACTIVE | WAITING | VERIFYING | BLOCKED | COMPLETE | SUPERSEDED
  completion_criteria: []
  current_checkpoint: string
  completed_evidence: []
  unresolved_questions: []
  candidate_options: []
  rejected_options: []
  next_valid_action: string
  owner_authority_required: false
  runs: []
```

Examples of valid multi-Run Work Items:

- selecting representative open-source projects for M3;
- evaluating licenses, architectures, testability and safe fixtures;
- implementing a storage adapter and its migration/recovery evidence;
- running cross-model benchmark campaigns;
- waiting for long CI, artifact publication or external infrastructure recovery.

## 4. Open-source project selection

Selecting an external project is a governed Work Item, not a one-hour lookup. It may use checkpoints such as:

```text
DEFINE_SELECTION_CRITERIA
→ BUILD_CANDIDATE_SET
→ LICENSE_AND_SAFETY_SCREEN
→ ARCHITECTURE_AND_TESTABILITY_REVIEW
→ REPRODUCIBLE_BASELINE
→ FINAL_SELECTION
→ PINNED_REVISION_AND_ASSET_LEDGER
```

No candidate becomes an approved benchmark target until the Work Item completion criteria and required authority are satisfied.

## 5. Progress and stagnation rules

The Relay must distinguish long work from stuck work.

- One Run with no completion is normal.
- Three consecutive lease-holding Runs with no new evidence, decision, checkpoint or blocker change trigger `REORIENT`.
- Six consecutive lease-holding Runs with no meaningful progress trigger `REPLAN_REQUIRED` and pause new implementation until the plan or blocker is updated.
- Repeating the same failed action without a changed precondition is forbidden.
- External waiting does not count as implementation failure, but the Relay must not rerun or rewrite merely to appear active.

## 6. Pilot versus production Relay

The current `COUNT=6` schedule is only a bounded control-plane Pilot. It validates scheduling, lease, fencing, GitHub records and Chat reporting. It is not the time budget for M1–M3 and must not be mapped to roadmap steps.

Pilot termination means one of:

- the Relay mechanism is accepted and a separately authorized production Relay schedule may be created;
- the Pilot is rejected or blocked and no production Relay is created.

The Pilot may safely advance an already authorized Campaign, but failure to finish that Campaign within six invocations is not a Pilot failure.

## 7. Production Relay lifecycle

A future production Relay must not use a Run count derived from roadmap steps. It should use:

- business terminal conditions (`PROGRAM_COMPLETE`, Owner stop, mandate revocation);
- a calendar safety fuse requiring explicit renewal, rather than a small arbitrary Run count;
- periodic operational reviews;
- durable terminal state in GitHub;
- best-effort self-disable when terminal, with terminal no-write behavior as fallback.

Recommended initial safety fuse after Pilot acceptance: 30 calendar days, subject to Owner renewal.

## 8. Program terminal condition

The approved M1–M3 Program is complete only when all required project gates, Goals, PRs, main/release evidence, ledgers, cleanup and required Human UAT are truthfully closed. Work Item count and Run count are irrelevant to this decision.

M4, M5 and M6 do not start automatically after Program completion.
