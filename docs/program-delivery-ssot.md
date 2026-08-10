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
Program State: CONTROL_MIGRATION
Active Slice: BETA-A
Current Focus: PROGRAM-DELIVERY-SSOT-IMPLEMENTATION
Next Slice After Active: BETA-B
Scheduled Relay: DISABLED_GOVERNANCE_MIGRATION
```

Beta 垂直架构已经合入 `main`。当前先完成统一推进控制面的迁移，保证后续所有 Agent / Relay 对“下一步”的计算一致；该迁移闭环后，产品关键路径进入 `BETA-A-SPEC → BETA-A-IMPLEMENTATION → BETA-A-ACCEPTANCE`。

## 2. 三个问题，三个事实面

| 问题 | 事实面 | 含义 |
|---|---|---|
| **MAY_DO** | Authorization | Policy / Oracle / Permission / Owner Authority / Mandate / Goal / SPEC 决定是否有权做 |
| **SHOULD_DO_NEXT** | Program Delivery | `docs/program-delivery-ssot.yaml` 唯一决定产品当前/下一步 |
| **WHO_DOES_IT** | Claim Registry | 只决定谁持有 Work Item、分支/PR fencing、heartbeat、expiry 和 integration queue |

Program Delivery 不能扩大授权；Claim Registry 不能创造产品优先级或完成状态。

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

当前 `BETA-A = PREPARING`。BETA-B～E 仍由 slice dependency 阻塞。

## 4. 能力泳道，而不是产品串行里程碑

- **M1 Memory**：主要服务 BETA-D；当前 M1C closure 可并行推进，但不是 BETA-A 产品关键路径。
- **M2 Model Generalization**：服务 BETA-B/C/E。
- **M3 Project Generalization**：服务 BETA-E。
- **M4 Bounded Orchestration**：只在 BETA-B/C 确有需要时进入。
- **M5 Durable Runtime**：直接服务 BETA-A/D，因此不再要求等 M1→M4 全部横向做完。
- **M6 Integrated Beta**：通过 BETA-E 最终验收。
- **UX FP/FN Assurance**：服务 BETA-C/E，可作为并行质量泳道。

能力模块只有在明确解除 active/next slice blocker 时，才能成为产品 Critical Path。

## 5. 当前关键路径

```text
PROGRAM-DELIVERY-SSOT-IMPLEMENTATION
→ BETA-A-SPEC
→ BETA-A-IMPLEMENTATION
→ BETA-A-ACCEPTANCE
```

当前并行泳道：

- PR #85：M1C migration evidence closure → BETA-D 支撑；
- PR #63：UX FP/FN SPEC → BETA-C/E 支撑。

旧 PR #89 只修复旧 `product-work-map` 的状态，不再代表目标控制模型。

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

`Pytest GitHub Relay` 必须继续保持禁用，直到：

- Program Delivery 实现进入 main；
- main Full Quality / Secret Scan / CodeQL 全绿；
- source consistency 与 deterministic selector 证明全绿；
- claims / integration queue 已按当前 GitHub 事实重新 reconcile；
- Program selector 在治理迁移关闭后的状态下唯一选择 `BETA-A-SPEC`；
- Relay prompt 已迁移到 Program Delivery SSOT；
- bounded acceptance run 通过。

**SPEC merge 或 implementation merge 本身都不等于 Relay 可以恢复。**

## 9. 变更规则

产品策略、slice dependency、critical path 或 selection policy 的语义变化必须通过 Goal / Change Event / SPEC 和 Review 进入 `main`。不能靠聊天、PR 描述、claim checkpoint 或旧 roadmap 静默改变。

若本文件与 YAML 不一致，以 YAML 为准并让 consistency CI 失败，直到重新同步。