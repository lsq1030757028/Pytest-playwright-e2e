# TodoMVC UX Mutation Proof SPEC

> SPEC：`SPEC-UX1-TODOMVC-MUTATION-PROOF@1.0.0`  
> 状态：`CANDIDATE`  
> Goal：Issue #34  
> Parent Runtime：`UX0-SYNTHETIC-USER-SHADOW@1.0.0`  
> Mandate：`MANDATE-AUTONOMY-M1-M3@1.0.0`  
> DEV：`DEV3`  
> UX：`UX3`  
> Runtime Mode：`SHADOW`  
> Human UAT：`REQUIRED`

## 1. 目标

UX0 已证明 Synthetic User 能让健康的四条 TodoMVC Journey 通过，但这不足以说明它真的能发现体验问题。

UX1 必须证明：当固定目标被注入明确的体验退化时，Synthetic User 能依据原有 Experience Oracle 和真实 Playwright 证据将其识别出来，并且不会把健康版本误判为失败。

每个 Mutation 都执行：

```text
Baseline PASS
→ Apply bounded Mutation
→ Mutation KILLED
→ Restore exact source bytes
→ Restored PASS
→ Independent Replay PASS
```

## 2. 本阶段不实现 Runner

本 PR 只定义：

- Mutation Contract；
- 固定目标与文件 Hash；
- Mutation Catalog；
- 三阶段状态机；
- Kill / Survive / Invalid / Blocked 语义；
- Hidden Evaluation；
- Evidence、Replay 和恢复要求；
- 未来 Runner Port。

SPEC 合并之前禁止实现 Mutation Runner 或修改目标文件。

## 3. 固定目标

```text
Repository：percy/example-todomvc
Revision：4a2344b2207a72c680e5c559c72617498fb5b75b
Target Manifest：targets/percy-example-todomvc/target.yaml
Mutable File：index.html
Git Blob：2f5a055475c5a4810bbf948f6b5acf6ed45fdc4a
Preimage SHA-256：8abcb565e24e7fdbe75feb21f986e9b7550173c04122727e4e07e7ec9c4d5f70
Bytes：1459
```

只允许修改一次性目标 Checkout 中声明的文件。仓库代码、远程服务和生产环境不在可写范围内。

## 4. 为什么采用 Exact Text Replace

第一版不建设通用 AST 或任意代码变异框架，而采用受控的：

```text
Exact Preimage Hash
+ Exact Search Text
+ Exact Replacement Text
+ Expected Match Count = 1
+ Exact Postimage Hash
```

理由：

- Mutation 语义可审计；
- 目标 Revision 改变时会自动失效；
- 不允许 Regex 意外匹配；
- 不允许任意 Shell；
- 可精确恢复原始 Bytes；
- 同一个 Catalog 可以独立重放。

任何以下情况都必须 `INVALID`：

- Preimage Hash 不一致；
- Search Text 为 0 或多于 1 个匹配；
- Postimage Hash 不一致；
- 出现未声明文件变化；
- 目标 Worktree 原本不干净。

## 5. 五个 Mutation

| ID | Family | 用户损失 | Journey / Oracle |
|---|---|---|---|
| `UXM-001` | Missing Feedback | 数据已保存，但用户看不到列表和剩余数反馈 | Novice / Add Task |
| `UXM-002` | Visible Success State Loss | 页面立即显示成功，但刷新后数据消失 | Interrupted、Returning |
| `UXM-003` | Keyboard / Semantic Barrier | 主输入框失去可访问名称 | Keyboard |
| `UXM-004` | Interrupted Resume Failure | 页面中断时清除已保存任务 | Interrupted |
| `UXM-005` | Filter / Route Drift | “Completed” 实际进入 Active 路由 | Returning |

完整 Search、Replacement、Hash 与 Oracle Mapping 位于：

```text
tests/assets/ux/ux1/mutation-catalog.yaml
```

## 6. 三阶段证明

### Baseline

目标必须是固定 Revision 和干净 Preimage。

要求：

- 相关 Journey `PASS`；
- Checkpoint 全部通过；
- Artifact 和 Actor Input 完整；
- 不允许先有 AI Warning 再把健康版本当失败。

Baseline 失败属于 False Positive 或环境问题，不能继续 Mutation 阶段。

### Mutated

只有 Mutation Postimage Hash 已验证后才能启动目标。

Kill 必须满足：

- 命中 Catalog 声明的 Experience Oracle Clause；
- 对应 Checkpoint 确定性失败；
- Evidence 至少 E3；
- Trace、Screenshot、Semantic Snapshot 和状态证据一致；
- 失败不是由环境、目标启动或无关 Journey 问题造成；
- AI Candidate Finding 不是 Kill Authority。

### Restored

恢复必须使用最初保存的原始 Bytes，不允许通过“逆向替换”猜测恢复。

要求：

- 文件 SHA-256 等于 Preimage；
- `git status` 干净；
- 变更文件列表为空；
- 同一 Journey/Profile/Environment 再次 PASS；
- Replay 与原证明语义一致。

恢复失败时整个 Mutation Proof 为 `INVALID`。

## 7. 状态机

