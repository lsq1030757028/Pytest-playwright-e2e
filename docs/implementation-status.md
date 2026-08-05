# AI Test Harness / Test Agent OS 实现状态

> 文档角色：项目状态单一事实源  
> 最近更新：2026-08-05  
> 当前状态：`FOUNDATION_BASELINE`  
> 阶段产品交付：`NOT_READY`  
> 当前里程碑：`M1 MEMORY_AND_CONTROLLED_EVOLUTION`  
> 已关闭模块：`M1.0 MEMORY_BENCHMARK_AND_THREAT_MODEL`  
> 当前主模块：`M1A MEMORY_CONTRACTS_AND_NAMESPACES`  
> 当前主模块阶段：`SPEC_DRAFT_NEXT`  
> 并行跨切面：`UX0 Synthetic User & Experience Acceptance Plane`  
> UX0 阶段：`SPEC_DRAFT / RUNTIME_NOT_IMPLEMENTED`  
> UX Gate：`SHADOW_ONLY_WHEN_IMPLEMENTED`  
> Human UAT：`REQUIRED`  
> M1.0 SPEC：`SPEC-M1.0-MEMORY-BENCHMARK@1.0.0`  
> UX0 SPEC：`SPEC-UX0-SYNTHETIC-USER@1.0.0 CANDIDATE`  
> 当前自治授权：`MANDATE-AUTONOMY-M1-M3@1.0.0 ACTIVE`

---

## 1. 状态结论

M1.0 Memory Benchmark Harness 已完成 SPEC、实现、测试设计、对抗资产、PR Review、主干合并、发布验证、证据归档和分支清理，状态为 `MERGED / CLOSED`。

M1A 仍是当前主模块。UX0 Synthetic User 是用户批准的新跨切面质量能力，当前只进入 SPEC 阶段，不声称 Runtime、TodoMVC UX Proof 或 Blocking Gate 已存在。

```text
M0 Harness Baseline：MERGED
M1.0 SPEC：MERGED / CLOSED
Autonomous Mandate：ACTIVE
M1.0 Benchmark Harness：MERGED / CLOSED
M1A Memory Contracts & Namespaces：SPEC_DRAFT_NEXT
UX0 Synthetic User SPEC：SPEC_DRAFT
Synthetic User Runtime：NOT_IMPLEMENTED
UX Gate Mode：SHADOW_ONLY_WHEN_IMPLEMENTED
Human UAT：REQUIRED
M1 Memory Gate：0 / 1
Stage Delivery：NOT_READY
```

M1.0 证明 Benchmark Harness 能够测量 Memory 价值、阻断安全退化并独立重放证据。它不实现生产 Memory Store，也不关闭完整 M1 Memory Gate。

UX0 的目标是通过真实 Playwright Journey、确定性体验证据和受限 AI Candidate Finding，提前暴露 UAT 风险。它不替代 Human UAT，也不允许 AI 主观评价直接阻断发布。

---

## 2. 当前推进链

```mermaid
flowchart LR
    A[✅ M0 Harness Baseline]
    --> B[✅ M1.0 SPEC]
    --> C[✅ Autonomous Mandate]
    --> D[✅ M1.0 Benchmark Harness<br/>MERGED / CLOSED]
    --> E[🟡 M1A Memory Contracts<br/>SPEC DRAFT]
    --> F[⬜ M1B Store / Retrieval]
    --> G[⬜ M1C Formation]
    --> H[⬜ M1D Shared Governance]
    --> I[⬜ M1E Controlled Evolution]
    --> J[⬜ M1F Memory Gate]

    D --> U1[🟡 UX0 Synthetic User<br/>SPEC DRAFT]
    U1 --> U2[⬜ Shadow Contracts / Runner]
    U2 --> U3[⬜ TodoMVC UX Mutation Proof]
    U3 --> U4[⬜ Advisory Gate]
    U4 --> U5[⬜ Blocking Policy Candidate]
```

---

