# Program Delivery SSOT

> ID: `PROGRAM-DELIVERY-SSOT@1.0.0`  
> 状态：`ACTIVE`  
> Source Role：`AUTHORITATIVE_DELIVERY_HUMAN_COMPANION`  
> 机器事实源：`docs/program-delivery-ssot.yaml`  
> Governing SPEC：`SPEC-PROGRAM-DELIVERY-SSOT@1.0.0`  
> Goal：#91

本文件是机器 SSOT 的人类可读伴随视图。**真正决定“下一步做什么”的唯一机器事实源是 `docs/program-delivery-ssot.yaml`。** 本文件不得独立改变状态、优先级或依赖。

## 1. 当前结论

```text
Product: TEST_AGENT_RUNTIME_BETA
Program State: BETA_A_IMPLEMENTATION
Active Slice: BETA-A
Current Focus: BETA-A-IMPLEMENTATION
Next Slice After Active: BETA-B
Scheduled Relay: DISABLED_GOVERNANCE_MIGRATION
```

BETA-A 的独立 Goal #95 与 `SPEC-BETA-A-DURABLE-GOVERNED-PACK@0.1.0` 已通过 PR #96 合入 `main`，并完成 dedicated SPEC、Full Quality、Secret Scan、CodeQL、Release 与 Cleanup 的主干验证。因此 `BETA-A-SPEC = CLOSED`，产品关键路径正式进入 `BETA-A-IMPLEMENTATION → BETA-A-ACCEPTANCE`。

## 2. 三个问题，三个事实面

| 问题 | 事实面 | 含义 |
|---|---|---|
| **MAY_DO** | Authorization | Policy / Oracle / Permission / Owner Authority / Mandate / Goal / SPEC 决定是否有权做 |
| **SHOULD_DO_NEXT** | Program Delivery | `docs/program-delivery-ssot.yaml` 唯一决定产品当前/下一步 |
| **WHO_DOES_IT** | Claim Registry | 只决定谁持有 Work Item、分支/PR fencing、heartbeat、expiry 和 integration queue |

Program Delivery 不能扩大授权；Claim Registry 不能创造产品优先级或完成状态。BETA-A 实施使用 #65/#66 的显式 owner scope extension、Goal #95 与已批准 BETA-A SPEC；`MANDATE-AUTONOMY-M1-M3@1.0.0` 本身没有被扩张。

## 3. 产品推进主轴

```text
BETA-A  已有 governed test pack → durable job → execute → evidence → verdict
  ↓
BETA-B  requirement → reviewable generated test → execute → verdict
  ↓
BETA-C  diagnose → bounded test-workflow repair → rerun → verdict
  ↓
BETA-D  restart → durable state + governed Memory → resume
  ↓
BETA-E  two materially different projects → Beta acceptance
```

当前 `BETA-A = IMPLEMENTING`。BETA-B～E 仍由 slice dependency 阻塞。

## 4. 当前关键路径

```text
BETA-A-IMPLEMENTATION
→ BETA-A-ACCEPTANCE
```

`PROGRAM-DELIVERY-SSOT-IMPLEMENTATION = CLOSED`。  
`BETA-A-SPEC = CLOSED`，对应 Goal #95 / PR #96 / `SPEC-BETA-A-DURABLE-GOVERNED-PACK@0.1.0`。  
`BETA-A-IMPLEMENTATION = READY`，是当前 canonical selector 应唯一选择的产品 Work Item。

当前并行能力泳道仍包括：

- PR #85：M1C migration evidence closure → BETA-D 支撑；
- PR #63：UX FP/FN SPEC → BETA-C/E 支撑。

这些并行泳道不能因为 claim 顺序、PR 编号或 milestone 编号而取代 BETA-A 产品关键路径。

## 5. BETA-A 实施边界

已批准 SPEC 将本阶段收窄为：

- 用户通过 CLI 提交 pinned project + **existing governed Pytest/Playwright pack**；
- SQLite WAL 保存 durable job/event/attempt/lease state；
- exact required node collection，缺失/skip/xfail/deselect 不能产生 `VERIFIED_SUCCESS`；
- 一个 job 最多一次实际 execution launch，automatic execution retry = `0`；
- `command_started` 后发生不确定崩溃时禁止自动重跑，完整 active resume 留给 BETA-D；
- evidence 使用 SHA-256 content addressing；
- deterministic verifier 是唯一 final verdict authority；
- product tree read-only、network deny-by-default、无 host Secret/socket 继承、无 shell interpolation；
- `CANCELLED` 只有在 process tree termination 与 cleanup 被证明后才能发布；
- package/container smoke、restart、replay、mutation、UX3 journey evidence 均是实施验收的一部分。

本阶段不做 test generation、diagnosis/repair、governed Memory reuse、two-project acceptance，也不恢复 Scheduled Relay。

## 6. 下一工作选择规则

在授权、安全和 claim 冲突检查通过后，顺序固定为：

1. Security / correctness repair；
2. Active Slice blocker；
3. Active Slice closer；
4. Dependency-unblocking integration；
5. 映射到 active/next slice 的并行能力；
6. Next Slice 必要准备；
7. 未映射的横向基础设施。

同一类别按：

```text
explicit priority DESC
→ work_item_id ASC
```

禁止用 milestone 编号、PR 编号、文件新旧、讨论热度或 claim sequence 推断产品优先级。

当前 canonical selector 的下一产品 Work Item 必须是 `BETA-A-IMPLEMENTATION`。

## 7. Source Roles

| Source | Role | 可决定下一步？ |
|---|---|---:|
| `docs/program-delivery-ssot.yaml` | `AUTHORITATIVE_DELIVERY` | **是** |
| 本文件 | Human Companion | 否 |
| `docs/github-development-ssot.*` | Process / Safety | 否 |
| Autonomous Mandate | Standing Authority | 否 |
| `docs/implementation-status.md` | `GENERATED_VIEW` | 否 |
| `docs/agent-os-roadmap.yaml` | `REFERENCE_ARCHITECTURE` | 否 |
| `docs/agent-os-evolution-roadmap.md` | Research / Architecture Reference | 否 |
| `docs/product-work-map.yaml` | Superseded / Compatibility View | 否 |
| `docs/test-agent-runtime-beta-roadmap.yaml` | Approved Product Slice Input | 否 |
| `.agent/relay/work-claims.json` | Operational Execution State | 否 |

## 8. Relay 状态

`Pytest GitHub Relay` **继续保持禁用**。Program Delivery 与 BETA-A SPEC 的完成只满足 Relay 恢复门禁中的一部分，不自动恢复定时任务。恢复仍要求 claims/integration queue 按当前 GitHub 事实 reconcile，并完成独立 bounded acceptance；Relay enablement 必须单独 fail-closed 审核。

**SPEC merge、BETA-A implementation merge 或本次 closure 都不等于 Relay 可以恢复。**

## 9. 变更规则

产品策略、slice dependency、critical path 或 selection policy 的语义变化必须通过 Goal / Change Event / SPEC 和 Review 进入 `main`。不能靠聊天、PR 描述、claim checkpoint 或旧 roadmap 静默改变。

若本文件与 YAML 不一致，以 YAML 为准并让 consistency CI 失败，直到重新同步。
