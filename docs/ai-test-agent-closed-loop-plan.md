# AI 端到端测试 Agent 闭环实施计划

> 文档状态：规划稿 v1.0  
> 目标仓库：`lsq1030757028/Pytest-playwright-e2e`  
> 核心目标：AI 接收需求后，自主完成需求理解、测试规划、测试生成、确定性执行、失败诊断、安全修复、影响回归，并向用户提交可独立复现的回归代码与证据。

---

## 1. 产品目标

系统最终不是一个“让 AI 自动点网页”的工具，而是一个：

> 将自然语言需求编译为可读、可执行、可证伪、可长期回归的测试资产，并通过独立重放证明 Agent 的测试结论。

一次完整任务必须产生三类核心结果：

1. **TestSpec**：Agent 对需求、边界和预期结果的结构化理解。
2. **Regression Code**：用户和 CI 可以独立运行的 Pytest/Playwright 回归代码。
3. **Executable Test Proof**：正常版本、反例版本和恢复版本的执行证据。

用户不需要信任 Agent 的自然语言结论。用户通过查看 TestSpec、审查回归代码、运行 replay 命令和检查缺陷敏感性结果来确认测试执行没有问题。

---

## 2. 核心设计原则

### 2.1 AI 负责生成，确定性系统负责裁决

AI 可以：

- 理解需求；
- 分析代码与页面；
- 规划场景；
- 生成或修复测试；
- 分析失败证据。

AI 不可以直接决定最终 PASS。最终结论必须来自固定版本、固定依赖、固定测试代码下的 Pytest/Playwright 独立执行结果。

### 2.2 TestSpec 是唯一中间表示

禁止从自然语言需求直接跳到测试代码。所有测试代码必须从经过验证的 TestSpec 生成，并能反向追踪到具体 Oracle。

### 2.3 回归代码是核心信任凭证

回归代码不是副产品。它必须：

- 可读；
- 可审查；
- 可独立执行；
- 可进入 Git；
- 可稳定重放；
- 能对目标缺陷产生失败。

### 2.4 正常通过不等于测试有效

一条测试只有满足以下条件，才能成为正式回归资产：

```text
正常版本：PASS
目标缺陷或反例版本：FAIL
恢复正常版本：PASS
多次独立重放：结果稳定
```

### 2.5 自动修复必须有边界

允许自动修复：

- Locator 失效；
- Fixture 使用错误；
- 测试数据冲突；
- Playwright 同步错误；
- 清理逻辑错误；
- 明确的测试代码语法或类型问题。

禁止自动修复：

- 修改业务预期；
- 删除关键断言；
- 将产品缺陷改判为测试缺陷；
- 用重试掩盖 Flaky；
- 为了让流水线变绿而放宽断言。

---

## 3. 当前仓库基线

当前仓库已经具备以下能力：

- Pytest 的测试分层、Marker 和 Fixture；
- Playwright Browser、Context、Page 生命周期；
- Trace、截图、视频、控制台和失败请求采集；
- 环境预检；
- 基础规则式失败分类；
- JUnit 和 Markdown 报告；
- GitHub Actions、Docker、Compose 和 Kubernetes 示例；
- `SKILL.md` 中定义的测试工程规范。

当前缺失：

- 需求输入和上下文读取；
- TestSpec Schema 与校验；
- AI Runtime；
- 项目代码和页面探索；
- 测试自动生成；
- 独立 Replay Bundle；
- Mutation / Negative Control；
- 证据驱动诊断；
- 安全自动修复；
- 需求—代码—测试影响图；
- 智能回归选择；
- Agent 自身的 Benchmark。

因此现阶段定位是“确定性执行底座 MVP”，下一阶段将其升级为“AI 测试编译器与可信重放系统”。

---

## 4. 目标架构

```text
Requirement / Issue / PR / Document
                ↓
       1. Requirement Intake
                ↓
       2. Context Resolver
                ↓
       3. TestSpec Compiler
                ↓
       4. Spec Validator
                ↓
       5. Test Planner
        ↙                 ↘
 API / State tests      UI exploration
        ↘                 ↙
       6. Code Generator
                ↓
       7. Test Code Validator
                ↓
       8. Deterministic Replayer
                ↓
       9. Negative Control / Mutation
                ↓
      10. Evidence Diagnoser
         ↙              ↘
 Test repair        Product defect
         ↓              ↓
      11. Regression Selector
                ↓
      12. Quality Gate
                ↓
 Test Asset Registry / Replay Bundle / PR Report
```

### 4.1 Requirement Intake

负责接收：