## 3. M1.0 已交付能力

```text
Versioned Campaign Plan
→ Typed Scenario / Fixture Loader
→ Namespace / ACL / Validity / Integrity / Budget Filtering
→ Actor Context without Evaluator-only Fields
→ Deterministic Reference Actor
→ Hidden Evaluator
→ Run Evidence
→ Paired Metrics
→ Safety-first Verdict
→ Artifact Manifest
→ Independent Replay
```

已交付：

- `MEM-S001`—`MEM-S016` 的强类型场景和可执行 Fixture；
- Memory Off、Candidate、Verified 和 Adversarial 条件；
- Requirement、Code SHA、Fixture、Provider、Capability、Tool、Environment、Seed、Budget 和 Evaluator Pin；
- Stale、Conflict、Poisoning、Cross-project、ACL、Authority、Oracle / Holdout Contamination、Rollback、Revoke、Budget Flood、Tamper 和 Concurrent Revision 场景；
- evaluator-only 字段隔离；
- JSON / Markdown 报告、Artifact Manifest 和 Replay Manifest；
- `test-workflow memory validate | run | replay`；
- 非 PASS Verdict 返回非零退出码。

---

## 4. 权威验证与发布事实

### PR 证据

```text
Focused Unit / Contract：9 / 9 PASS
Boundary Integration：2 / 2 PASS
Canonical Campaign：16 场景 / 60 次运行 / PASS
Independent Replay：PASS
PR Evidence Run：30978317793
Final PR Regression：30978729480
```

### 安全摘要

```text
Failed Runs：0
Blocked Runs：0
Invalid Runs：0
Critical False Green：0
Unauthorized Scope Read：0
Unauthorized Memory Write：0
Assumption → Authority：0
Detected Contamination：12
Value Gate：PASS
Closes full M1 Memory Gate：false
```

### 主干与发布

```text
Merge Commit：0038a741a130add9432f8dc2dbc626a1ba1e0a00
Final Ledger Commit：89e0ab38b895dfceb604089ef3cc729ac8d17220
Main Quality：Run #99 / 30979625315 — SUCCESS
Release：Run #10 / 30979625302 — SUCCESS
Cleanup：Run #8 — SUCCESS
Python Artifact：8919608767
GHCR main / sha-89e0ab3
```

### Benchmark 证据摘要

```text
GitHub Evidence Artifact：8919174436
Evidence ZIP Digest：sha256:4942f98a3f40996f6c5f8b7e888954137e4f1b90267051c301db9fa8e559de5f
Semantic Digest：sha256:001fd1b17d903983a0dae4fd6b7b3c9f492fa663a45d0073c6d1c3b761af254b
Artifact Manifest Digest：sha256:8a76a5ae95e5dd1c58d6cc7fb9c5c157fe13de552d8622e708c37f9c417f985a
```

---

## 5. M1.0 测试与资产

- `src/test_workflow/memory_benchmark/`；
- `benchmarks/memory/m1.0/scenario-catalog.yaml`；
- `benchmarks/memory/m1.0/fixture-catalog.yaml`；
- `benchmarks/memory/m1.0/campaign.yaml`；
- `tests/unit/test_memory_benchmark.py`；
- `tests/integration/test_memory_benchmark_harness_integration.py`；
- `docs/testing/m1.0-memory-benchmark-harness-test-design.md`；
- GitHub Actions Evidence Artifact `8919174436`。

完整 CI 是仓库回归保护，M1.0 专属 Gate 负责证明本模块的契约、隐藏评估、对抗场景和 Replay 边界。

---

## 6. UX0 Synthetic User 当前设计

```text
Experience Oracle
→ Synthetic User Profile
→ ExperienceEnvironment
→ Real Playwright Journey
→ Deterministic Interaction / Accessibility / Recovery Evidence
→ AI Candidate Findings
→ Evidence Adjudication
→ UAT Readiness Report
```

当前已定义的 SPEC 资产：

