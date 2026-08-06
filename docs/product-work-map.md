# M1–M3 Product Work Map

> Map ID: `PRODUCT-WORK-MAP-M1-M3@0.1.0`  
> Status: `CANDIDATE`  
> Machine source: `docs/product-work-map.yaml`

## Purpose

This map turns the roadmap into claimable business Work Items. It does not change the approved M1–M3 product order; it identifies which work can safely overlap and where integration must wait.

## Current delivery lanes

| Work Item | Business result | Current readiness | Exclusive lane | Integration group |
|---|---|---:|---|---|
| `RELAY-CONVERSATION-ISOLATION-CLOSE` | Close and merge the isolated scheduled Relay design | Ready after final acceptance evidence | `relay-control-plane` | `RELAY_FOUNDATION` |
| `PARALLEL-WORK-CLAIMS-SPEC` | Approve the claim and integration-queue rules | In progress | `parallel-delivery-control` | `RELAY_FOUNDATION` |
| `M1A-RUNTIME-CONTRACTS-CLOSE` | Close the executable governed-memory contract foundation | Ready | `memory-runtime-contracts` | `M1_FOUNDATION` |
| `UX-FP-FN-BENCHMARK-SPEC` | Define false-positive and false-negative quality proof | Ready and parallel-safe | `ux-benchmark` | `UX_ASSURANCE` |
| `M1B-STORE-RETRIEVAL-SPEC` | Define persistent memory storage and progressive retrieval | Blocked by M1A closure | `memory-store-retrieval` | `M1_MEMORY` |

This means the human Chat can work on the parallel-delivery foundation while the scheduled Relay works on M1A or UX, provided the claims do not overlap.

## M1 delivery map

```text
M1A Runtime Contracts closure
├── unlocks M1B Store & Progressive Retrieval
│   └── unlocks M1C Memory Formation
│       └── unlocks M1D Shared Governance
│           └── unlocks M1E Controlled Evolution
│               └── unlocks M1F Memory Gate
└── may run beside UX FP/FN Benchmark work
```

M1B through M1F remain sequential where their product dependencies require it. Supporting quality, security, documentation and project-fixture work may run in separate lanes when explicitly declared.

## M2 delivery map

After M1 Gate:

```text
M2A Model Capability Profile
├── M2B Contract and Output Normalization
└── M2C Weak-model Execution Ladder
    └── M2D Cross-model Benchmark
        └── M2E Routing and Escalation
            └── M2 Gate
```

M2B and M2C may overlap after M2A when their SPECs declare separate scopes. M2D joins them; M2E depends on benchmark evidence.

## M3 delivery map

After M2 Gate:

```text
M3A Project and Architecture Contracts
├── M3B Complex Web Matrix
├── M3C Mobile Adapters and Devices
├── M3D Mini-program Adapter
└── M3E Embedded / IoT Adapter
    └── M3F Device Lab and Cross-project Gate
```

M3B–M3E are intended parallel lanes after M3A. They use separate repositories or fixtures only when the approved module SPEC requires independent targets. M3F is their integration point.

## Integration cadence

Parallel work is joined at three levels:

1. each PR passes its own module evidence;
2. each integration group runs combination checks before merge or promotion;
3. milestone and global safety gates run before stage delivery.

The integration queue remains serialized even when development is parallel.