- Markdown 需求；
- GitHub Issue；
- PR 描述和 Diff；
- API 文档；
- 用户在对话中提供的业务规则。

输出统一的 `RequirementInput`，保留来源、版本、提交 SHA 和原始文本，不允许覆盖原始需求。

### 4.2 Context Resolver

负责收集生成测试所需的项目上下文：

- 相关源代码；
- 已有测试；
- Fixture；
- Page / Flow Object；
- API Schema；
- 数据模型；
- 已知缺陷；
- Domain Skill；
- 环境能力和写入限制。

必须限制上下文范围，避免把整个仓库无差别发送给模型。

### 4.3 TestSpec Compiler

将需求转换为结构化测试规格。第一版建议采用 YAML + Pydantic Schema。

```yaml
id: ORDER-FREE-001
title: 免费关台边界
risk: critical
source:
  type: requirement
  reference: docs/order-close.md#free-time

preconditions:
  - order.status == running
  - free_minutes == 2

actions:
  - close_order:
      close_duration_seconds: 120

oracles:
  - id: free-time-applied
    field: response.free_time_applied
    expected: true
    source: requirement
    confidence: confirmed

  - id: order-closed
    field: database.orders.status
    expected: closed
    source: state_machine
    confidence: confirmed

verification:
  api: true
  ui: true
  database: true

cleanup:
  - delete_test_order

regression_keys:
  - order-close
  - billing
  - free-time
```

TestSpec 必须区分：

- 明确事实；
- 推导结果；
- 假设；
- 未解决歧义。

存在关键歧义时，状态进入 `REQUIREMENT_CONFLICT`，不得继续生成正式断言。

### 4.4 Test Adapter Layer

每个业务系统通过 Adapter 暴露稳定的测试能力：

```python
class ProductTestAdapter:
    def seed(self, spec): ...
    def login_as(self, role): ...
    def query_state(self, resource_id): ...
    def wait_for_event(self, event_type): ...
    def cleanup(self, resources): ...
    def reset(self): ...
```

第一版包含：

- Data Factory；
- Auth Adapter；
- API Client；
- State Probe；
- Cleanup Adapter。

后续增加：

- Database Probe；
- MQ / Event Probe；
- Clock Adapter；
- Feature Flag Adapter；
- External Service Stub。

### 4.5 Explorer

Explorer 只在以下场景调用 AI：

- 页面结构未知；
- 需要发现业务操作路径；
- 现有 Locator 失效；
- Canvas、图形或非语义控件无法通过标准 DOM 定位。

Explorer 输出结构化 Action Plan，而不是直接作为最终回归：

```yaml
page: order_detail
actions:
  - action: click
    locator:
      strategy: role
      role: button
      name: 结束订单
  - action: expect_visible
    locator:
      strategy: role
      role: dialog
      name: 结束订单
```

Action Plan 经校验后编译成确定性 Playwright 代码。

### 4.6 Code Generator

从 TestSpec、Adapter 和 Action Plan 生成：

- API 测试；
- 状态验证测试；
- Playwright E2E；
- Page Object；
- Flow Object；
- Fixture 和测试数据；
- Requirement Mapping 元数据。

生成规范：

- 测试名称表达业务行为；
- Docstring 包含 Requirement ID；
- 关键断言必须直接可见；
- 每个关键断言引用 Oracle ID；
- 禁止隐藏业务断言在通用 Helper 中；
- 禁止固定 sleep；
- 禁止无理由 `force=True`；
- 禁止 Agent 生成的代码直接写入生产环境。

### 4.7 Test Code Validator

生成代码必须先经过：

1. Schema 和 AST 校验；
2. 格式化和 Ruff；
3. 禁止模式扫描；
4. `pytest --collect-only`；
5. Fixture 依赖解析；
6. TestSpec—Assertion 映射检查；
7. 测试隔离和清理检查；
8. Dry Run。

### 4.8 Deterministic Replayer

Replayer 是最终可信执行器，不能调用模型，也不能修改测试代码。

固定：

- Git Commit；
- Python 和依赖锁文件；
- Playwright / Browser 版本；
- 环境配置；
- TestSpec；
- 测试数据种子；
- 测试代码哈希。

用户、CI、Agent Builder 都通过同一入口重放：

```bash
test-workflow replay runs/ORDER-FREE-001
```

### 4.9 Negative Control / Mutation

第一阶段不做通用 Mutation Engine，而做高价值业务反例模板：

- `<` 与 `<=` 边界交换；
- 布尔结果翻转；
- 优先级交换；
- 权限校验跳过；
- 金额增加或减少一个最小单位；
- 状态不迁移；
- API 返回成功但数据库不落库；
- UI 成功提示与真实状态不一致。

