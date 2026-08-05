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
> UX0 阶段：`SHADOW_RUNTIME_VERIFIED_MERGE_PENDING`  
> UX Gate：`SHADOW_NONBLOCKING`  
> Human UAT：`REQUIRED`  
> M1.0 SPEC：`SPEC-M1.0-MEMORY-BENCHMARK@1.0.0`  
> UX0 SPEC：`SPEC-UX0-SYNTHETIC-USER@1.0.0 MERGED`  
> 当前自治授权：`MANDATE-AUTONOMY-M1-M3@1.0.0 ACTIVE`

---

## 1. 状态结论

```text
M0 Harness Baseline：MERGED
M1.0 SPEC：MERGED / CLOSED
Autonomous Mandate：ACTIVE
M1.0 Benchmark Harness：MERGED / CLOSED
M1A Memory Contracts & Namespaces：SPEC_DRAFT_NEXT
UX0 Synthetic User SPEC：MERGED / CLOSED
Synthetic User Runtime：VERIFIED / MERGE_PENDING
UX Gate Mode：SHADOW / NONBLOCKING
Human UAT：REQUIRED
M1 Memory Gate：0 / 1
Stage Delivery：NOT_READY
```

M1.0 已证明 Memory Benchmark、威胁场景、证据和独立 Replay 基线；它不实现生产 Memory Store，也不关闭完整 M1 Memory Gate。

UX0 Synthetic User 已完成规范并形成可执行 Shadow Runtime 候选：四条真实 TodoMVC Journey、确定性体验裁决、Trace / Screenshot / Semantic Snapshot、AI Candidate Finding、Artifact Manifest 和独立 Replay均已通过专属 Gate。该能力尚未合并到 `main`，因此状态是 `VERIFIED / MERGE_PENDING`，不是 `MERGED`。

---

## 2. 当前推进链

```mermaid
flowchart LR
    A[✅ M0 Harness Baseline]
    --> B[✅ M1.0 Memory Benchmark]
    --> C[🟡 M1A Memory Contracts<br/>SPEC DRAFT]
    --> D[⬜ M1B Store / Retrieval]
    --> E[⬜ M1C Formation]
    --> F[⬜ M1D Shared Governance]
    --> G[⬜ M1E Controlled Evolution]
    --> H[⬜ M1F Memory Gate]

    B --> U1[✅ UX0 SPEC]
    U1 --> U2[🟡 Shadow Runtime<br/>VERIFIED / MERGE PENDING]
    U2 --> U3[⬜ TodoMVC UX Mutation Proof]
    U3 --> U4[⬜ False-positive / False-negative Benchmark]
    U4 --> U5[⬜ Advisory Gate Candidate]
    U5 --> U6[⬜ Blocking Policy Candidate]
```

Memory 仍是主里程碑；UX Assurance 是跨 M1—M3 的并行质量面，不抢占 M1A 的主执行指针。

---

## 3. 已关闭能力

### M0 Harness Baseline

已具备：

- Capability Contract；
- Registry 与不可变 Artifact Store；
- Policy、Permission 和 Budget；
- Dynamic Workflow Compiler / Orchestrator；
- Requirement Revision、Impact、Campaign 和 Valid Progress；
- Generation、Diagnosis、Regression 和 Verdict；
- Replay、Mutation Proof、Browser 和 Pinned Target；
- Python Package 与 GHCR 发布。

### M1.0 Memory Benchmark Harness

```text
Versioned Campaign Plan
→ Typed Scenario / Fixture
→ Namespace / ACL / Validity / Integrity Filtering
→ Actor Context without Evaluator-only Fields
→ Hidden Evaluator
→ Paired Metrics
→ Safety-first Verdict
→ Artifact Manifest
→ Independent Replay
```

权威事实：

```text
Implementation Commit：0038a741a130add9432f8dc2dbc626a1ba1e0a00
Final Ledger Commit：89e0ab38b895dfceb604089ef3cc729ac8d17220
Main Quality：Run #99 / 30979625315 — SUCCESS
Release：Run #10 / 30979625302 — SUCCESS
Scenarios：16
Runs：60
Critical False Green：0
Semantic Digest：sha256:001fd1b17d903983a0dae4fd6b7b3c9f492fa663a45d0073c6d1c3b761af254b
```

---

## 4. UX0 Synthetic User Shadow Runtime

### 4.1 执行模型

```text
Experience Oracle
→ Synthetic User Profile
→ ExperienceEnvironment
→ Pinned TodoMVC Target
→ Real Playwright Journey
→ Semantic State / Interaction Evidence
→ Deterministic UX Evaluation
→ Nonblocking AI Candidate Finding
→ UAT Report / Artifact Manifest / Replay
```

### 4.2 已实现