- `docs/specs/ux0-synthetic-user-agent-spec.md`；
- `docs/specs/ux0-synthetic-user-agent.yaml`；
- `docs/ux-assurance-ssot.md`；
- `docs/ux-assurance-ssot.yaml`；
- `docs/testing/ux0-synthetic-user-agent-test-design.md`；
- `tests/assets/ux/ux0/canonical-contracts.yaml`；
- `tests/unit/test_ux0_synthetic_user_spec.py`。

关键边界：

- Persona 是行为能力模型，不推断敏感人口属性；
- Agent 必须执行真实 Playwright Interaction；
- Experience Oracle 对 Actor 隐藏；
- AI Finding 永远先是 Candidate；
- Blocker 必须绑定 Oracle Clause 和 E3/E4 证据；
- 初始 Runtime 只能 SHADOW；
- Human UAT 不被替代。

当前未实现：

- SyntheticUserAgent Runtime；
- UX Capability Adapters；
- TodoMVC UX Mutation Proof；
- False-positive / False-negative Benchmark；
- Advisory 或 Blocking Release Gate。

---

## 7. 当前自治边界

`MANDATE-AUTONOMY-M1-M3@1.0.0` 覆盖 M1—M3 内的 DEV0—DEV3 Goal、SPEC、实现、测试、Benchmark、Review、Merge、Release、Ledger 和 Cleanup。

仍不覆盖：

- M1—M3 外范围扩张；
- 真实生产数据、个人数据和 Secret；
- 破坏性生产迁移和不可逆外部写；
- 实质性不可逆费用；
- 无受控 Device SPEC 的危险真实设备动作；
- 更高权威、Oracle、Experience Oracle、Policy 或 Permission 冲突；
- DEV-E 生产动作；
- 绕过失败的 CI、Evidence、Review 或 Release Gate。

Synthetic User 额外禁止：

- 真实客户账号；
- 敏感人口属性和生物识别推断；
- 无限制网页探索；
- AI-only Blocker；
- 自动替代 Human UAT。

---

## 8. 当前主模块：M1A Memory Contracts & Namespaces

M1A 先进入独立 SPEC 阶段，定义：

- Working、Semantic、Episodic、Procedural 和 Skill Memory 类型；
- Memory ID、Revision、Content Hash、Provenance、Confidence、TTL 和 Validity；
- Candidate、Verified、Promoted、Superseded、Revoked 和 Expired 生命周期；
- Organization、Project、Campaign、Agent 等 Namespace 隔离；
- ACL、Owner、Reader、Writer、Promoter 和 Revoker 权限；
- Compare-and-swap、冲突检测和版本历史；
- Candidate 不得自动成为 Fact、Oracle、Policy 或 Permission；
- M1B Store / Retrieval 的厂商无关接口边界。

M1A SPEC 不选择数据库、向量检索、Embedding Model 或长期存储供应商。

---

## 9. UX0 下一状态

```text
SPEC_DRAFT
→ SPEC_IN_REVIEW
→ SPEC_APPROVED / MERGED
→ Shadow Contracts & Runner Goal
→ TodoMVC UX Mutation Proof
→ False-positive / False-negative Benchmark
→ Advisory Gate Candidate
```

在 Benchmark 和版本化 Policy Promotion 前，Blocking Gate 必须保持关闭。

---

## 10. 阶段交付条件

项目只有在以下全部通过后，才从 `FOUNDATION_BASELINE` 晋升为 `TEST_AGENT_RUNTIME_BETA`：

```text
M1 Memory Gate：PASS
M2 Model Generalization Gate：PASS
M3 Project / Architecture Gate：PASS
Global Safety Gate：PASS
```

全局指标继续要求：Critical False Green 0、未授权 Oracle / Experience Oracle / Policy / Permission 修改 0、Out-of-Mandate 动作执行 0、关键 Evidence 可重放率 100%、Memory / Model / Device / UX Asset 全部可追溯、所有自动晋升资产可回滚。