验证结果：

```text
Baseline: PASS
Mutation: FAIL
Restored: PASS
```

无法杀死目标 Mutation 的测试不能晋升为正式 Regression。

### 4.10 Evidence Diagnoser

诊断输入：

- TestSpec；
- 测试代码 Diff；
- Pytest traceback；
- Playwright Trace；
- DOM Snapshot；
- Console；
- Network；
- API Response；
- State Probe；
- 环境健康结果；
- 历史执行结果。

输出：

- 分类；
- 置信度；
- 根因；
- 证据引用；
- 是否允许自动修复；
- 推荐回归范围。

规则引擎先处理确定性分类，AI 只分析规则无法可靠判断的部分。

### 4.11 Repairer

修复流程：

```text
创建候选补丁
→ 静态验证
→ 原失败用例重放
→ 关联模块重放
→ Smoke 重放
→ Negative Control 重放
→ 生成 Diff 和修复报告
```

业务 Oracle 发生变化时必须重新回到 Requirement Intake，不能按测试缺陷修复。

### 4.12 Regression Selector

建立需求、代码、页面、接口和测试之间的影响图：

```text
Requirement
  → Business Rule
  → Source Module / API / Page
  → TestSpec
  → Test Case
  → Historical Failure
```

回归策略：

- 低风险：直接关联测试；
- 中风险：关联测试 + Smoke；
- 高风险：关联测试 + 领域回归；
- 核心计费、权限、支付：可强制完整回归。

---

## 5. Workflow 状态机

```text
RECEIVED
  ↓
CONTEXT_RESOLVED
  ↓
SPEC_DRAFTED
  ↓
SPEC_VALIDATED
  ↓
PLAN_CREATED
  ↓
TESTS_GENERATED
  ↓
TESTS_VALIDATED
  ↓
BASELINE_REPLAYED
  ↓
NEGATIVE_CONTROL_VERIFIED
  ↓
DIAGNOSED
  ↓
REPAIRED | DEFECT_REPORTED | BLOCKED
  ↓
REGRESSION_REPLAYED
  ↓
GATED
  ↓
PROMOTED
```

每个状态必须记录：

- 输入 Artifact；
- 输出 Artifact；
- 执行者；
- 模型和 Prompt 版本；
- 代码 SHA；
- 时间；
- 重试次数；
- 允许修改的文件范围；
- Gate 结果。

禁止通过对话记忆隐式维护 Workflow 状态。

---

## 6. Replay Bundle 协议

每个测试任务生成独立目录：

```text
runs/ORDER-FREE-001/<run-id>/
├── requirement/
│   ├── original.md
│   └── source.json
├── spec/
│   ├── test-spec.yaml
│   └── validation.json
├── plan/
│   ├── test-plan.yaml
│   └── action-plan.yaml
├── generated/
│   ├── tests/
│   ├── pages/
│   ├── flows/
│   └── fixtures/
├── environment/
│   ├── manifest.json
│   └── lock-info.json
├── evidence/
│   ├── baseline/
│   ├── mutation/
│   └── restored/
├── diagnosis/
│   └── result.json
├── regression/
│   └── selection.json
├── mutation-report.json
├── verdict.json
└── replay.sh
```

关键文件必须包含内容哈希，防止执行后被修改。

---

## 7. 测试资产晋升机制

```text
Candidate
  ↓ 代码校验 + Baseline 通过
Verified
  ↓ Negative Control 通过 + 稳定重放
Regression
  ↓ 长期维护和发布门禁
Deprecated
```

建议元数据：

```yaml
test_id: ORDER-FREE-001-E2E
status: regression
requirement_id: ORDER-FREE-001
spec_hash: sha256:...
code_hash: sha256:...
normal_replay:
  passed: true
mutation_score:
  killed: 3
  survived: 0
stability:
  runs: 5
  passed: 5
last_verified_commit: abc123
```

只有 `Regression` 状态测试可以作为发布阻断条件。

---

## 8. CLI 规划

第一阶段：

```bash
test-workflow spec validate test-spec.yaml
test-workflow bundle create test-spec.yaml
test-workflow replay <bundle>
test-workflow verify-test <bundle>
test-workflow promote <bundle>
```

第二阶段：

```bash
test-workflow intake requirement.md
test-workflow plan test-spec.yaml
test-workflow generate test-spec.yaml
test-workflow explore test-spec.yaml
test-workflow diagnose <run-id>
test-workflow repair <run-id>
test-workflow regress <run-id>
test-workflow gate <run-id>
```

第三阶段：

