# AI Test Harness / Test Agent Runtime 实现状态

> Source Role: `GENERATED_VIEW`  
> Delivery Selection Authoritative: `false`  
> Canonical Delivery SSOT: `docs/program-delivery-ssot.yaml`  
> 最近同步：2026-08-10  
> 当前产品：`TEST_AGENT_RUNTIME_BETA`  
> Program State：`PRE_BETA_A`  
> Active Product Slice：`BETA-A`  
> 当前 Focus：`BETA-A-SPEC`  
> Scheduled Relay：`DISABLED_GOVERNANCE_MIGRATION`

本文件只用于人类快速阅读当前状态。它不得独立决定下一步、Work Item priority、Product Slice 或 Relay claim。若本文件与 `docs/program-delivery-ssot.yaml` 不一致，以 Program Delivery SSOT 为准，并由 consistency gate 阻止静默漂移。

---

## 1. 当前业务结论

项目已经越过“只做 Pytest + Playwright 框架”的阶段，当前目标是交付一个真正可运行的 `TEST_AGENT_RUNTIME_BETA`。

已批准的产品主轴是：

```text
BETA-A  Existing governed test pack → durable job → execute → evidence → verdict
→ BETA-B  Requirement → generated/reviewable test → execute
→ BETA-C  Diagnose → bounded test-workflow repair → re-run
→ BETA-D  Restart → durable state + governed Memory → resume
→ BETA-E  Two materially different projects → Beta acceptance
```

Beta 产品/架构 SPEC 已通过 PR #87 合入 `main`。统一 Program Delivery 控制实现已通过 PR #93 合入并完成主干 Full Quality / Security / Consistency / Cleanup 验证。

因此控制迁移不再阻塞产品推进，当前关键路径正式进入：

```text
BETA-A-SPEC
→ BETA-A-IMPLEMENTATION
→ BETA-A-ACCEPTANCE
```

---

## 2. 当前关键路径

| Work Item | 状态 | 产品作用 |
|---|---|---|
| `PROGRAM-DELIVERY-SSOT-IMPLEMENTATION` | `CLOSED` | 单一 delivery truth / selector / Relay source 迁移已闭环 |
| `BETA-A-SPEC` | `READY` | 当前唯一产品下一步：定义首个 durable runtime slice |
| `BETA-A-IMPLEMENTATION` | `BLOCKED` | 等 BETA-A SPEC 批准后实现 durable CLI job + existing governed pack execution + evidence-backed verdict |
| `BETA-A-ACCEPTANCE` | `BLOCKED` | 等实现完成后做 package/container/replay/main-release 证明并关闭 BETA-A |

这里的状态和顺序来自 `docs/program-delivery-ssot.yaml`，不是本文件计算出来的。

---

## 3. 并行能力泳道

### M1 Memory

M1 Memory 现在是 BETA-D 的能力泳道，而不是阻塞 BETA-A 的全局串行前置。

已实现事实包括：

- M1A Governed Memory Runtime Contracts 已关闭；
- M1B durable SQLite Store、progressive retrieval、resilience/replay/migration 已实现并完成主线交付；
- M1C Hot Formation、Background Consolidation、poisoning/replay/concurrency gate 核心实现已合入；
- PR #85 正在收尾 M1C migration evidence，目标是迁移/切换/回滚时不丢 Formation、Consolidation、Replay 和 contamination 证据。

当前 Program Delivery 将 #85 视为并行能力 closure，主要支撑未来 BETA-D。

### UX False-positive / False-negative Assurance

PR #63 仍是并行 UX 质量泳道，主要服务 BETA-C / BETA-E。它不替代 Human UAT，也不阻塞当前 BETA-A。

### M2 / M3 / M4 / M5 / M6

- M2：跨模型 normalization / safe degradation / routing，主要服务 BETA-B/C/E；
- M3：项目/架构 adapter 泛化，主要服务 BETA-E；
- M4：只在 BETA-B/C 的实际 slice 需要时引入 bounded orchestration；
- M5：durable control plane / worker state / recovery，直接服务 BETA-A/D；
- M6：通过 BETA-E 做 integrated Beta acceptance。

这些编号不再天然代表产品执行顺序。

---

## 4. Delivery / Authority / Ownership 分工

```text
MAY_DO          → Development SSOT + Owner Authority + Mandate + Goal + SPEC
SHOULD_DO_NEXT  → docs/program-delivery-ssot.yaml
WHO_DOES_IT     → control-branch Claim Registry / Integration Lease
```

