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
Program State: BETA_A_ACCEPTANCE
Active Slice: BETA-A
Current Focus: BETA-A-ACCEPTANCE
Next Slice After Active: BETA-B
Scheduled Relay: DISABLED_GOVERNANCE_MIGRATION
```

BETA-A Implementation 已完成：PR #98 已合入 `main`，merge commit 为 `2c980826044d1bdafece52d0ad1918aaa04b06d8`。该精确主干提交上的 BETA-A Runtime、Full Quality、Secret Scan、CodeQL 与 Release 均已通过，因此 `BETA-A-IMPLEMENTATION = CLOSED`，产品关键路径只剩 `BETA-A-ACCEPTANCE`。

## 2. 三个问题，三个事实面

| 问题 | 事实面 | 含义 |
|---|---|---|
| **MAY_DO** | Authorization | Policy / Oracle / Permission / Owner Authority / Mandate / Goal / SPEC 决定是否有权做 |
| **SHOULD_DO_NEXT** | Program Delivery | `docs/program-delivery-ssot.yaml` 唯一决定产品当前/下一步 |
| **WHO_DOES_IT** | Claim Registry | 只决定谁持有 Work Item、分支/PR fencing、heartbeat、expiry 和 integration queue |

Program Delivery 不能扩大授权；Claim Registry 不能创造产品优先级或完成状态。BETA-A 使用 #65/#66 的 owner scope extension、Goal #95 与已批准 `SPEC-BETA-A-DURABLE-GOVERNED-PACK@0.1.0`；`MANDATE-AUTONOMY-M1-M3@1.0.0` 本身没有被扩张。

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

当前 `BETA-A = ACCEPTING`。BETA-B～E 仍受 slice dependency 阻塞。

## 4. 当前关键路径

```text
BETA-A-ACCEPTANCE
```

`PROGRAM-DELIVERY-SSOT-IMPLEMENTATION = CLOSED`。  
`BETA-A-SPEC = CLOSED`，对应 Goal #95 / PR #96。  
`BETA-A-IMPLEMENTATION = CLOSED`，对应 PR #98 / main `2c980826...`。  
`BETA-A-ACCEPTANCE = READY`，是当前 canonical selector 应唯一选择的产品 Work Item。

并行能力泳道仍可存在，但不能因为 claim 顺序、PR 编号或 milestone 编号而取代 BETA-A acceptance 产品关键路径。

## 5. BETA-A Acceptance 边界

Acceptance 不新增第二套 Runtime，也不扩大实施范围。它只证明已合入能力具备可重复、可审计的 operating evidence：

- 使用已打包 `test-agent` 入口，而不是源码树捷径；
- 重跑 existing governed Pytest/Playwright pack 的真实 Docker/Chromium 证据；
- 验证 durable state、restart、replay、artifact hash 与 deterministic verdict 一致；
- 验证真实 cancellation/process cleanup；
- 重跑 critical mutation 与 UX3 journey 证明；
- 绑定实现 merge commit 与主干质量/安全/Release 运行事实；
- 任何缺失、篡改、uncertain execution 或 cleanup 不可信都不得产生成功。

Acceptance 不做 BETA-B test generation、BETA-C repair、BETA-D governed Memory/full resume、BETA-E two-project acceptance，也不恢复 Scheduled Relay。

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

当前 canonical selector 的下一产品 Work Item 必须是 `BETA-A-ACCEPTANCE`。

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

`Pytest GitHub Relay` **继续保持禁用**。BETA-A implementation 的完成只满足 Relay 恢复门禁中的一部分；恢复仍要求 claims/integration queue 按当前 GitHub 事实 reconcile，并完成独立 bounded Relay acceptance。`BETA-A-ACCEPTANCE = READY` 不等于 Relay 可以恢复。

## 9. 变更规则

产品策略、slice dependency、critical path 或 selection policy 的语义变化必须通过 Goal / Change Event / SPEC 和 Review 进入 `main`。不能靠聊天、PR 描述、claim checkpoint 或旧 roadmap 静默改变。若本文件与 YAML 不一致，以 YAML 为准并让 consistency CI 失败，直到重新同步。
