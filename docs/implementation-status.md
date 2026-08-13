# AI Test Harness / Test Agent Runtime 实现状态

> Source Role: `GENERATED_VIEW`  
> Delivery Selection Authoritative: `false`  
> Canonical Delivery SSOT: `docs/program-delivery-ssot.yaml`  
> 最近同步：2026-08-13  
> 当前产品：`TEST_AGENT_RUNTIME_BETA`  
> Program State：`PRE_BETA_B`  
> Active Product Slice：`BETA-B`  
> 当前 Focus：`BETA-B-SPEC`  
> Scheduled Relay：`DISABLED_GOVERNANCE_MIGRATION`

本文件只用于人类快速阅读当前状态。它不得独立决定下一步、Work Item priority、Product Slice 或 Relay claim。若本文件与 `docs/program-delivery-ssot.yaml` 不一致，以 Program Delivery SSOT 为准。

---

## 1. 当前业务结论

产品主轴仍是：

```text
BETA-A  Existing governed pack → durable job → evidence-backed verdict  [CLOSED]
→ BETA-B  Requirement → generated/reviewable test-only patch → execute  [SPEC NEXT]
→ BETA-C  Diagnose → bounded test-workflow repair → re-run
→ BETA-D  Restart → durable state + governed Memory → resume
→ BETA-E  Two materially different projects → Beta acceptance
```

BETA-A 已完成实现、implementation closure 与独立 operating acceptance：

- Implementation PR #98 → main `2c980826...`，主干 BETA-A runtime / Full Quality / Secret / CodeQL / Release 全绿；
- Implementation closure PR #99 → main `77d54bd6...`，主干 Program Delivery / Full Quality / Secret / CodeQL / Release 全绿；
- Acceptance PR #100 → main `056d8819...`，主干 `beta-a-acceptance` / Full Quality / Secret / CodeQL / Release 全绿。

因此 BETA-A 可以正式 `CLOSED`。BETA-B Goal 已创建为 #101，当前只允许 SPEC-first 工作。

---

## 2. 当前关键路径

| Work Item | 状态 | 产品作用 |
|---|---|---|
| `BETA-A-SPEC` | `CLOSED` | PR #96，定义 durable governed-pack contract |
| `BETA-A-IMPLEMENTATION` | `CLOSED` | PR #98，交付 durable runtime |
| `BETA-A-ACCEPTANCE` | `CLOSED` | PR #100，独立证明历史真值、真实 Docker/Playwright、package/restart/replay 与 UX3 |
| `BETA-B-SPEC` | `READY` | Goal #101；当前唯一产品下一步 |
| `BETA-B-IMPLEMENTATION` | `BLOCKED` | BETA-B SPEC 合并并主干验证前禁止启动 |
| `BETA-B-ACCEPTANCE` | `BLOCKED` | implementation 完成并主干验证前禁止启动 |

---

## 3. BETA-A 形成的已验证产品基线

BETA-A 已验证能力包括：

- `test-agent job submit/status/result/events/cancel`；
- pinned project + immutable governed Pytest/Playwright pack；
- SQLite WAL durable job/event/attempt/lease state；
- exact required-node completeness，missing/skip/xfail/deselect 不能成功；
- automatic execution retry = `0`；
- durable command-start + lease/revision fencing；
- uncertain launched execution restart 后不得自动重跑；
- durable evidence 可 deterministic reverify/finalize；
- SHA-256 CAS evidence + deterministic verdict authority；
- Docker-only strong sandbox、read-only product source、network deny、host secret/socket isolation；
- truthful process-tree cancellation/cleanup；
- clean wheel、control-plane container、packaged CLI、restart/replay；
- 10 个 critical mutation families、survivor = `0`；
- UX3：3 persona × 3 repetitions + adversarial recovery。

这套 BETA-A 基线将在 BETA-B 作为执行底座复用，而不是重建第二套 runtime。

---

## 4. BETA-B 下一步只做 SPEC

Goal #101 的业务目标是：

```text
requirement + provenance + pinned project/profile + authoritative Oracle
→ bounded deterministic generation
→ reviewable test-only patch artifact
→ validation
→ BETA-A durable execution
→ evidence-backed verdict
```

BETA-B SPEC 必须定义 requirement/provenance、Oracle、patch artifact、permitted test paths、product-source read-only、validation/handoff、evidence、budgets、mutation proof 与 UX3。硬约束包括 product source write = `0`、missing/stale Oracle success = `0`、unreviewable patch success = `0`、assertion weakening = `0`、fixed/blind retry = `0`。

在 SPEC 合并并 main-verified 以前，不得提交 generation runtime implementation。

---

## 5. Delivery / Authority / Ownership

```text
MAY_DO          → Development SSOT + Owner Authority + Mandate + Goal + SPEC
SHOULD_DO_NEXT  → docs/program-delivery-ssot.yaml
WHO_DOES_IT     → control-branch Claim Registry / Integration Lease
```

BETA-B 使用 #65/#66 的显式 owner scope extension和 Goal #101。`MANDATE-AUTONOMY-M1-M3@1.0.0` 没有被扩大。

---

## 6. Relay 状态

`Pytest GitHub Relay` 仍保持禁用。BETA-A 完成不会自动恢复 Scheduled Relay；恢复仍要求 claims/integration queue reconcile、selector agreement、独立 bounded Relay acceptance 以及全部安全/质量门禁通过。

---

## 7. 下一动作

当前 canonical Program Delivery 的唯一产品下一步是：

```text
BETA-B-SPEC = READY
```

只允许创建 BETA-B SPEC / threat model / independent test design / dedicated SPEC gate；禁止提前写 BETA-B generation runtime。

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