```bash
test-workflow pr analyze <repo> <pr-number>
test-workflow benchmark run
test-workflow assets list
test-workflow assets verify <test-id>
```

---

## 9. 目标目录结构

```text
src/test_workflow/
├── intake/
├── context/
├── specs/
├── planning/
├── adapters/
├── exploration/
├── generation/
├── validation/
├── replay/
├── mutation/
├── diagnosis/
├── repair/
├── regression/
├── assets/
├── benchmark/
└── orchestration/

schemas/
├── requirement-input.schema.json
├── test-spec.schema.json
├── replay-manifest.schema.json
├── failure-evidence.schema.json
└── verdict.schema.json

skills/
├── core/
└── domains/
    ├── order/
    ├── billing/
    └── authentication/

benchmarks/
└── free-time/

runs/
└── .gitignore
```

正式测试仍保留在 `tests/`，Agent 的候选代码先进入 Bundle，晋升后再写入正式测试目录。

---

## 10. 分阶段实施计划

## Phase 0：底座收敛

目标：保证现有执行框架稳定，形成后续扩展边界。

任务：

- 补依赖锁文件；
- 将当前 Playwright Pytest 插件从 `tests/conftest.py` 抽到正式包；
- 统一 Artifact 命名；
- 增加 JSON 执行摘要；
- 验证 GitHub Actions 首次完整运行；
- 删除初始化遗留文件；
- 固化版本矩阵。

验收：

- 本地、Docker、GitHub Actions 使用相同命令；
- 连续运行 5 次无随机失败；
- 失败时证据目录完整；
- 同一提交的报告可重复生成。

## Phase 1：TestSpec + Replay Bundle

目标：建立整个系统的中间表示和信任载体。

任务：

- Pydantic TestSpec Model；
- YAML 读取和 JSON Schema；
- Oracle 来源与置信度；
- Replay Manifest；
- Bundle 创建、校验和哈希；
- `replay` CLI；
- 测试资产状态模型。

验收：

- 免费关台需求能手工编写为 TestSpec；
- Bundle 在干净容器中一键重放；
- 修改 TestSpec 或代码后哈希校验失败；
- 用户不依赖 Agent 即可复现测试。

## Phase 2：第一条完整 Golden Path

目标：用免费关台场景打通端到端可信闭环。

任务：

- 免费关台 Domain Adapter；
- API 和 UI Test Generator 的最小版本；
- Baseline → Mutation → Restored；
- `<` / `<=` 边界 Mutation；
- 测试晋升 Candidate → Verified → Regression；
- 完整 Replay Bundle。

验收：

- 输入 TestSpec 后生成 API 与 E2E 测试；
- 正常实现通过；
- 边界缺陷实现失败；
- 恢复后通过；
- 重放 5 次一致；
- 生成的代码可读并能追踪 Oracle。

## Phase 3：AI Intake + Planning + Generation

目标：AI 开始接收自然语言需求并生成候选测试资产。

任务：

- 模型 Provider 抽象；
- 结构化输出；
- Prompt / Skill 版本化；
- 需求解析 Agent；
- Context Resolver；
- TestSpec Compiler；
- 测试计划 Agent；
- Python AST 代码生成；
- 生成代码验证循环。

验收：

- 给定 10 条 Golden Requirement，至少 8 条生成合法 TestSpec；
- 关键 Oracle 不得来源于当前实现；
- 生成测试首次可收集率 ≥ 90%；
- 首次可执行率 ≥ 70%；
- 无自动放宽业务断言。

## Phase 4：探索、诊断与安全修复

目标：处理未知页面和测试失败。

任务：

- Accessibility / DOM Snapshot；
- Action Plan；
- Locator 候选与评分；
- Trace、Network、State Probe 聚合；
- 分层诊断；
- Locator、同步、数据冲突修复；
- 修复后多层回归。

验收：

- 已知 Locator 变化场景修复成功率 ≥ 80%；
- 产品缺陷不得被自动修改断言掩盖；
- 诊断结果必须引用证据；
- 需求冲突时停止并请求确认。

## Phase 5：影响图与智能回归

目标：基于需求和代码变化选择回归范围。

任务：

- Requirement Mapping；
- Source/API/Page/Test 图；
- PR Diff 分析；
- 风险评分；
- 关联测试选择；
- 历史失败加权；
- 回归遗漏审计。

验收：

- Golden PR 数据集中核心受影响测试召回率 ≥ 95%；
- 相比全量回归减少至少 50% 的执行时间；
- 核心计费、权限和支付变更不允许缩小到低风险回归。

## Phase 6：Benchmark 与工程化

目标：可以量化判断 Agent 是否真的变好。

任务：

