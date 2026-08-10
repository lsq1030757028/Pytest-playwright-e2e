# M1–M3 Product Work Map

> Map ID: `PRODUCT-WORK-MAP-M1-M3@0.1.0`  
> Status: `SUPERSEDED`  
> Source Role: `SUPERSEDED_DELIVERY_MAP_OR_COMPATIBILITY_VIEW`  
> Delivery Selection Authoritative: `false`  
> Canonical Delivery SSOT: `docs/program-delivery-ssot.yaml`  
> Machine compatibility source: `docs/product-work-map.yaml`

## Supersession notice

This document preserves the earlier M1–M3 horizontal work-map design for audit, migration and compatibility. It **must not answer “what should we do next?”** and must not be used to reorder Program Delivery Work Items.

Current product state, BETA-A→E slices, critical path, readiness and next-work selection come only from `docs/program-delivery-ssot.yaml`. Claim Registry state only answers execution ownership.

The historical content below is intentionally retained so old Goal/PR/Relay evidence remains understandable. Its readiness labels and dependency sequence may be stale by design.

## Historical purpose

This map originally turned the horizontal roadmap into claimable M1–M3 business Work Items. Under `SPEC-PROGRAM-DELIVERY-SSOT@1.0.0`, claimable product definitions migrate to Program Delivery and this map no longer owns product order.

## Historical delivery lanes

| Work Item | Business result | Historical readiness | Exclusive lane | Integration group |
|---|---|---:|---|---|
| `RELAY-CONVERSATION-ISOLATION-CLOSE` | Close and merge the isolated scheduled Relay design | Ready after final acceptance evidence | `relay-control-plane` | `RELAY_FOUNDATION` |
| `PARALLEL-WORK-CLAIMS-SPEC` | Approve the claim and integration-queue rules | In progress | `parallel-delivery-control` | `RELAY_FOUNDATION` |
| `M1A-RUNTIME-CONTRACTS-CLOSE` | Close the executable governed-memory contract foundation | Ready | `memory-runtime-contracts` | `M1_FOUNDATION` |
| `UX-FP-FN-BENCHMARK-SPEC` | Define false-positive and false-negative quality proof | Ready and parallel-safe | `ux-benchmark` | `UX_ASSURANCE` |
| `M1B-STORE-RETRIEVAL-SPEC` | Define persistent memory storage and progressive retrieval | Blocked by M1A closure | `memory-store-retrieval` | `M1_MEMORY` |

## Historical M1 delivery map

```text
M1A Runtime Contracts closure
├── unlocks M1B Store & Progressive Retrieval
│   └── unlocks M1C Memory Formation
│       └── unlocks M1D Shared Governance
│           └── unlocks M1E Controlled Evolution
│               └── unlocks M1F Memory Gate
└── may run beside UX FP/FN Benchmark work
```

This sequence is now a reference capability dependency, not the product critical path. Program Delivery may advance an operating Beta slice before unrelated horizontal modules when the active slice does not require them.

## Historical M2 delivery map

```text
M2A Model Capability Profile
├── M2B Contract and Output Normalization
└── M2C Weak-model Execution Ladder
    └── M2D Cross-model Benchmark
        └── M2E Routing and Escalation
```

These relationships remain useful architecture references, but Program Delivery decides whether and when an M2 capability becomes active product work.

## Historical M3 delivery map

```text
M3A Project and Architecture Contracts
├── M3B Complex Web Matrix
├── M3C Mobile Adapters and Devices
├── M3D Mini-program Adapter
└── M3E Embedded / IoT Adapter
    └── M3F Device Lab and Cross-project Gate
```

Again, this is not a requirement to complete every horizontal branch before a user-runnable Beta slice.

## Integration cadence retained

Parallel work is still joined through evidence and serialized integration:

1. each PR passes its own module evidence;
2. related integration checks run at the required boundary;
3. Program Delivery Product Slice / release safety gates run before product closure.

Integration ownership remains serialized even when development is parallel. Product priority remains exclusively in `docs/program-delivery-ssot.yaml`.