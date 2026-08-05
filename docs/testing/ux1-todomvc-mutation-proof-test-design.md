# UX1 TodoMVC Mutation Proof Test Design

> Goal：Issue #34  
> SPEC：`SPEC-UX1-TODOMVC-MUTATION-PROOF@1.0.0`  
> Parent Runtime：`UX0-SYNTHETIC-USER-SHADOW@1.0.0`  
> Mandate：`MANDATE-AUTONOMY-M1-M3@1.0.0`  
> DEV：`DEV3`  
> UX：`UX3`  
> 本阶段：SPEC only

## 1. 测试目标

证明 UX1 SPEC 足以约束未来 Mutation Proof Runner，使它能够：

- 在健康目标上保持零 Baseline False Positive；
- 对五类体验退化产生确定性 Kill；
- 不把 AI 主观 Finding 当作 Kill；
- 不泄漏 Mutation Metadata 给 Synthetic User；
- 不修改当前仓库、远程系统或生产数据；
- 精确恢复目标源码并独立重放证明；
- 在任一前置条件、恢复或证据失败时 Fail Closed。

SPEC Gate 不执行真实 Mutation，但必须离线证明 Mutation Catalog 与固定目标 Preimage 一致、Hash 正确且可精确恢复。

## 2. 风险与失败模式

| ID | 失败模式 | 风险 |
|---|---|---|
| UX1-01 | Mutation Search 在目标中不存在或匹配多次 | 变异对象不确定，可能改错代码 |
| UX1-02 | Preimage / Postimage Hash 未固定 | 目标变化后仍误用旧 Mutation |
| UX1-03 | Catalog 允许 Regex、Shell 或路径穿越 | Mutation 逃逸受控 Sandbox |
| UX1-04 | Baseline 失败仍继续执行 Mutation | 环境故障被误报为 Kill |
| UX1-05 | Mutated Journey PASS 仍标记 Killed | Critical False Green |
| UX1-06 | 只有 AI Finding 就计为 Kill | 主观判断污染证明 |
| UX1-07 | Mutation ID 或预期失败泄漏给 Actor | Synthetic User 看答案做题 |
| UX1-08 | 三阶段 Pins 不一致 | 不能归因于 Mutation |
| UX1-09 | 恢复通过逆向替换而非原始 Bytes | 无法证明精确恢复 |
| UX1-10 | Restored 失败仍关闭 Proof | 目标污染或回归被掩盖 |
| UX1-11 | 未声明文件被修改 | Mutation Blast Radius 越界 |
| UX1-12 | Artifact / Replay 被篡改 | 证据不可重放 |
| UX1-13 | Mutation Proof 被误用来启用 Blocking | 未经 Benchmark 就升级发布权力 |
| UX1-14 | SPEC 合并被误报为 Runner 已实现 | 进度和能力失真 |

## 3. Test Obligations

| Obligation | 证据 |
|---|---|
| SPEC 身份、Goal、父 Runtime 和 Mandate 正确 | identity policy test |
| 固定目标 Revision、文件 Blob、Byte Length 和 SHA-256 一致 | source inventory test |
| 五个 Mutation ID 连续且五个 Family 完整 | catalog ordering test |
| 每个 Search 在 Preimage 中恰好出现一次 | exact-match test |
| Search / Replacement / Postimage Hash 正确 | offline mutation proof test |
| 替换后恢复原始 Bytes 得到同一 Preimage Hash | restoration round-trip test |
| 每个 Mutation 映射到现有 Journey、Oracle 和 Checkpoint | coverage mapping test |
| Catalog 不允许 Regex、Shell、绝对路径或 Traversal | negative catalog test |
| Hidden Evaluator 字段不会进入 Actor Input | hidden-boundary test |
| 状态机只允许声明转换，失败态为终态 | transition closure test |
| Baseline Failed、Mutation Survived、Restore Failed 优先阻断 PASS | adjudication precedence test |
| AI Candidate 不能成为 Kill Authority | AI authority test |
| 所有三阶段 Pins 相同，只有目标内容 Hash / Phase 可变化 | pin invariant test |
| Artifact、Replay、Tamper 和 Digest 义务完整 | replay contract test |
| SHADOW、Human UAT、Advisory/Blocking 边界不变 | governance boundary test |
| M1A 仍是主模块，M1 Gate 与 Stage Delivery 未完成 | project truthfulness test |

