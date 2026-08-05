# UX0 Synthetic User Shadow Runtime

> Runtime：`UX0-SYNTHETIC-USER-SHADOW@1.0.0`  
> SPEC：`SPEC-UX0-SYNTHETIC-USER@1.0.0`  
> Approval：`APPROVAL-UX0-SYNTHETIC-USER-SPEC@1.0.0`  
> Goal：Issue #31  
> Pull Request：#32  
> Mode：`SHADOW`  
> Release Effect：`NONBLOCKING_SHADOW`  
> Human UAT：`REQUIRED`

## 1. 目标

该 Runtime 在 Human UAT 之前，以版本化 Synthetic User Profile、ExperienceEnvironment 和 Experience Oracle 驱动真实 Playwright Journey，生成可审计、可重放的体验证据。

它回答：

- 用户能否发现并完成目标；
- 产品是否给出可观察反馈；
- 状态、筛选和恢复是否符合预期；
- 键盘与语义可访问性是否支持关键任务；
- AI 诊断是否有证据且保持非阻断。

它不替代产品负责人或真实用户 UAT。

## 2. 执行链

```text
Campaign Plan
→ Profile / Environment / Journey Catalog
→ Pinned Target Materialization
→ Real Playwright Interaction
→ Semantic State / Screenshot / Trace
→ Deterministic Evaluation
→ Nonblocking AI Candidate Findings
→ JSON / Markdown Report
→ Artifact Manifest
→ Independent Replay
```

## 3. 当前四条 Journey

| Journey | Profile | 关键验收 |
|---|---|---|
| `novice-add-task` | Novice | 发现入口、提交任务、列表与剩余计数反馈 |
| `returning-filter-persistence` | Returning | 完成任务、筛选、刷新后状态和路由保持 |
| `keyboard-primary` | Keyboard-oriented | 不依赖指针完成主任务、焦点和语义名称有效 |
| `interrupted-resume` | Interrupted | 刷新中断后任务和可见状态恢复 |

每条 Journey 使用独立 Browser Context 和 Synthetic Fixture，不使用生产账号或个人数据。

## 4. 证据

每个 Journey 生成：

- Interaction Event Stream；
- Before / After Semantic State Hash；
- Playwright Trace；
- Final Screenshot；
- Semantic Accessibility Snapshot；
- Checkpoint Results；
- UX Metrics；
- Deterministic Evaluation；
- AI Candidate Findings。

Campaign 生成：

- `report.json`；
- `report.md`；
- `artifact-manifest.json`；
- `replay-manifest.json`；
- Target stdout / stderr。

## 5. 权限与裁决边界

```text
AI Candidate Finding
≠ Experience Oracle
≠ Blocker
≠ Release Verdict
```

当前 Runtime 强制：

- Campaign 只能使用 `SHADOW`；
- Release Effect 固定为 `NONBLOCKING_SHADOW`；
- Human UAT 固定为 `REQUIRED`；
- Actor Input 不包含 evaluator-only 字段；
- 生产账号和敏感 Persona 字段在模型校验阶段拒绝；
- AI Finding 的 `blocking` 固定为 `false`；
- 输入、Manifest、Artifact 或 Replay 被篡改时返回 `INVALID`，不能假绿。

## 6. CLI

```bash
test-workflow ux validate benchmarks/ux/ux0/campaign.yaml

test-workflow ux run benchmarks/ux/ux0/campaign.yaml \
  --workspace .target-work/ux0 \
  --output test-results/ux0

test-workflow ux replay test-results/ux0 \
  --workspace .target-work/ux0-replay
```

SHADOW Journey 的体验 FAIL 会写入报告，但不声称阻断 Release。输入或证据无效时 CLI 返回非零。

## 7. 当前验证事实

```text
Focused Runtime Gate：Run #16 / 30991412463 — SUCCESS
Unit / Contract：9 / 9 PASS
CLI Contract Validation：PASS
Real Playwright Journeys：4 / 4 PASS
Independent Replay：PASS
Campaign Verdict：PASS
Runtime Mode：SHADOW
Release Effect：NONBLOCKING_SHADOW
Human UAT：REQUIRED
Full Repository CI：Run #125 / 30991412405 — SUCCESS
```

证据：

```text
Artifact ID：8924285005
Artifact ZIP Digest：sha256:349f51fa11cca5c5f83bee863c69b289b19eebc63bfabe6c5623399b8254a3fc
Semantic Digest：sha256:1dda03adfcc3a264240b20a883daf2a230e3ce6dcd00c43dccfb84da40b885c5
Artifact Manifest Digest：sha256:702fdce96eedbb8b81566dda08768d33434346a7edf88653594587f676c92fa4
Manifest Files：19
```

## 8. 尚未证明

本模块没有完成：

- 缺失反馈、状态丢失、键盘障碍和恢复失败的 UX Mutation Proof；
- False-positive / False-negative Benchmark；
- 真实 LLM Provider 的诊断一致性；
- 跨项目、移动端、小程序或真实设备体验执行；
- Advisory 或 Blocking Gate。

因此下一节点是 TodoMVC UX Mutation Proof，而不是直接把 SHADOW 晋升为 Blocking。
