# GitHub Development SSOT 测试设计

> 变更保障等级：`DEV2`  
> 原因：本变更修改 Agent 入口、SPEC Gate、PR 模板、CI Gate 和仓库研发行为，但不放宽 Oracle、Policy、Permission 或生产批准边界。

## 1. 测试目标

证明仓库存在且只使用一套可执行的 GitHub 云端研发流程事实源，并保证该流程：

- 每个非平凡模块在运行时实现前先完成并合并 SPEC；
- 不把“每模块固定单元测试 + 集成测试”写成机械规则；
- 根据变更风险和真实边界动态选择证据；
- 禁止直接写入 `main`；
- 限制 Agent 自动合并和治理修改权限；
- 合并后必须继续验证主干和发布；
- 将 Goal、SPEC、Agent、PR、CI、状态和资产管理连接成闭环。

## 2. 主要失败模式

| ID | 失败模式 | 影响 |
|---|---|---|
| SSOT-01 | Agent 找不到统一入口 | 每个 Agent 自定义流程，状态和证据分裂 |
| SSOT-02 | DEV0 也被强制编写 Unit / Integration | 无意义维护成本，流程笨重 |
| SSOT-03 | 边界变化不需要 Integration | Unit 假证明真实 API、Store、CI 或发布行为 |
| SSOT-04 | DEV3 可由 Agent 降级或自动合并 | Oracle、Memory、Model、Device、Policy 失控 |
| SSOT-05 | PR 绿色就直接 CLOSED | 主干或发布失败被忽略 |
| SSOT-06 | Change-specific Evidence 与全量 CI 混为一谈 | 跑了很多测试但没有证明本次需求 |
| SSOT-07 | 模板、Markdown 与 YAML 漂移 | 人类流程和机器 Gate 不一致 |
| SSOT-08 | 临时分支未清理 | 云端仓库积累过期实现状态 |
| SSOT-09 | 未落 SPEC 就开始写运行时代码 | 需求、架构、Oracle、风险和验收在实现后补写 |
| SSOT-10 | SPEC 合并被误报为模块完成 | 路线和进度出现假完成 |
| SSOT-11 | 已批准 SPEC 被静默改写 | 既有实现和证据的语义基础失效但未触发重跑 |

## 3. Test Obligations

| Obligation | 证据 |
|---|---|
| 根目录存在强制 `AGENTS.md` | `test_repository_has_one_active_github_development_ssot` |
| GitHub Actions 是权威验证，禁止直接 main | 同上 |
| 生命周期包含 SPEC_DRAFT → SPEC_IN_REVIEW → SPEC_APPROVED → IMPLEMENTING | `test_spec_gate_precedes_runtime_implementation` |
| DEV2 / DEV3 需要已批准 SPEC | 同上、Profile 测试 |
| DEV0 / DEV1 / DEV-E 例外被明确约束 | `test_spec_gate_precedes_runtime_implementation` |
| SPEC 完成不能直接关闭模块 | 同上 |
| DEV0 不机械要求 Unit / Integration | `test_assurance_profiles_are_risk_adaptive_not_mechanical` |
| DEV2 的真实边界必须有 Integration 或解释替代 | 同上 |
| DEV3 需要人工批准且 Agent 不可降级 | 同上、`test_agent_autonomy_has_explicit_safety_boundaries` |
| 变更证据与仓库回归是两套职责 | `test_change_specific_evidence_is_separate_from_repository_regression` |
| CLOSED 之前必须 Main + Release 验证 | `test_lifecycle_requires_main_and_release_verification_before_close` |
| 修改 SSOT 至少 DEV2，放宽 SPEC / 安全规则为 DEV3 | `test_ssot_changes_cannot_relax_governance_silently` |
| PR 模板必须引用 SPEC 和当前阶段 | `test_github_templates_and_ci_expose_the_ssot_process` |
| 现有产品、Harness、Replay、Browser、Target、Mutation 基线未回退 | 完整 GitHub Actions workflow |
| 合并后主干与发布仍然成功 | Main CI、Release Workflow、Artifact / GHCR 证据 |
| 实现分支被清理 | Cleanup Workflow + branch audit |

## 4. 证据选择说明

### 选择

- YAML 结构与策略单元测试：流程核心是结构化策略，适合确定性验证；
- GitHub PR / Issue / SPEC 入口解析：验证云端开发入口；
- 完整仓库 CI：证明新增治理文件没有破坏现有执行基线；
- 主干与 Release Workflow：证明 CLOSED 规则在本次变更中被实际执行；
- 分支清理：验证云端生命周期尾项。

### 不单独新增业务 Integration Test 的原因

本变更不改变业务运行时或 Harness Capability 边界。其真实边界是 GitHub Goal、SPEC、PR、Actions、Release 和 Branch lifecycle，因此以 GitHub 云端流水线作为阶段集成证据，比构造本地“流程集成测试”更真实。

M1.0 后续 Memory Runtime 实现不是本规则的例外：它必须在 SPEC 合并后，以 DEV3 方式增加真实 Store / Retrieval Integration、Poisoning、Replay、Benchmark 和 Rollback 证据。

## 5. 资产

- Agent 入口：`AGENTS.md`
- 规范：`docs/github-development-ssot.md`
- 机器策略：`docs/github-development-ssot.yaml`
- PR 模板：`.github/pull_request_template.md`
- Goal 模板：`.github/ISSUE_TEMPLATE/goal.yml`
- 单元测试：`tests/unit/test_github_development_ssot.py`
- CI Gate：`.github/workflows/ci.yml`
- 测试设计：本文件

## 6. 通过条件

- SPEC-first 和 SSOT 策略测试全部通过；
- Ruff / Collect 通过；
- 完整现有 CI 全绿；
- Review 无未解决阻塞项；
- 合并后 Main CI、Release 和 Branch Cleanup 成功；
- 当前状态不把 SPEC 合并误报为模块实现完成；
- 当前状态不再机械要求每个模块固定执行 Unit + Integration；
- Critical False Green 保持为 0。