```text
PLANNED
→ BASELINE_RUNNING
→ BASELINE_PROVEN
→ MUTATION_APPLYING
→ MUTATION_VERIFIED
→ MUTATED_RUNNING
→ MUTATION_KILLED
→ RESTORING
→ RESTORE_VERIFIED
→ RESTORED_RUNNING
→ CLOSED_PASS
```

主要失败态：

```text
BASELINE_FAILED
MUTATION_APPLY_FAILED
MUTATION_SURVIVED
RESTORE_FAILED
REPLAY_DRIFTED
INVALID_EVIDENCE
BLOCKED
```

进入失败态后禁止继续执行后续阶段。

## 8. Kill、Survive 与 Invalid

### KILLED

Mutated 阶段以 E3/E4 确定性证据触发 Catalog 声明的 Oracle / Checkpoint 失败，并完成精确恢复、Restored PASS 和 Replay。

### SURVIVED

以下任何一种情况表示 Mutation 生存：

- Mutated Journey 仍通过；
- 失败与声明的 Oracle 无关；
- 只有 AI 主观 Finding；
- Evidence 低于 E3。

关键 Mutation 生存意味着 Campaign `FAIL`，并计为 Critical False Green 风险。

### INVALID

- Baseline 失败；
- Mutation 未真实应用；
- Hidden Metadata 泄漏；
- Artifact 被篡改；
- 恢复不精确；
- Worktree 不干净；
- Replay 漂移。

`INVALID` 不能被记为 Kill 或 PASS。

### BLOCKED

工具、目标、浏览器、权限或超时边界导致无法构造有效证明时使用。Blocked 不能自动转成 PASS。

## 9. Hidden Evaluation

Synthetic User 在三个阶段看到相同类型的输入：

```text
User Goal
+ Profile
+ ExperienceEnvironment
+ Visible Application State
+ Allowed Capabilities
+ Budgets
```

以下字段仅 Proof Controller / Evaluator 可见：

- Mutation ID / Family；
- Target Path；
- Search / Replacement；
- Expected Failed Checkpoint；
- Expected Verdict；
- Evaluator Scoring Key。

Actor Input 出现任何 Mutation Metadata 时，本次证据必须 `INVALID`。

## 10. Pin 一致性

Baseline、Mutated、Restored 必须保持一致：

- Target Revision；
- Journey、Profile、ExperienceEnvironment；
- Requirement 和 Design System；
- Fixture、Browser、Playwright、Evaluator；
- Capability Versions；
- Random Seed 和 Budgets。

唯一允许的目标差异是：

```text
Target File Content Hash
+ Proof Phase
```

## 11. Sandbox 与权限

未来 Runner 只能：

- 克隆固定目标到 Disposable Checkout；
- 读取、Hash 和精确替换声明文件；
- 启停本地 Target Process；
- 启停本地 Browser；
- 写入本地 Artifact；
- 恢复原始 Bytes。

禁止：

- 修改当前仓库；
- 写远程或生产目标；
- 读取 Secret 或真实用户数据；
- Catalog 携带 Shell Command；
- 路径穿越或 Symlink Escape；
- 多个 Mutation 共用脏 Checkout。

## 12. Evidence

每个 Phase 至少生成：

- 全部 Pin；
- Actor Input Hash；
- Target Revision、文件 Hash 和 Git Status；
- Interaction Events；
- Before / After State Hash；
- Trace、Screenshot、Semantic Snapshot；
- Checkpoint Results；
- Deterministic Evaluation；
- Target stdout / stderr。

Mutation 应用额外生成：

- Search / Replacement Hash；
- 实际 Replacement Count；
- Postimage Hash；
- Changed Files。

Campaign 生成：

- JSON / Markdown Report；
- Source Inventory；
- Artifact Manifest；
- Replay Manifest；
- Semantic Proof Digest。

## 13. Campaign Gate

```text
Required Mutations：5 / 5
Critical Mutation Kill Rate：100%
Baseline False Positive：0
Critical False Green：0
Exact Restore：100%
Independent Replay：100%
Hidden Metadata Leakage：0
Undeclared Changed Files：0
AI-only Kill：0
```

Campaign PASS 不会自动启用 Advisory 或 Blocking，只为后续 False-positive / False-negative Benchmark 提供基础。

## 14. Runner Boundary

未来实现分为六个 Port：

- `MutationCatalogPort`；
- `TargetSandboxPort`；
- `MutationApplicationPort`；
- `UXPhaseExecutionPort`；
- `MutationAdjudicationPort`；
- `MutationReplayPort`。

Mutation Runner 必须复用已合并的 `UXShadowRunner`、`TargetManager`、Artifact 与 Replay 语义，不建立第二套 Synthetic User Runtime。

## 15. 不改变的边界

```text
Runtime Mode：SHADOW
Release Effect：NONBLOCKING_SHADOW
Human UAT：REQUIRED
Advisory：DISABLED
Blocking：DISABLED
M1A：当前主模块
M1 Memory Gate：0 / 1
Stage Delivery：NOT_READY
```

## 16. 实现顺序

```text
UX1 SPEC
→ Domain Models / Catalog
→ Disposable Target Sandbox
→ Exact Mutation Application
→ Three-phase Runner
→ Deterministic Adjudication
→ Artifact / Replay
→ Five-mutation Campaign
→ False-positive / False-negative Benchmark
→ Advisory Candidate Assessment
```
