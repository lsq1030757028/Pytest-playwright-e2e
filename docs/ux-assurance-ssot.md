# UX Assurance SSOT

> 状态：`CANDIDATE`  
> 版本：`1.0`  
> SPEC：`SPEC-UX0-SYNTHETIC-USER@1.0.0`

本文件是 `docs/github-development-ssot.md` 的用户体验验收附加规范。它不替代功能正确性、安全、Memory、Mutation、Replay 或 Human UAT Gate。

## 1. 何时触发

任何以下变化都必须做 UX Triage：

- UI、交互、文案或反馈；
- 用户任务流程；
- 浏览器、移动端或设备入口；
- 业务规则导致可见行为变化；
- 错误、恢复、刷新、网络失败和中断；
- 资金、鉴权、隐私、破坏性和不可逆操作；
- Release / UAT Readiness。

## 2. PR 必填信息

- 是否有用户可感知变化；
- 受影响 Journey；
- UX0—UX3；
- Primary Persona；
- ExperienceEnvironment；
- Accessibility / Recovery Impact；
- 执行和跳过的体验证据；
- Human UAT 是否仍要求。

影响不明确时默认 UX2，不允许默认为“无影响”。

## 3. 正常链路

```text
Requirement / Diff
→ UX Triage
→ Experience Oracle
→ Affected Journey Selection
→ ExperienceEnvironment
→ SyntheticUserAgent Playwright Execution
→ Deterministic Evidence
→ AI Candidate Findings
→ Evidence Gate
→ Shadow / Advisory / Blocking Result
→ Human UAT Readiness Report
```

## 4. Gate 行为

- UX0：无用户可感知变化；
- UX1：一个关键 Journey；
- UX2：Persona / Input / Recovery Matrix；
- UX3：关键损失场景、多次 Replay、Adversarial Environment。

初始 Gate 永远是 SHADOW。SHADOW 失败不会阻断 PR，但必须出现在报告中。

## 5. AI 边界

AI 只能提出 Candidate Finding。以下行为被禁止：

- AI 单独标 Blocker；
- 修改 Oracle、Requirement、Policy 或 Permission；
- 用“感觉不好”代替证据；
- 推断敏感人口属性或情绪；
- 隐藏替代解释和不确定性。

## 6. Blocking 晋升

只有满足下列全部条件，才可通过版本化 Policy Event 把某类 UX Gate 晋升为 BLOCKING：

- False-positive Benchmark PASS；
- False-negative Mutation Proof PASS；
- Independent Replay PASS；
- Critical False Green = 0；
- Rollback Verified；
- 可解释的 Experience Oracle 和 Evidence Threshold。

## 7. Human UAT

Synthetic User 负责提前发现和整理问题；Human UAT 负责最终产品判断。UAT 报告必须明确：

- 已验证 Journey；
- Persona / Environment Matrix；
- 失败与 Candidate Finding；
- 未覆盖范围；
- 需要人工判断的设计问题；
- Replay、Trace 和 Screenshot 入口。
