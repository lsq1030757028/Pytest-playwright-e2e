# AI Test Harness / Test Agent Runtime 实现状态

> Source Role: `GENERATED_VIEW`  
> Delivery Selection Authoritative: `false`  
> Canonical Delivery SSOT: `docs/program-delivery-ssot.yaml`  
> 最近同步：2026-08-11  
> 当前产品：`TEST_AGENT_RUNTIME_BETA`  
> Program State：`BETA_A_IMPLEMENTATION`  
> Active Product Slice：`BETA-A`  
> 当前 Focus：`BETA-A-IMPLEMENTATION`  
> Scheduled Relay：`DISABLED_GOVERNANCE_MIGRATION`

本文件只用于人类快速阅读当前状态。它不得独立决定下一步、Work Item priority、Product Slice 或 Relay claim。若本文件与 `docs/program-delivery-ssot.yaml` 不一致，以 Program Delivery SSOT 为准。

---

## 1. 当前业务结论

当前目标仍是交付真正可运行的 `TEST_AGENT_RUNTIME_BETA`：

```text
BETA-A  Existing governed test pack → durable job → execute → evidence → verdict
→ BETA-B  Requirement → generated/reviewable test → execute
→ BETA-C  Diagnose → bounded test-workflow repair → re-run
→ BETA-D  Restart → durable state + governed Memory → resume
→ BETA-E  Two materially different projects → Beta acceptance
```

Beta 架构、Program Delivery 迁移均已完成。BETA-A 独立 Goal #95 已建立，`SPEC-BETA-A-DURABLE-GOVERNED-PACK@0.1.0` 已通过 PR #96 合入 `main`，并完成 dedicated SPEC、Full Quality、Secret Scan、CodeQL、Release 与 Cleanup 的主干验证。

当前关键路径已经切换为：

```text
BETA-A-IMPLEMENTATION
→ BETA-A-ACCEPTANCE
```

---

## 2. 当前关键路径

| Work Item | 状态 | 产品作用 |
|---|---|---|
| `PROGRAM-DELIVERY-SSOT-IMPLEMENTATION` | `CLOSED` | 单一 delivery truth / selector / Relay source 迁移已闭环 |
| `BETA-A-SPEC` | `CLOSED` | Goal #95 / PR #96 已定义 durable governed-pack implementation contract |
| `BETA-A-IMPLEMENTATION` | `READY` | 当前唯一产品下一步：实现 durable CLI job + existing governed pack execution + evidence-backed verdict |
| `BETA-A-ACCEPTANCE` | `BLOCKED` | 等实现完成后做 package/container/replay/main-release 证明并关闭 BETA-A |

这些状态来自 `docs/program-delivery-ssot.yaml`。

---

## 3. BETA-A 已批准实施边界

本阶段只实现首个真实可运行 vertical slice：

- `test-agent job submit/status/result/events/cancel`；
- pinned project + immutable governed Pytest/Playwright pack；
- SQLite WAL durable job/event/attempt/lease state；
- exact required-node collection；
- 一个 job 最多一次 execution launch，automatic retry = `0`；
- durable `command_started` + lease/revision fencing；
- control-process restart 后安全 reconcile，不自动重跑 uncertain launched execution；
- SHA-256 content-addressed evidence；
- deterministic verifier-owned final verdict；
- process-tree cancellation + cleanup truth；
- package/container smoke、replay、critical mutation proof、UX3 journey evidence。

明确不包含 test generation、diagnosis/repair、governed Memory reuse、two-project acceptance、product-source repair/write、生产/个人数据、private-repo Secret acquisition 或 Scheduled Relay re-enable。

---

## 4. 并行能力泳道

M1 Memory 主要服务 BETA-D；PR #85 的 M1C closure 可并行推进，但不是 BETA-A 实施前置。PR #63 的 UX FP/FN assurance 主要服务 BETA-C/E，也不替代当前 BETA-A 路径。

M2/M3/M4/M5/M6 是映射到产品 Slice 的能力泳道，不是强制横向串行顺序。当前 M5 Durable Runtime 直接服务 BETA-A，因此进入 active implementation lane。

---

## 5. Delivery / Authority / Ownership

```text
MAY_DO          → Development SSOT + Owner Authority + Mandate + Goal + SPEC
SHOULD_DO_NEXT  → docs/program-delivery-ssot.yaml
WHO_DOES_IT     → control-branch Claim Registry / Integration Lease
```

BETA-A 实施使用 #65/#66 的显式 owner scope extension、Goal #95 与已批准的 `SPEC-BETA-A-DURABLE-GOVERNED-PACK@0.1.0`。`MANDATE-AUTONOMY-M1-M3@1.0.0` 没有被扩大。

---

## 6. Relay 状态

`Pytest GitHub Relay` 仍保持禁用。Program Delivery、BETA-A SPEC 或 BETA-A 实施本身都不会自动恢复 Scheduled Relay。恢复仍要求 claims/integration queue reconcile、selector agreement、bounded Relay acceptance 以及全部安全/质量门禁通过。

---

## 7. 下一动作

当前 canonical Program Delivery 的唯一产品下一步是：

```text
BETA-A-IMPLEMENTATION = READY
```

下一阶段必须严格在 `SPEC-BETA-A-DURABLE-GOVERNED-PACK@0.1.0` 边界内实现，不得把 BETA-B/C/D/E 的能力提前混入，也不得放宽 Oracle / Policy / Permission / product-source / sandbox / evidence / cancellation 约束。

---

## 8. 历史兼容快照（仅供旧证据测试，不代表当前状态）

以下文本保留 2026-08-05 旧状态页的历史标签。**这些行均为 `LEGACY_SNAPSHOT_NON_AUTHORITATIVE`，不能被新的 selector 读取。**

```text
M0 Harness Baseline：MERGED
M1.0 Memory Benchmark Harness：MERGED / CLOSED
M1A Memory Contracts & Namespaces SPEC：MERGED / CLOSED
M1A Runtime Contracts：MERGED / CLOSED
M1B Store & Progressive Retrieval：NEXT / SPEC
UX0 Synthetic User Runtime：MERGED / CLOSED
TodoMVC UX Mutation Proof SPEC：MERGED / CLOSED
UX Mutation Proof Runner：MERGED / CLOSED
Five-mutation Campaign：5 / 5 KILLED
UX False-positive / False-negative Benchmark：NEXT / SPEC
UX Gate Mode：SHADOW / NONBLOCKING
Human UAT：REQUIRED
M1 Memory Gate：0 / 1
Stage Delivery：NOT_READY
```

任何当前交付决策必须检查 `docs/program-delivery-ssot.yaml`。