- Golden Requirement；
- 缺陷注入集；
- Locator 变化集；
- 环境故障集；
- 数据冲突集；
- 需求歧义集；
- 模型与 Prompt 对比；
- 成本、时间和质量报告。

验收指标：

- TestSpec 准确率；
- 可执行测试生成率；
- 真实缺陷召回率；
- False Green；
- 误报率；
- 错误自动修复率；
- Flaky 率；
- 回归漏选率；
- 平均 Token 成本；
- 平均执行时间。

最高优先级指标是 `False Green`，即系统给出 PASS，但目标缺陷未被发现。

---

## 11. 第一版 Benchmark 设计

围绕免费关台构建：

- 10 条明确需求；
- 20 个边界场景；
- 5 个产品缺陷；
- 3 个 Locator 变化；
- 3 个环境故障；
- 3 个测试数据冲突；
- 2 个需求歧义。

产品缺陷示例：

1. `<=` 错写为 `<`；
2. 免费分钟为 0 时仍生效；
3. API 正确但 UI 展示错误；
4. UI 展示正确但数据库状态错误；
5. 关台超过免费时长时错误减免。

测试缺陷示例：

1. 按钮文案变化；
2. Dialog 增加同名按钮；
3. 异步状态更新变慢。

---

## 12. 用户审核和信任体验

用户审核页面或报告只需回答五个问题：

1. **需求是否理解正确？** 查看 TestSpec 与 Oracle 来源。
2. **实际测了什么？** 查看回归代码和步骤摘要。
3. **是否真实执行？** 查看 JUnit、Trace、日志和状态探针。
4. **能否独立复现？** 执行统一 replay 命令。
5. **测试能否发现缺陷？** 查看 Negative Control / Mutation 报告。

最终 Verdict 示例：

```json
{
  "requirement_id": "ORDER-FREE-001",
  "spec_valid": true,
  "baseline": "PASS",
  "negative_control": "PASS",
  "restored": "PASS",
  "stability": "5/5",
  "classification": null,
  "asset_status": "REGRESSION",
  "quality_gate": "PASS"
}
```

---

## 13. 安全边界

- 生产环境默认只读；
- 所有写操作通过 Adapter 白名单；
- Agent 不能直接读取未授权 Secret；
- Bundle 中禁止保存明文密码和 Token；
- Agent 生成代码在隔离容器执行；
- 执行目录和网络访问受限；
- 模型调用内容必须可审计；
- 关键测试晋升需要规则 Gate；
- 高风险测试可配置人工审核；
- 自动修复永远不允许修改确认过的 Oracle。

---

## 14. 非目标

第一阶段不做：

- 通用 RPA 平台；
- 完全依赖视觉的浏览器 Agent；
- 每次回归都实时调用 LLM；
- 多 Agent 大规模并行；
- 通用 Mutation Testing 全量实现；
- 复杂 Dashboard；
- 自动修改业务代码；
- 生产环境破坏性测试。

---

## 15. 高杠杆优先级

严格按以下顺序推进：

1. TestSpec 和 Oracle；
2. Replay Bundle 与独立 Replayer；
3. Test Adapter；
4. 免费关台 Golden Path；
5. Negative Control；
6. AI Requirement Intake；
7. AI 测试生成；
8. 证据驱动诊断；
9. 安全修复；
10. 影响图和智能回归；
11. Benchmark；
12. 多 Agent、视觉和 UI 产品化。

在前六项没有打通之前，不优先投入多 Agent 调度、万能自愈或复杂可视化。

---

## 16. 下一开发迭代建议

下一迭代只实现 Phase 0 和 Phase 1，预计交付：

- `TestSpec` Pydantic Model；
- `ReplayManifest`；
- `ReplayBundle` Builder；
- Artifact 哈希和完整性校验；
- `test-workflow spec validate`；
- `test-workflow bundle create`；
- `test-workflow replay`；
- 免费关台 TestSpec 示例；
- 对应单元测试和 CI；
- 当前 Playwright 插件正式包化。

这一迭代完成后，再进入 AI 模型接入。这样可以先建立一个无需 AI 也能验证的确定性协议，避免 Agent 逻辑与执行底座同时变化导致难以定位问题。

---

## 17. 最终定义

本项目的最终交付不是一句“测试通过”，而是一份可执行测试证明：

```text
自然语言需求
→ 结构化 TestSpec
→ 可审查回归代码
→ 独立 Replayer
→ 正常通过
→ 目标缺陷失败
→ 恢复后通过
→ 稳定回归
→ 质量门禁
```

只有完成这条链路，Agent 的测试结论才具有工程可信度。