## 4. 证据选择

### 本 SPEC PR 必须执行

- YAML 机器契约结构检查；
- 固定目标 Preimage 离线 Hash；
- 五个 Exact Text Mutation 的 Search / Replacement / Postimage Hash；
- Exact Match Count = 1；
- Apply / Restore Round-trip；
- Journey / Oracle / Checkpoint 映射；
- 状态机闭包与非法跳转；
- Negative / Adversarial 资产；
- SHADOW 和 Human UAT 治理边界；
- 完整仓库 CI 回归；
- Main / Release / Cleanup。

### 本 SPEC PR 明确不执行

- 目标 Checkout 的真实修改；
- Baseline / Mutated / Restored Playwright 运行；
- Mutation Kill Rate；
- False-positive / False-negative Benchmark；
- 真实 LLM 诊断；
- Advisory / Blocking Promotion。

这些证据属于 SPEC 合并后的 UX1 Implementation Goal，不应在 SPEC PR 中提前实现。

## 5. Canonical Asset

```text
tests/assets/ux/ux1/target-index-preimage.html
```

该文件是固定目标 `index.html` 的精确快照：

```text
Bytes：1459
SHA-256：8abcb565e24e7fdbe75feb21f986e9b7550173c04122727e4e07e7ec9c4d5f70
Git Blob：2f5a055475c5a4810bbf948f6b5acf6ed45fdc4a
```

SPEC Test 使用该快照离线证明：

```text
Preimage
→ Exact Search Count = 1
→ Exact Replace
→ Expected Postimage Hash
→ Restore Saved Original Bytes
→ Original Hash
```

## 6. Mutation Coverage

| Mutation | Expected Journey | Required deterministic loss |
|---|---|---|
| UXM-001 | novice-add-task | 任务列表或剩余数反馈不可观察 |
| UXM-002 | interrupted-resume / returning-filter-persistence | 刷新后状态丢失 |
| UXM-003 | keyboard-primary | 输入框无语义名称 |
| UXM-004 | interrupted-resume | 中断恢复失败 |
| UXM-005 | returning-filter-persistence | Completed 路由和筛选结果错误 |

每个 Expected Failed Checkpoint 必须真实存在于父 UX0 Catalog；不存在的 Checkpoint 使 SPEC Gate 失败。

## 7. 状态机测试

成功路径必须完整且有序：

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

测试要求：

- 成功路径每一对相邻状态均合法；
- 所有 Transition Target 都在状态集合中；
- 所有失败态无后继；
- `PLANNED → MUTATION_APPLYING` 非法；
- `BASELINE_FAILED → ...` 非法；
- `MUTATION_SURVIVED → CLOSED_PASS` 非法；
- `MUTATION_KILLED → CLOSED_PASS` 非法，必须先恢复；
- `CLOSED_PASS` 不能重新开始。

## 8. Verdict Precedence

未来 Runner 必须按以下优先级 Fail Closed：

```text
Evidence / Target / Restore INVALID
→ External Boundary BLOCKED
→ Baseline False Positive INVALID / FAIL
→ Critical Mutation SURVIVED = FAIL
→ All KILLED + Restored + Replay = PASS
```

AI Candidate Finding 不参与该优先级。

## 9. 通过条件

```text
Required Mutation Families：5 / 5
Required Mutation IDs：UXM-001 ... UXM-005
Target Revision / Preimage Hash：Pinned
Exact Search Count：1 / Mutation
Offline Postimage Hash Match：5 / 5
Exact Restore Round-trip：5 / 5
Journey / Oracle / Checkpoint Mapping：100%
Hidden Metadata Leakage Paths：0
Arbitrary Command / Regex / Traversal Paths：0
AI-only Kill Paths：0
Advisory Enabled：false
Blocking Enabled：false
Human UAT Required：true
M1 Memory Gate：0 / 1
Stage Delivery：NOT_READY
Critical False Green：0
```

SPEC 通过后，只允许进入 UX1 Mutation Proof Runner Implementation，不允许直接晋升 Advisory 或 Blocking。
