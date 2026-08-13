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
Program State: PRE_BETA_B
Active Slice: BETA-B
Current Focus: BETA-B-SPEC
Next Slice After Active: BETA-C
Scheduled Relay: DISABLED_GOVERNANCE_MIGRATION
```

BETA-A 已完成并通过独立 operating acceptance。Acceptance PR #100 合入 `main` 为 `056d8819e6b7da507c8f9ed1be3ab8fca77f046a`，该精确主干提交上的 `beta-a-acceptance`、Full Quality、Secret Scan、CodeQL、Release 均为 success。因此 BETA-A 可标记 `CLOSED`，下一产品工作转为 **BETA-B SPEC**。

BETA-B Goal 为 #101。它只授权 SPEC-first：在 BETA-B SPEC 合并并主干验证前，不得实现 generation runtime。

## 2. 三个问题，三个事实面

| 问题 | 事实面 | 含义 |
|---|---|---|
| **MAY_DO** | Authorization | Policy / Oracle / Permission / Owner Authority / Mandate / Goal / SPEC 决定是否有权做 |
| **SHOULD_DO_NEXT** | Program Delivery | `docs/program-delivery-ssot.yaml` 唯一决定产品当前/下一步 |
| **WHO_DOES_IT** | Claim Registry | 只决定谁持有 Work Item、分支/PR fencing、heartbeat、expiry 和 integration queue |

Program Delivery 不能扩大授权；Claim Registry 不能创造产品优先级或完成状态。BETA-B 使用 #65/#66 的 owner scope extension 与 Goal #101；`MANDATE-AUTONOMY-M1-M3@1.0.0` 本身没有被扩张。

## 3. 产品推进主轴

```text
BETA-A  existing governed pack → durable job → execute → evidence → verdict  [CLOSED]
  ↓
BETA-B  requirement → reviewable generated test-only patch → execute → verdict  [SPEC NEXT]
  ↓
BETA-C  diagnose → bounded test-workflow repair → rerun → verdict
  ↓
BETA-D  restart → durable state + governed Memory → resume
  ↓
BETA-E  two materially different projects → Beta acceptance
```

当前 `BETA-B = PREPARING`，BETA-C～E 仍受 slice dependency 阻塞。

## 4. 当前关键路径

```text
BETA-B-SPEC
→ BETA-B-IMPLEMENTATION
→ BETA-B-ACCEPTANCE
```

`BETA-A-SPEC = CLOSED`（PR #96）。  
`BETA-A-IMPLEMENTATION = CLOSED`（PR #98）。  
`BETA-A-ACCEPTANCE = CLOSED`（PR #100）。  
`BETA-B-SPEC = READY`（Goal #101）是 canonical selector 当前唯一应选择的产品 Work Item。  
`BETA-B-IMPLEMENTATION` 与 `BETA-B-ACCEPTANCE` 保持 `BLOCKED`。

并行能力泳道仍可存在，但不能因为 claim 顺序、PR 编号或 milestone 编号而取代 BETA-B SPEC 产品关键路径。

## 5. BETA-B SPEC 边界

BETA-B 的下一步仅定义合同，不写 generation runtime。SPEC 至少需要固定：

- requirement + provenance schema；
- pinned project/profile/commit；
- current authoritative Oracle；
- deterministic bounded generation；
- **test-only、reviewable patch artifact**；
- permitted test-path containment，product source write = `0`；
- validation before execution；
- BETA-A durable execution handoff；
- evidence/verdict binding；
- finite budgets、fixed/blind retry = `0`；
- threat model、independent test design、critical mutations、UX3。

BETA-B SPEC 不得包含 BETA-C repair、BETA-D governed Memory/full resume、BETA-E two-project acceptance，也不得启用 Scheduled Relay。

## 6. 下一工作选择规则

在授权、安全和 claim 冲突检查通过后，顺序固定为：

1. Security / correctness repair；
2. Active Slice blocker；
3. Active Slice closer；
4. Dependency-unblocking integration；
5. 映射到 active/next slice 的并行能力；
6. Next Slice 必要准备；
7. 未映射的横向基础设施。

同一类别按 `explicit priority DESC → work_item_id ASC`。禁止用 milestone 编号、PR 编号、文件新旧、讨论热度或 claim sequence 推断产品优先级。

当前 canonical selector 的下一产品 Work Item 必须是 `BETA-B-SPEC`。

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

`Pytest GitHub Relay` **继续保持禁用**。BETA-A 已完成也不会自动恢复 Relay；恢复仍要求 claims/integration queue reconcile、selector agreement 和独立 bounded Relay acceptance。`BETA-B-SPEC = READY` 不等于 Relay 可以恢复。

## 9. 变更规则

产品策略、slice dependency、critical path 或 selection policy 的语义变化必须通过 Goal / Change Event / SPEC 和 Review 进入 `main`。不能靠聊天、PR 描述、claim checkpoint 或旧 roadmap 静默改变。若本文件与 YAML 不一致，以 YAML 为准并让 consistency CI 失败，直到重新同步。