关键边界：

- Program Delivery 可以说明 M5/BETA-A 很重要，但不能把它自动纳入 M1–M3 mandate；
- Claim Registry 可以说明某 Work Item 已被谁持有，但不能把 BLOCKED 变 READY；
- 旧 status/roadmap/product-work-map 不能再作为 fallback selector；
- durable delivery sources 冲突时必须 `REPLAN_REQUIRED`。

---

## 5. 已交付基础能力摘要

### Harness Baseline

已具备需求/测试计划、Pytest、Playwright、真实浏览器、证据、诊断、回归、Replay、Mutation、Quality Gate、Python package / container 等基础能力。

### Governed Memory

当前已经具备：

- Namespace / ACL / lifecycle / provenance / immutable revision / CAS / idempotency；
- durable SQLite primary Store；
- authority-first Hot/Warm/Cold progressive retrieval；
- exact-ref recall、cursor binding、primary revalidation；
- index drift detection/rebuild、Outbox recovery、fail-closed outage；
- migration/rollback manifest verification；
- Hot Formation / Background Consolidation；
- parent dependency fencing、contamination propagation、tamper/replay detection。

这些能力是产品子系统，不再被单独视为最终交付终点。

---

## 6. Program Delivery 迁移结果

Goal #91 / `SPEC-PROGRAM-DELIVERY-SSOT@1.0.0` 已批准，SPEC PR #92 与实现 PR #93 均已进入主干。

迁移已经完成以下职责重构：

- `docs/program-delivery-ssot.yaml` 成为唯一 `SHOULD_DO_NEXT` 机器事实源；
- deterministic selector / validator 与 mutation proof 已落地；
- AGENTS / Development SSOT 已迁移到 Program Delivery；
- Parallel Claims 只回答 `WHO_DOES_IT`；
- Hourly Relay prompt 只消费 Program Delivery 的产品顺序；
- 旧 status / roadmap / product-work-map 已降权；
- main Full Quality、Secret Scan、CodeQL、Program consistency、Parallel Claims、UX mutation 与 Cleanup 验证已通过。

`PROGRAM-DELIVERY-SSOT-IMPLEMENTATION = CLOSED`，`BETA-A-SPEC = READY`。

---

## 7. Relay 恢复条件

`Pytest GitHub Relay` 仍保持禁用。迁移完成不等于自动恢复。

只有以下剩余门禁全部满足后，Scheduled Relay 才允许单独进入 re-enable 动作：

```text
main Full Quality green
+ Secret Scan / CodeQL green
+ source consistency green
+ deterministic selector proof green
+ current claims / integration queue reconciled
+ post-migration selector resolves BETA-A-SPEC
+ Relay prompt uses Program Delivery
+ bounded acceptance run green
```

**本次 migration closure 不启用 Relay。**

---

## 8. 产品完成条件

`TEST_AGENT_RUNTIME_BETA` 只有在产品 Slice 的真实 operating evidence 完成后才能关闭，包括：

- 一个真实 submission/status/result/cancel 入口；
- durable restart recovery；
- plan → test generation → execution → diagnosis → bounded repair/re-run → verdict；
- 直接 Evidence references；
- 至少两个 materially different projects；
- seeded product defect 被检测，healthy control 不误报；
- Critical False Green = `0`；
- release/deployment smoke、文档和 Human UAT 完成。

更大的六项目/多设备矩阵仍可作为后续泛化和生产成熟度目标，但不再被本状态页解释为 BETA-A 的前置条件。

---

## 9. 下一动作

当前 canonical Program Delivery 的唯一产品下一步是：

```text
BETA-A-SPEC = READY
```

下一阶段必须继续遵守 SPEC-first：先建立并批准 BETA-A 的 durable runtime 实现契约、测试设计和威胁模型，再进入 Runtime Implementation。

---

## 10. 历史兼容快照（仅供旧证据测试，不代表当前状态）

以下文本保留 2026-08-05 旧状态页的历史标签，使已发布 SPEC / Replay / CI 仍可验证它们当时所绑定的 delivery snapshot。**这些行均为 `LEGACY_SNAPSHOT_NON_AUTHORITATIVE`，不能被新的 selector 读取。**

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

旧测试若需要证明“某历史 SPEC 当时看到的状态”，可以检查该兼容快照；任何当前交付决策必须检查 `docs/program-delivery-ssot.yaml`。