- 强类型 Profile、Environment、Oracle、Journey、Event、Metric、Finding 和 Report；
- Profile 仅描述行为能力，不推断敏感人口属性；
- Synthetic Fixture Only 和生产账号拒绝；
- Actor Input 与 evaluator-only 字段隔离；
- `test-workflow ux validate | run | replay`；
- 四条真实 Journey：Novice、Returning、Keyboard、Interrupted；
- 每条 Journey 独立 Browser Context；
- Semantic State Hash、Screenshot、Trace 和 Semantic Accessibility Snapshot；
- Rule-first Deterministic Evaluator；
- AI Finding 固定为非阻断 Candidate；
- JSON / Markdown 报告、Artifact Manifest 和 Replay Manifest；
- Artifact Tamper 和 Replay Drift 拒绝。

### 4.3 当前证据

```text
Focused Runtime Gate：Run #16 / 30991412463 — SUCCESS
Unit / Contract：9 / 9 PASS
CLI Validate：PASS
Real Playwright Journeys：4 / 4 PASS
Journey Checkpoints：14 / 14 PASS
Independent Replay：PASS
Campaign Verdict：PASS
Full Repository CI：Run #125 / 30991412405 — SUCCESS
```

```text
Artifact ID：8924285005
Artifact ZIP Digest：sha256:349f51fa11cca5c5f83bee863c69b289b19eebc63bfabe6c5623399b8254a3fc
Semantic Digest：sha256:1dda03adfcc3a264240b20a883daf2a230e3ce6dcd00c43dccfb84da40b885c5
Artifact Manifest Digest：sha256:702fdce96eedbb8b81566dda08768d33434346a7edf88653594587f676c92fa4
Manifest Files：19
```

### 4.4 尚未完成

- UX Mutation Proof；
- 缺失反馈、状态丢失、键盘障碍、恢复失败 Mutations；
- False-positive / False-negative Benchmark；
- 真实 LLM Provider 的跨模型诊断一致性；
- 跨项目、移动端、小程序和真实设备；
- Advisory / Blocking Gate。

当前 Runtime 只能 `SHADOW`，Release Effect 固定为 `NONBLOCKING_SHADOW`，Human UAT 保持 `REQUIRED`。

---

## 5. 当前主模块：M1A Memory Contracts & Namespaces

M1A 独立 SPEC 分支已形成候选，下一步进入 SPEC PR。范围包括：

- Working、Semantic、Episodic、Procedural、Skill Memory；
- Memory ID、Immutable Revision、Canonical Hash 和 Provenance；
- Organization、Project、Campaign、Agent、Shared Namespace；
- Principal、Role、ACL、Default Deny 和 Deny Override；
- Candidate、Verified、Promoted、Conflicting、Quarantined、Superseded、Revoked、Expired、Forgotten；
- Compare-and-swap、Conflict Artifact 和 Idempotency；
- M1B 的厂商无关 Store / Query Ports。

M1A SPEC 不选择数据库、向量库、Embedding Model 或 Ranking Algorithm。

---

## 6. 当前自治与安全边界

`MANDATE-AUTONOMY-M1-M3@1.0.0` 覆盖 M1—M3 范围内的 Goal、SPEC、实现、测试、Benchmark、Review、Merge、Release、Ledger 和 Cleanup。

仍不覆盖：

- M1—M3 外范围扩张；
- 真实生产数据、个人数据和 Secret；
- 破坏性生产迁移和不可逆外部写；
- 实质性不可逆费用；
- 无受控 Device SPEC 的危险设备动作；
- 更高权威、Oracle、Experience Oracle、Policy 或 Permission 冲突；
- DEV-E 生产动作；
- 绕过失败的 CI、Evidence、Review 或 Release Gate。

Synthetic User 额外禁止：

- 真实客户账号；
- 敏感属性和生物识别推断；
- 无限制网页探索；
- AI-only Blocker；
- 自动替代 Human UAT。

---

## 7. 近期执行顺序

```text
1. UX0 Shadow Runtime Final Review / Merge / Main / Release / Cleanup
2. M1A Memory Contracts SPEC PR / Merge
3. TodoMVC UX Mutation Proof SPEC
4. M1A Domain Contracts Implementation
5. UX False-positive / False-negative Benchmark
6. M1B Store & Progressive Retrieval
```

UX 与 Memory 可交错推进，但不能通过并行降低各自的 Evidence Gate。

---

## 8. 阶段交付条件

项目只有在以下全部通过后，才从 `FOUNDATION_BASELINE` 晋升为 `TEST_AGENT_RUNTIME_BETA`：

```text
M1 Memory Gate：PASS
M2 Model Generalization Gate：PASS
M3 Project / Architecture Gate：PASS
Global Safety Gate：PASS
```

全局要求继续是：Critical False Green 0、未授权 Oracle / Experience Oracle / Policy / Permission 修改 0、Out-of-Mandate 动作 0、关键 Evidence 可重放率 100%、Memory / Model / Device / UX Asset 可追溯、自动晋升资产可回滚。
