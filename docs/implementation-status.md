# AI 测试 Agent 实现状态

> 文档角色：项目状态的单一事实源（Single Source of Truth）  
> 最近更新：2026-08-04  
> 默认分支：`main`  
> 当前开发分支：`agent/deterministic-mock-control-plane`  
> 当前 PR：[#7 Add deterministic mock control plane and replay bundles](https://github.com/lsq1030757028/Pytest-playwright-e2e/pull/7)

---

## 1. 使用规则

本文件用于回答以下问题：

1. 某项能力是否已经写成代码；
2. 是否有单元测试；
3. 是否经过阶段性集成测试；
4. 是否已通过远端 CI；
5. 是否已经合并进入 `main`；
6. 下一步由哪个工作流继续实现。

任何能力不得仅凭设计文档或演示代码标记为完成。

### 1.1 状态定义

| 状态 | 含义 |
|---|---|
| `PLANNED` | 已进入总体计划，但尚未开始编码 |
| `IN_PROGRESS` | 正在开发，接口或行为仍可能变化 |
| `PARTIAL` | 已实现部分能力，但不能独立完成目标场景 |
| `IMPLEMENTED` | 功能代码已经完成，具备对应单元测试 |
| `VERIFIED` | 已通过阶段性集成测试和远端 CI |
| `MERGED` | 已验证并合并进入 `main` |
| `BLOCKED` | 因依赖、环境、权限或需求冲突暂时无法推进 |

`IMPLEMENTED` 不等于 `VERIFIED`，`VERIFIED` 不等于 `MERGED`。

### 1.2 完成标准

一项能力只有同时满足以下条件，才能标记为 `VERIFIED`：

- 功能代码已提交；
- 核心行为有单元测试；
- 与上下游模块完成阶段性集成测试；
- 失败路径和边界条件有测试；
- 实现文档或使用文档已更新；
- GitHub Actions 对应步骤通过；
- 没有通过放宽业务断言、静默重试或跳过测试获得绿色结果。

只有进入 `main` 后，状态才能标记为 `MERGED`。

---

## 2. 当前总体结论

当前项目定位仍是：

> **AI 测试 Agent 的确定性执行、环境控制和可信重放底座。**

尚未达到：

> **AI 接收残缺需求后，自主完成业务理解、风险识别、测试生成、缺陷证伪、诊断修复和智能回归。**

当前已经验证的核心链路：

```text
人工整理的粗糙需求与 TestSpec
→ EnvironmentSpec / MockPlan / DataSeedSpec
→ 真实性边界和契约校验
→ 确定性环境编译
→ 哈希锁定 Replay Bundle
→ 无模型独立重放
→ CI 验证
```

当前尚未验证的目标链路：

```text
粗糙自然语言需求
→ AI 事实 / 假设 / 风险识别
→ AI TestSpec 编译
→ AI 生成 Pytest / Playwright 回归代码
→ 正常版本 GREEN
→ 缺陷版本 RED
→ 恢复版本 GREEN
→ 安全诊断与修复
→ 智能回归选择
```

---

## 3. 分支与发布状态

| 范围 | 状态 | 说明 |
|---|---|---|
| `main` 基础测试框架 | `MERGED` | Pytest、Playwright、证据采集、基础 CLI、CI、Docker |
| AI 闭环总体计划 | `MERGED` | `docs/ai-test-agent-closed-loop-plan.md` |
| Mock / 环境控制 / Replay Phase 1 | `VERIFIED` | 位于 Draft PR #7，远端 CI 已通过，尚未合并 |
| TodoMVC 业务 Golden Path | `PLANNED` | 当前 Bundle 只验证测试世界，不验证完整 Todo 业务 |
| AI Runtime 与自动需求编译 | `PLANNED` | 尚无模型 Provider 和 Agent Runtime |

---

## 4. 能力状态矩阵

### 4.1 确定性测试执行底座

| 能力 | 状态 | 代码 / 资产 | 单元测试 | 阶段集成测试 | 文档 | 下一步 |
|---|---|---|---|---|---|---|
| Pytest Marker、Fixture、参数化 | `MERGED` | `tests/`、`pyproject.toml` | 有 | CI Collect + Unit/API | README、Skill | 后续抽取正式插件包 |
| Playwright Browser / Context / Page | `MERGED` | `tests/conftest.py` | 部分 | Browser Smoke、Live E2E | README | 从 `conftest.py` 抽到 `src/` |
| Trace、截图、视频 | `MERGED` | `tests/conftest.py` | 部分 | Browser Smoke | README、Skill | 补证据完整性测试 |
| Console 与 Failed Request 采集 | `MERGED` | `tests/conftest.py` | 部分 | Browser Smoke | Skill | 统一 Evidence Schema |
| Preflight | `MERGED` | `src/test_workflow/preflight.py` | 有 | CLI 测试 | README | 增加浏览器和 Secret 检查 |
| 测试执行 CLI | `MERGED` | `src/test_workflow/runner.py`、`cli.py` | 部分 | CI | README | 合并到统一状态机 |
| JUnit / Markdown 报告 | `MERGED` | `reporting.py` | 有 | CI | README | 增加结构化 Verdict |
| 基础失败分类 | `MERGED` | `classifier.py` | 有 | 单元级 | Skill | 升级为证据驱动诊断 |

### 4.2 TestSpec 与可信 Oracle

| 能力 | 状态 | 代码 / 资产 | 单元测试 | 阶段集成测试 | 文档 | 下一步 |
|---|---|---|---|---|---|---|
| Fact / Assumption / Risk Model | `VERIFIED` | `src/test_workflow/specs.py` | 有 | Todo Bundle 验证 | Phase 1 报告 | 自动从粗糙需求生成 |
| Scenario / Oracle Model | `VERIFIED` | `src/test_workflow/specs.py` | 有 | Spec Validate | Phase 1 报告 | Oracle 依据追踪和冲突分析 |
| Truth Boundary | `VERIFIED` | `specs.py`、`mocking.py` | 有 | Mock 越界负向测试 | Mock 控制平面文档 | 增加模块级边界推导 |
| TestSpec YAML 校验 | `VERIFIED` | `serialization.py`、CLI | 有 | Todo Bundle | README、Phase 1 报告 | 增加 JSON Schema 导出 |
| AI TestSpec Compiler | `PLANNED` | 无 | 无 | 无 | 总体计划 | Requirement Intake 后实现 |
| Oracle 来源可信度校验 | `PARTIAL` | Model 约束 | 有限 | Spec Validate | 总体计划 | 禁止从当前实现反推业务预期 |

### 4.3 环境控制、Mock 与造数据

| 能力 | 状态 | 代码 / 资产 | 单元测试 | 阶段集成测试 | 文档 | 下一步 |
|---|---|---|---|---|---|---|
| EnvironmentSpec | `VERIFIED` | `specs.py` | 有 | Todo Bundle | Mock 控制平面文档 | 增加容器和服务编排字段 |
| DataSeedSpec | `VERIFIED` | `specs.py` | 有 | LocalStorage 环境编译 | Phase 1 报告 | 增加 API / DB Factory Adapter |
| LocalStorage 造数 | `VERIFIED` | `control_plane.py` | 有 | Replay 测试 | Mock 控制平面文档 | 支持 SessionStorage / IndexedDB |
| 固定系统时间 | `VERIFIED` | `control_plane.py` | 有 | Replay 测试 | Mock 控制平面文档 | 增加后端 Clock Adapter |
| 固定随机数 | `VERIFIED` | `control_plane.py` | 有 | Replay 测试 | Mock 控制平面文档 | 多语言 Seed 协议 |
| MockPlan | `VERIFIED` | `specs.py`、`mocking.py` | 有 | Mock Verify | Phase 1 报告 | 自动依赖识别和 Mock 决策 |
| Mock 真实性边界校验 | `VERIFIED` | `mocking.py` | 有 | 拒绝 Mock `todo.create` | Mock 控制平面文档 | 结合调用图增强校验 |
| JSON Schema 契约校验 | `VERIFIED` | `mocking.py` | 有 | 契约漂移负向测试 | Mock 控制平面文档 | 增加 OpenAPI / Protobuf |
| 契约哈希 | `VERIFIED` | `integrity.py` | 有 | Contract Drift Test | Phase 1 报告 | 真实环境契约采样 |
| FastAPI Virtual Service | `VERIFIED` | `virtual_service.py` | 有 | CI Replay | Mock 控制平面文档 | 网络异常、延迟、乱序事件 |
| 调用记录 | `IMPLEMENTED` | `virtual_service.py` | 有 | 基础集成 | Mock 控制平面文档 | 进入 Evidence Bundle |
| Auth / User Factory | `PLANNED` | 无 | 无 | 无 | 总体计划 | RealWorld 阶段实现 |
| DB / API Data Factory | `PLANNED` | 无 | 无 | 无 | 总体计划 | Product Adapter 阶段实现 |
| MQ / Webhook / Device Simulator | `PLANNED` | 无 | 无 | 无 | 总体计划 | 真实项目阶段实现 |
| Fault Injection | `PLANNED` | 无 | 无 | 无 | 总体计划 | Mutation 与风险探索阶段实现 |

### 4.4 Replay 与测试证明

| 能力 | 状态 | 代码 / 资产 | 单元测试 | 阶段集成测试 | 文档 | 下一步 |
|---|---|---|---|---|---|---|
| ReplayManifest | `VERIFIED` | `specs.py`、`bundle.py` | 有 | Todo Bundle | Phase 1 报告 | 增加镜像 Digest 和依赖锁 |
| Artifact SHA-256 | `VERIFIED` | `integrity.py` | 有 | Seed 篡改负向测试 | Phase 1 报告 | 签名和可信发布来源 |
| 未登记文件检测 | `VERIFIED` | `bundle.py` | 有 | Bundle Validate | Phase 1 报告 | 白名单运行时输出目录 |
| 独立 Replayer | `VERIFIED` | `bundle.py`、CLI | 有 | 本地 2 passed + CI | Mock 控制平面文档 | 在全新容器中重放 |
| Replay Evidence | `PARTIAL` | stdout、stderr、result JSON | 有限 | Replay | Phase 1 报告 | 与 Trace、Network、State Probe 统一 |
| Replay Bundle 生命周期 | `PARTIAL` | 示例目录 | 有限 | Todo Bundle | 总体计划 | Candidate / Verified / Regression |
| 数字签名 / 供应链验证 | `PLANNED` | 无 | 无 | 无 | 总体计划 | 稳定阶段再实现 |

### 4.5 业务理解与 AI Agent

| 能力 | 状态 | 代码 / 资产 | 单元测试 | 阶段集成测试 | 文档 | 下一步 |
|---|---|---|---|---|---|---|
| 粗糙需求输入样例 | `VERIFIED` | `experiments/.../rough-requirement.md` | 不适用 | Bundle 验证 | Phase 1 报告 | 接入 Intake Pipeline |
| 人工 Fact / Assumption / Risk 样例 | `VERIFIED` | `experiments/.../understanding/` | Schema 测试 | Bundle 验证 | Phase 1 报告 | 由 AI 自动生成候选 |
| RequirementInput | `PLANNED` | 无 | 无 | 无 | 总体计划 | 定义来源、版本、原文哈希 |
| Context Resolver | `PLANNED` | 无 | 无 | 无 | 总体计划 | 代码、测试、API、页面上下文 |
| 模型 Provider 抽象 | `PLANNED` | 无 | 无 | 无 | 总体计划 | 支持可替换模型和 Mock Provider |
| 业务理解 Agent | `PLANNED` | 无 | 无 | 无 | 总体计划 | 输出 Facts / Assumptions / Risks |
| 风险识别 Agent | `PLANNED` | 无 | 无 | 无 | 总体计划 | 使用隐藏 Golden Evaluator 验证 |
| Test Planner | `PLANNED` | 无 | 无 | 无 | 总体计划 | 决定 Unit / API / E2E 层级 |
| Test Code Generator | `PLANNED` | 无 | 无 | 无 | 总体计划 | 输出候选 Bundle，不直写正式测试 |
| 页面 Explorer | `PLANNED` | 无 | 无 | 无 | 总体计划 | Accessibility Snapshot + Action Plan |

### 4.6 测试有效性、诊断与回归

| 能力 | 状态 | 代码 / 资产 | 单元测试 | 阶段集成测试 | 文档 | 下一步 |
|---|---|---|---|---|---|---|
| 正常版本 Baseline | `PLANNED` | 无真实 Todo 业务测试 | 无 | 无 | 总体计划 | TodoMVC Golden Path |
| Mutation / Negative Control | `PLANNED` | 无 | 无 | 无 | 总体计划 | 先做高价值业务 Mutation |
| GREEN → RED → GREEN | `PLANNED` | 无 | 无 | 无 | 总体计划 | Phase 2 核心验收 |
| 证据驱动诊断 | `PLANNED` | 当前仅关键词分类 | 基础分类测试 | 无 | 总体计划 | 聚合 Trace / Network / Probe |
| Locator 安全修复 | `PLANNED` | 无 | 无 | 无 | 总体计划 | Phase 4 |
| 测试数据自动修复 | `PLANNED` | 无 | 无 | 无 | 总体计划 | Adapter 成熟后实现 |
| 产品缺陷保护规则 | `PARTIAL` | Skill 与分类规则 | 有限 | 无 | Skill、总体计划 | Repair Gate 强制执行 |
| 需求—代码—测试影响图 | `PLANNED` | 无 | 无 | 无 | 总体计划 | Phase 5 |
| 智能回归选择 | `PLANNED` | 无 | 无 | 无 | 总体计划 | 影响图后实现 |
| Agent Benchmark | `PLANNED` | 无 | 无 | 无 | 总体计划 | Phase 6 |
| False Green 指标 | `PLANNED` | 仅设计 | 无 | 无 | 总体计划 | TodoMVC Mutation 起开始统计 |

---

## 5. 并行开发策略

项目不要求一次性完成全部能力，允许按相对独立的工作流并行推进，但必须遵守接口优先和阶段集成原则。

### 5.1 并行工作流

| 工作流 | 主要范围 | 当前状态 | 可并行依赖 |
|---|---|---|---|
| A. Core Runtime | CLI、状态机、Artifact、Evidence | `PARTIAL` | 可与 B、C 并行 |
| B. Spec & Oracle | RequirementInput、TestSpec、Oracle Gate | `PARTIAL` | 为 D 提供稳定接口 |
| C. Environment Control | Seed、Mock、Clock、Virtual Service | `VERIFIED` 于 PR #7 | 可继续扩展 Adapter |
| D. AI Intake & Planning | 业务理解、风险识别、测试计划 | `PLANNED` | 依赖 B 的 Schema |
| E. Test Generation | Pytest / Playwright 生成与校验 | `PLANNED` | 依赖 B、C、D |
| F. Mutation & Proof | Baseline、Mutation、Restored | `PLANNED` | 可先用人工 TestSpec 并行 |
| G. Diagnosis & Repair | 证据聚合、分类、有限修复 | `PLANNED` | 依赖 A 的 Evidence |
| H. Regression & Benchmark | 影响图、智能回归、指标 | `PLANNED` | 在 E、F 稳定后推进 |

### 5.2 并行约束

1. **接口先于实现**：并行模块先提交 Pydantic Model、Protocol 或 JSON Schema。
2. **禁止直接耦合实现细节**：模块之间只通过版本化 Artifact 交互。
3. **候选资产隔离**：AI 生成内容先进入 Replay Bundle，不直接修改正式回归集。
4. **每个工作流独立分支和 PR**：避免大规模长生命周期分支。
5. **每个 PR 只声明自己完成的状态**：不得顺带将未验证能力标记完成。
6. **阶段集成分支短期存在**：跨模块联调后及时合并或删除。
7. **文档与代码同 PR 更新**：状态文档必须在能力状态变化时同步修改。

---

## 6. 测试策略

### 6.1 单元测试要求

每个新模块必须覆盖：

- 正常路径；
- 输入 Schema 校验；
- 边界值；
- 拒绝路径；
- 安全约束；
- 可重复性；
- 序列化与反序列化；
- 关键错误信息。

高风险模块的最低单元测试要求：

| 模块 | 必测内容 |
|---|---|
| TestSpec | Oracle 引用、Assumption Gate、Truth Boundary |
| MockPlan | 越界 Mock、缺失契约、契约漂移、非法行为 |
| Replay | 篡改、缺失、新增文件、命令失败、重复运行 |
| AI Intake | 不完整输入、歧义、事实与假设混淆 |
| Code Generator | 禁止 sleep、禁止放宽断言、AST 可解析 |
| Repairer | 仅允许测试缺陷修复、产品缺陷不可修改 Oracle |
| Regression Selector | 核心变更召回、风险升级、不允许漏掉 Critical |

### 6.2 阶段性集成测试要求

每个阶段必须有一个独立、可重复运行的集成场景。

| 阶段 | 集成场景 | 当前状态 |
|---|---|---|
| Stage 0 | Pytest + Playwright Smoke + Live E2E | 已通过 |
| Stage 1 | TestSpec + MockPlan + Env Build + Replay | 已通过 PR #7 |
| Stage 2 | 真实 TodoMVC Baseline + Mutation + Restored | 未实现 |
| Stage 3 | 粗糙需求 → AI TestSpec → 候选测试生成 | 未实现 |
| Stage 4 | Locator 变化 → 诊断 → 安全修复 → 回归 | 未实现 |
| Stage 5 | PR Diff → 智能选测 → 漏选审计 | 未实现 |
| Stage 6 | Golden Benchmark 全量评估 | 未实现 |

### 6.3 CI 分层

建议 CI 固定为以下层级：

```text
PR Fast Gate
├── Ruff / 类型与 Schema 校验
├── 单元测试
├── Pytest Collect
└── 受影响模块集成测试

Stage Gate
├── 当前阶段 Golden Scenario
├── Replay 完整性
├── Negative Control
└── Artifact 上传

Main / Nightly
├── 全量单元测试
├── API + Browser Regression
├── 多次稳定性重放
├── Contract Smoke
└── Benchmark 子集
```

任何阶段能力不得只依赖手工验证。

---

## 7. 阶段 Gate

### Gate 1：Phase 1 合并

当前 PR #7 已达到 `VERIFIED`，合并前需要：

- 保持 GitHub Actions 全绿；
- 审查 Truth Boundary 行为；
- 确认 Phase 1 文档无误；
- 将本状态文档纳入 PR；
- 合并后将对应能力状态改为 `MERGED`。

### Gate 2：TodoMVC Golden Path

必须完成：

- 固定公开 TodoMVC Commit；
- 使用真实 Todo 核心逻辑；
- 生成或手写可读回归代码；
- 至少四个业务 Mutation；
- Baseline PASS；
- Mutation FAIL；
- Restored PASS；
- 连续重放至少三次一致；
- Critical False Green 为 0。

### Gate 3：最小 AI 闭环

必须完成：

- 粗糙需求自动生成 Facts / Assumptions / Risks；
- 关键歧义能够停止或降级；
- 自动生成合法 TestSpec；
- 自动生成可收集测试；
- 独立 Replayer 执行；
- Hidden Evaluator 能检查业务理解和风险召回。

---

## 8. 近期执行顺序

允许并行，但建议优先形成两个并行纵向切片。

### 切片 A：真实 TodoMVC 测试证明

```text
固定目标版本
→ Product Adapter
→ 真实 E2E
→ Mutation
→ GREEN / RED / GREEN
→ 稳定 Replay
```

该切片不依赖 AI，可先证明测试有效性体系。

### 切片 B：AI 业务理解最小闭环

```text
RequirementInput
→ Mock Model Provider
→ Facts / Assumptions / Risks
→ TestSpec
→ Hidden Evaluator
```

该切片先不生成浏览器代码，专注验证业务理解与风险识别。

二者稳定后再汇合：

```text
粗糙需求
→ AI TestSpec
→ TodoMVC 测试生成
→ 独立 Replay
→ Mutation 证伪
```

---

## 9. 状态维护责任

每个开发 PR 必须更新本文件：

- 新增或调整能力状态；
- 写明代码位置；
- 写明新增单元测试；
- 写明阶段集成测试结果；
- 写明 CI Run；
- 写明是否已合并；
- 明确剩余风险。

状态变化规则：

```text
PLANNED
→ IN_PROGRESS
→ PARTIAL / IMPLEMENTED
→ VERIFIED
→ MERGED
```

出现回归或发现实现不完整时，允许状态向前回退，不得为了进度保留虚假的完成状态。

---

## 10. 当前下一步

1. 审查并合并 PR #7；
2. 合并后更新本文件，将 Phase 1 能力改为 `MERGED`；
3. 建立 TodoMVC Golden Path 分支；
4. 并行建立 RequirementInput 与 AI Understanding Schema；
5. 每个分支先补单元测试，再加入阶段性集成测试；
6. TodoMVC 与 AI Understanding 两个切片通过后，再启动自动测试代码生成。
