# AI Test Harness / Test Agent OS 实现状态

> 文档角色：项目状态单一事实源  
> 最近更新：2026-08-05  
> 当前状态：`FOUNDATION_BASELINE`  
> 阶段产品交付：`NOT_READY`  
> 当前里程碑：`M1 MEMORY_AND_CONTROLLED_EVOLUTION`  
> 当前主模块：`M1A MEMORY_CONTRACTS_AND_NAMESPACES`  
> 当前主模块阶段：`SPEC_DRAFT_NEXT`  
> 并行跨切面：`UX Assurance Plane`  
> 已关闭 UX 模块：`UX0 SYNTHETIC_USER_SHADOW_RUNTIME`  
> 下一 UX 模块：`TODO_MVC_UX_MUTATION_PROOF_SPEC`  
> UX Gate：`SHADOW_NONBLOCKING`  
> Human UAT：`REQUIRED`  
> 当前自治授权：`MANDATE-AUTONOMY-M1-M3@1.0.0 ACTIVE`

---

## 1. 状态结论

```text
M0 Harness Baseline：MERGED
M1.0 Memory Benchmark Harness：MERGED / CLOSED
M1A Memory Contracts & Namespaces：SPEC_DRAFT_NEXT
UX0 Synthetic User SPEC：MERGED / CLOSED
Synthetic User Runtime：MERGED / CLOSED
TodoMVC UX Mutation Proof：SPEC_NEXT
UX Gate Mode：SHADOW / NONBLOCKING
Human UAT：REQUIRED
M1 Memory Gate：0 / 1
Stage Delivery：NOT_READY
```

M1.0 已证明 Memory Benchmark、威胁场景、证据和独立 Replay 基线；它不实现生产 Memory Store，也不关闭完整 M1 Memory Gate。

UX0 Synthetic User Shadow Runtime 已完成 SPEC、实现、真实 Playwright Journey、独立 Replay、PR Review、主干合并、Python/GHCR 发布、台账和分支清理。它能够在 UAT 前生成真实体验证据，但仍是非阻断 SHADOW，不替代 Human UAT。

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
    U1 --> U2[✅ Shadow Runtime<br/>MERGED / CLOSED]
    U2 --> U3[🟡 TodoMVC UX Mutation Proof<br/>SPEC NEXT]
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

### 4.2 已交付

- 强类型 Profile、Environment、Oracle、Journey、Event、Metric、Finding 和 Report；
- Profile 只描述行为能力，不推断敏感人口属性；
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

### 4.3 交付证据

```text
Merge Commit：f687fd9c30873c4a81d9ffb57b20459fdcebe4ee
PR Focused Runtime：Run #25 / 30992515643 — SUCCESS
PR Full Quality：Run #134 / 30992515715 — SUCCESS
Main UX Shadow Gate：Run #26 / 30993021836 — SUCCESS
Main Quality：Run #135 / 30993021825 — SUCCESS
Release：Run #12 / 30993022051 — SUCCESS
Cleanup：Run #10 / 30993021598 — SUCCESS
Unit / Contract / Delivery / Approval：17 / 17 PASS
Real Playwright Journeys：4 / 4 PASS
Journey Checkpoints：14 / 14 PASS
Independent Replay：PASS
Campaign Verdict：PASS
Critical False Green：0
```

```text
Main UX Artifact：8924951167
Main UX Artifact Digest：sha256:afd95dfea4ba738494bc24e2c9b2c2247eb64cbaff1b5d07901ea20c4b758134
Python Distribution：8924921509
Python Digest：sha256:6ff953f33d5699d64dc832bb7bf73d63425eb5e5ae2a2f24bec9558c0996e16d
Docker Build Record：8924949424
Docker Build Digest：sha256:89e9c4b4c971f4e9a0524abdb75a2514434a3b53e72b81add762f31fe74eafc9
GHCR Tags：main / sha-f687fd9
Image Digest：sha256:a0d20ae869f323a0622e71dad8c4257fac3f32963552ea3ac9781086c3e2797d
Image Config：sha256:69fad9daed03cfdb4a7373e57a5dc6439a5d285c1ce0eae9d80385993c2f72b7
Semantic Digest：sha256:1dda03adfcc3a264240b20a883daf2a230e3ce6dcd00c43dccfb84da40b885c5
Artifact Manifest Digest：sha256:702fdce96eedbb8b81566dda08768d33434346a7edf88653594587f676c92fa4
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

## 6. 下一 UX 模块：TodoMVC UX Mutation Proof

该模块先落独立 SPEC，证明 Synthetic User 不只会让正常页面通过，还能可靠发现体验退化。

首批 Mutation Family：

```text
Missing Feedback
Visible Success but Lost State
Keyboard / Focus / Semantic Barrier
Interrupted Resume Failure
Filter / Route State Drift
```

每个 Mutation 使用：

```text
Baseline PASS
→ Mutation KILLED
→ Source Restored
→ Restored PASS
```

并记录假阳性、假阴性、Critical False Green、Replay 和恢复完整性。该模块仍不启用 Advisory 或 Blocking。

---

## 7. 当前自治与安全边界

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

## 8. 近期执行顺序

```text
1. UX0 Final Ledger / CLOSED
2. TodoMVC UX Mutation Proof SPEC
3. M1A Memory Contracts SPEC PR / Merge
4. TodoMVC UX Mutation Proof Implementation
5. M1A Domain Contracts Implementation
6. UX False-positive / False-negative Benchmark
7. M1B Store & Progressive Retrieval
```

UX 与 Memory 可交错推进，但不能通过并行降低各自的 Evidence Gate。

---

## 9. 阶段交付条件

项目只有在以下全部通过后，才从 `FOUNDATION_BASELINE` 晋升为 `TEST_AGENT_RUNTIME_BETA`：

```text
M1 Memory Gate：PASS
M2 Model Generalization Gate：PASS
M3 Project / Architecture Gate：PASS
Global Safety Gate：PASS
```

全局要求继续是：Critical False Green 0、未授权 Oracle / Experience Oracle / Policy / Permission 修改 0、Out-of-Mandate 动作 0、关键 Evidence 可重放率 100%、Memory / Model / Device / UX Asset 可追溯、自动晋升资产可回滚。
