# Hourly GitHub Relay Parallel Work Claiming Addendum

> Addendum ID: `ADDENDUM-HOURLY-GITHUB-RELAY-PARALLEL-CLAIMS@0.2.0`  
> Parent SPEC: `SPEC-HOURLY-GITHUB-RELAY@0.1.0`  
> Goal: Issue #49  
> Foundation authority: Issue #55, merged PRs #56 and #57  
> Status: `OWNER_ACCEPTED / ACTIVATION_GATED`

## 1. Business outcome

The human collaboration Chat and the dedicated scheduled Relay Runtime may work at the same time when they own different, non-conflicting Work Items. The same Work Item, exclusive domain, branch or PR remains single-owner. Integration, merge, release and final project-state closure remain serialized.

This addendum supersedes repository-wide development ownership in the earlier concurrency addendum. The old global Relay Lease remains a compatibility kill switch and an exclusive maintenance lock; it is no longer the normal lock for module development after activation.

## 2. Authoritative control state

```text
Product work map:
  main:docs/product-work-map.yaml

Work Item claims:
  ops/hourly-github-relay-control:.agent/relay/work-claims.json

Serialized integration lease:
  ops/hourly-github-relay-control:.agent/relay/leases/integration.json

Compatibility / maintenance lease:
  ops/hourly-github-relay-control:.agent/relay/leases/hourly-github-relay.json
```

GitHub remains the only durable handoff and recovery plane. Chat history is never project authority.

## 3. Wake and selection behavior

Every invocation must:

1. read repository SSOT and the product work map;
2. read the compatibility Lease, Work Item claim registry and integration Lease;
3. fail closed when the claim registry is disabled or malformed;
4. resume the unexpired claim already owned by its session class when one exists;
5. otherwise recover only claims that are expired and have no recent branch, PR or CI activity;
6. select the highest-priority `READY` Work Item whose dependencies are closed, authority and SPEC exist, and conflict checks pass;
7. allocate it through one registry revision compare-and-swap;
8. reread and verify ownership before creating a Run record or development write.

When no safe Work Item exists, return `NO_CLAIMABLE_WORK`, `BLOCKED` or `WAITING` with no development mutation.

## 4. Parallel ownership rules

Different claims may be active together only when all of these differ or are explicitly compatible:

- Work Item ID;
- exclusive domain;
- target branch;
- target PR;
- declared incompatible domains.

A contender must reject an overlap deterministically. It must not create an alternative branch or PR to evade the conflict.

Observation of another domain is read-only and does not grant mutation authority.

## 5. Claim and Run identity

`claim_token` owns the Work Item across multiple hourly Runs. A Work Item may remain claimed across natural checkpoints until it reaches evidence-ready, blocked handoff, superseded or closed state.

Each invocation also has a unique `run_token`. On allocation or resume, the invocation first performs a revision-fenced registry heartbeat. The resulting registry revision is included in the Run identity:

```text
relay-<work-item-id>-r<registry-revision>-<UTC-start-time>
```

Every development Commit contains `[RELAY:<run-token>]`. The GitHub Run record stores both `claim_token` and `run_token`.

## 6. Per-mutation fencing

Immediately before every mutation, reread the claim registry and require:

```text
registry enabled == true
claim token matches
claim state is active
current time < claim expiry
exclusive domain matches
target branch matches
target PR matches
actual branch Head == expected_head_sha
```

After a self-created Commit, update the claim's expected Head through registry CAS before another mutation. Unexpected branch movement, registry revision conflict or ownership change stops the Run as `LOST_CLAIM` or `REPLAN_REQUIRED`. Force push, reset and overwrite are forbidden.

## 7. Compatibility Lease behavior

After production activation, ordinary module work does not acquire the global Relay Lease.

A valid ACTIVE compatibility Lease means exclusive control-plane maintenance or emergency stop is in progress. No new Work Item claim may be allocated and existing claim owners perform no new development mutation until it returns to IDLE.

Malformed compatibility state remains fail-closed. The compatibility Lease may not be silently ignored.

## 8. Multi-Run checkpoint behavior

An incomplete Work Item keeps its claim and records a durable checkpoint. Before ending the Run it must:

- update the same GitHub Run comment to PRE_FINAL;
- record completed evidence, unresolved questions and next valid action;
- heartbeat the claim and extend expiry;
- leave the branch Head and expected Head consistent;
- emit the bounded Relay Runtime receipt.

A later Run resumes the same claim rather than selecting unrelated work.

A genuinely blocked item may release its claim only after the blocker and re-entry condition are durable and another eligible item may safely proceed.

## 9. Integration queue

Module development and module evidence may run in parallel. Integration remains one-owner:

1. only `EVIDENCE_READY` work enters the integration queue;
2. queue ordering follows security/correctness repair, dependency unblocking, then enqueue time;
3. only the ACTIVE holder of `integration.json` may merge, update `main`, publish release evidence or close final project status;
4. the integration holder revalidates the module claim, final Head, CI, Review and evidence before integration;
5. one integration result is completed or rolled back before the next entry begins.

A module claim does not itself authorize merge or release.

## 10. Session isolation

`HUMAN_CONTROL` and `RELAY_RUNTIME` remain separate conversations. They share GitHub state but not conversational memory.

The binding probe already accepted for the dedicated Relay Runtime session remains valid only while scheduled receipts continue to appear exclusively there. A scheduled receipt in the human collaboration conversation causes `SESSION_ISOLATION_FAILED`, immediate no-write behavior and task disablement.

## 11. Activation sequence

Production parallel claiming is enabled only after all of these are true:

- PRs #56 and #57 are merged and verified on `main`;
- this protocol addendum and updated bootstrap are merged;
- the product work map reflects the merged foundation state;
- the scheduled task is paused during migration;
- one bounded scheduled claim probe allocates and releases or checkpoints exactly one safe Work Item;
- the probe receipt appears only in the dedicated Relay Runtime session;
- the registry is cleared or contains only the intended production claim after the probe.

Until then, `work-claims.json.enabled` remains `false` outside the bounded probe.

## 12. Rollback

Rollback is deterministic:

1. disable the scheduled task;
2. set the claim registry to disabled without deleting audit history;
3. clear only acceptance-only claims after evidence is recorded;
4. return the integration Lease to IDLE when safely owned;
5. use the compatibility Lease for exclusive repair;
6. preserve all Issues, PRs, Commits, CI and Run records.

Rollback never force-pushes or deletes development evidence.
