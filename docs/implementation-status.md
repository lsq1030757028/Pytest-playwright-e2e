# AI Test Harness / Test Agent Runtime 实现状态

> Source Role: `GENERATED_VIEW`  
> Delivery Selection Authoritative: `false`  
> Canonical Delivery SSOT: `docs/program-delivery-ssot.yaml`  
> 最近同步：2026-08-13  
> 当前产品：`TEST_AGENT_RUNTIME_BETA`  
> Program State：`BETA_A_ACCEPTANCE`  
> Active Product Slice：`BETA-A`  
> 当前 Focus：`BETA-A-ACCEPTANCE`  
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

BETA-A 实现已合入：PR #98 的 merge commit 为 `2c980826044d1bdafece52d0ad1918aaa04b06d8`。该精确 main 提交上的 BETA-A Runtime、Full Quality、Secret Scan、CodeQL 与 Release 均已通过，因此实现阶段已满足关闭条件。

当前关键路径：

```text
BETA-A-ACCEPTANCE
```

---

## 2. 当前关键路径

| Work Item | 状态 | 产品作用 |
|---|---|---|
| `PROGRAM-DELIVERY-SSOT-IMPLEMENTATION` | `CLOSED` | 单一 delivery truth / selector / Relay source 迁移已闭环 |
| `BETA-A-SPEC` | `CLOSED` | Goal #95 / PR #96 定义 durable governed-pack contract |
| `BETA-A-IMPLEMENTATION` | `CLOSED` | PR #98 已在 main 交付 durable CLI job、真实 governed-pack execution 与 evidence-backed verdict |
| `BETA-A-ACCEPTANCE` | `READY` | 当前唯一产品下一步：用独立 operating evidence 证明 package / Docker / replay / mutation / UX3 / main-release 真值 |

这些状态来自 `docs/program-delivery-ssot.yaml`。

---

## 3. BETA-A 已实现能力

已合入的 vertical slice 包含：

- `test-agent job submit/status/result/events/cancel`；
- pinned project + immutable governed Pytest/Playwright pack；
- SQLite WAL durable job/event/attempt/lease state；
- exact required-node collection，missing/skip/xfail/deselect 不能成功；
- 一个 job 最多一次真实 execution launch，automatic retry = `0`；
- durable `command_started` + lease/revision fencing；
- uncertain launched execution 在 restart 后禁止自动重跑；
- 完整 durable evidence 可 deterministic reverify/finalize；
- SHA-256 content-addressed evidence；
- deterministic verifier-owned final verdict；
- Docker-only strong sandbox；
- process-tree cancellation + cleanup truth；
- clean wheel install、packaged CLI、restart/replay、critical mutation proof、UX3 3 persona × 3 repetitions。

明确不包含 BETA-B test generation、BETA-C repair、BETA-D governed Memory/full active resume、BETA-E two-project acceptance、product-source repair/write 或 Scheduled Relay re-enable。

---

## 4. Acceptance 要证明什么

`BETA-A-ACCEPTANCE` 不继续扩功能，而是对已合入能力做独立 operating proof：

- 绑定 PR #98 merge commit 与主干 gate 运行事实；
- 独立重跑真实 Docker / Chromium / cancellation；
- 独立重跑 package / CLI / restart / replay；
- 证明 critical false green = `0`、uncertain auto-reexecution = `0`；
- 证明 durable artifacts/hash/bindings 可复核；
- 缺失或篡改证据必须 fail closed。

Acceptance 通过并完成 main 验证后，才允许关闭 BETA-A 并准备 BETA-B SPEC。

---

## 5. Delivery / Authority / Ownership

```text
MAY_DO          → Development SSOT + Owner Authority + Mandate + Goal + SPEC
SHOULD_DO_NEXT  → docs/program-delivery-ssot.yaml
WHO_DOES_IT     → control-branch Claim Registry / Integration Lease
```

BETA-A 使用 #65/#66 的显式 owner scope extension、Goal #95 与 `SPEC-BETA-A-DURABLE-GOVERNED-PACK@0.1.0`。`MANDATE-AUTONOMY-M1-M3@1.0.0` 没有被扩大。

---

## 6. Relay 状态

`Pytest GitHub Relay` 仍保持禁用。BETA-A implementation 或 acceptance readiness 都不会自动恢复 Scheduled Relay；恢复仍要求 claims/integration queue reconcile、selector agreement、bounded Relay acceptance 以及全部安全/质量门禁通过。

---

## 7. 下一动作

当前 canonical Program Delivery 的唯一产品下一步是：

```text
BETA-A-ACCEPTANCE = READY
```

Acceptance 只收集并验证 operating evidence，不得把 BETA-B/C/D/E 的新能力提前混入，也不得放宽 Oracle / Policy / Permission / product-source / sandbox / evidence / cancellation 约束。

---

## 8. 历史兼容快照（仅供旧证据测试，不代表当前状态）

以下文本是 `LEGACY_SNAPSHOT_NON_AUTHORITATIVE`，不能被新的 selector 读取：

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
