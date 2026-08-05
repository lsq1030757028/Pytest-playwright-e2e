# UX0 Synthetic User Agent & Experience Acceptance Plane SPEC

> SPEC ID：`SPEC-UX0-SYNTHETIC-USER@1.0.0`  
> 状态：`CANDIDATE`  
> Goal：Issue #29  
> 范围：M1—M3 跨切面  
> 自治授权：`MANDATE-AUTONOMY-M1-M3@1.0.0`  
> 保障等级：SPEC `DEV3`，实现 `DEV3`  
> 机器契约：`docs/specs/ux0-synthetic-user-agent.yaml`

---

## 1. 为什么需要它

现有功能测试能回答“系统是否按规则运行”，但不能稳定回答：

- 用户是否能找到入口；
- 操作后是否知道发生了什么；
- 失败时是否知道如何恢复；
- 刷新、中断、网络异常后是否丢失状态；
- 键盘、缩放、屏幕阅读器语义下是否仍能完成任务；
- 流程是否需要异常多的返回、重复点击和猜测；
- 文案与实际结果是否一致。

这些问题通常会在真实 UAT 才暴露，返工成本高。UX0 将用户体验验收前移到 PR、Stage 和 Release Gate。

它的定位不是“AI 审美评分器”，而是：

```text
Experience Oracle
+ Synthetic User Profile
+ ExperienceEnvironment
+ Real Playwright Journey
+ Deterministic Telemetry
+ AI Candidate Findings
+ Evidence Gate
= UAT Readiness Evidence
```

---

## 2. 新的环境维度：ExperienceEnvironment

这里的“环境变量”不是一个普通字符串，而是一组必须被版本化、Hash 和重放的体验执行上下文：

```text
ExperienceEnvironment
├── persona_revision
├── journey_revision
├── device_profile
├── locale_timezone
├── network_profile
├── accessibility_context
├── prior_knowledge
├── account_and_data_state
├── requirement / design-system / code / fixture pins
└── random_seed / step / time / context budgets
```

### 2.1 Persona

Persona 只描述行为能力和使用情境：

- NOVICE；
- RETURNING；
- EXPERT；
- INTERRUPTED；
- Keyboard-only；
- Reduced-motion；
- 高缩放；
- 低带宽或间歇离线。

禁止推断或模拟真实用户的种族、宗教、健康、性取向、面部情绪等敏感属性。

### 2.2 Device / Locale / Network

体验环境必须固定：

- viewport、DPR、浏览器引擎；
- pointer、touch、keyboard；
- locale、timezone、数字/日期/货币格式；
- latency、带宽、离线窗口和故障注入；
- zoom、reduced-motion、focus、contrast 和语义可访问性要求。

### 2.3 Account / Data State

只允许使用受控 Synthetic Fixture，不允许真实客户账号、生产个人数据或 Secret。

---

## 3. SyntheticUserAgent

SyntheticUserAgent 是 Harness 管理的薄控制器，不是可以随意浏览和自由决定标准的大模型 Persona。

```text
ux.profile.resolve
→ ux.journey.compile
→ ux.environment.materialize
→ ux.execute.playwright
→ ux.observe.interaction
→ ux.observe.accessibility
→ ux.observe.feedback_and_recovery
→ ux.evaluate.deterministic
→ ux.evaluate.ai_proposal
→ ux.adjudicate.evidence_gate
→ ux.report
→ ux.replay
```

### 3.1 权限

允许：

- Synthetic Fixture 写入；
- Browser Session 状态；
- Screenshot、Trace、Video；
- DOM / Accessibility Snapshot；
- Evidence 和 Report。

禁止：

- 生产写入；
- Secret 和个人数据；
- 无限制网页探索；
- 无恢复路径的破坏性操作；
- 修改 Requirement、Oracle、Policy、Permission；
- 直接修改 Release Verdict。

### 3.2 Agent 与 Capability 的关系

Agent 负责组合和调度，Capability 负责可验证的单一能力。Capability 返回 Artifact、Event、Metrics 和 Finding Proposal，不能直接修改 Campaign 或 Release State。

---

## 4. Experience Oracle

每条 Journey 必须有显式 Experience Oracle：

- 用户目标和业务价值；
- Persona 能力假设；
- 起始状态与 Fixture；
- 必须经过的 Checkpoint；
- 可观察的成功结果；
- Forbidden Outcome；
- 关键操作后的反馈要求；
- Invalid Input、Network Failure、Interruption 的恢复要求；
- 权威 Step、Backtrack、Retry、Time Budget；
- Accessibility / Input Mode 义务；
- Evidence 要求和 Severity Floor；
- Requirement、Design System 和 Authority Revision。

“我觉得不好看”不能成为 Oracle。没有批准的 Design System 或 Requirement 支撑时，只能成为非阻断 Candidate Finding。

Evaluator-only 字段不能传给 Acting Agent，包括隐藏答案、推荐操作序列、Mutation 位置和评分 Key。

---

## 5. 可观察证据

### 5.1 Interaction Events

- Navigate；
- View Presented；
- Action Attempted / Succeeded / Failed；
- Feedback Observed；
- Focus Changed；
- Validation Error；
- Backtrack；
- Repeat Action；
- Dead End；
- Recovery Attempted / Succeeded；
- Journey Completed / Abandoned。

每个事件记录：

- Sequence；
- Semantic Target；
- Before / After State Hash；
- Observable Result；
- Screenshot / Trace / DOM / Accessibility Evidence Ref。

### 5.2 Deterministic Metrics

- Task / Checkpoint Completion；
- Step、Backtrack、Repeat、Retry、Dead-end；
- Recovery Success；
- Required Feedback Latency；
- Focus Order；
- Keyboard Completion；
- Viewport Overflow；
- Semantic Accessibility Failure；
- Unexpected State Loss。

禁止使用“推断用户情绪”或无证据的“满意度”作为指标。

---

## 6. AI 的职责

AI 可以：

- 解释可能的困惑文案；
- 发现入口、反馈、恢复和信息层级问题；
- 关联多个证据；
- 生成带引用的 Candidate Finding；
- 提出下一步验证建议。

AI 不可以：

- 自己标记 Blocker；
- 修改 Experience Oracle；
- 修改 Requirement；
- 降低 Evidence Threshold；
- 改变 Release State。

AI Finding 必须包含 Observation、Evidence、Oracle Clause、替代解释和不确定性。没有足够证据时保持 Candidate。

---

## 7. Evidence 与 Finding 生命周期

证据等级：

```text
E0 模型印象
E1 单次弱观察
E2 可重复 Telemetry / Accessibility Signal
E3 确定性 Journey + Trace / State / Screenshot
E4 独立 Replay / Mutation / Human-confirmed Benchmark
```

Finding：

```text
OBSERVED
→ SUPPORTED
→ REPRODUCED
→ PROVEN
→ CONTROLLED
```

AI 不得自行晋升 Finding。

---

## 8. UX Assurance Level

### UX0

无用户可感知变化，不需要 Synthetic Journey。

### UX1

普通用户可见变化：一个关键 Journey + 一个主 Persona。

### UX2

重要流程或规则变化：至少两个 Persona、两个 Input Mode、一个 Recovery Path，AI Critique 仅 Advisory。

### UX3

资金、鉴权、隐私、破坏性、不可逆、数据丢失和 Release-critical Journey：

- 多 Persona；
- Keyboard / Pointer；
- Recovery Matrix；
- Adversarial ExperienceEnvironment；
- 至少三次 Replay；
- 独立 Evidence Gate。

执行中只能自动升级。降级必须有显式证据。

---

## 9. Verdict

运行模式：

- SHADOW：不阻断，只产生报告；
- ADVISORY：失败形成 PR Warning；
- BLOCKING：满足 Benchmark 和 Policy Promotion 后才可使用。

Verdict：PASS、WARN、FAIL、INCONCLUSIVE、BLOCKED、INVALID。

优先级：

```text
Invalid Evidence
→ Forbidden Outcome
→ Critical Task Failure
→ Accessibility Task Block
→ Recovery Failure
→ Authoritative Friction Budget Failure
→ Nonblocking Candidate Findings
```

Blocking 规则：

- Critical Journey 无法完成：E3/E4 FAIL；
- Forbidden / Irreversible Outcome：E3/E4 FAIL；
- Accessibility 阻止完成任务：E3/E4 FAIL；
- 资金/鉴权/隐私/数据丢失歧义：E2 INCONCLUSIVE，E3/E4 FAIL；
- 文案、视觉偏好：默认 WARN，AI 单独不能阻断。

---

## 10. CI 节奏

### PR Fast Gate

- 只选受影响 Journey；
- 一个主 Profile；
- 确定性 Completion、Feedback、Focus 和 State Checks。

### Stage Gate

- Persona / Device / Locale / Input Matrix；
- Invalid Input、Network Failure、Interruption Recovery。

### Nightly / Release Gate

- Critical Journey Replay；
- Adversarial Environment；
- Stability 和 Baseline Comparison。

### Human UAT

Human UAT 仍然存在，但获得：

- 关键 Journey 结果；
- Screenshot / Trace；
- UX Candidate Findings；
- 已知风险；
- 未覆盖范围；
- 需要人工判断的设计问题。

---

## 11. 与现有系统集成

### TestSpec

增加：

- `experience_oracle_ref`；
- `journey_refs`；
- `ux_assurance_level`。

### Harness

增加 UX Capability Descriptor、ExperienceEnvironment Pin、Budget、Evidence 和 Event。

### Campaign

增加：

- `experience_environment_revision`；
- `ux_mode`；
- Persona / Journey Matrix。

### Memory

可以保存 Verified UX Finding 作为 Candidate 或 Evidence-bearing Memory；禁止 AI Finding 直接进入 Oracle、Policy 或 Permission。

### Regression

只有 PROVEN Finding、稳定重现、明确 Oracle 和可接受维护成本的 Journey 才能晋升为长期回归资产。

---

## 12. 初始 TodoMVC Vertical Slice

1. Novice 添加任务并看到可理解的持久化反馈；
2. Returning User 完成、筛选并保留状态；
3. Keyboard-only 完成主流程；
4. Interrupted User 刷新后恢复；
5. Missing Feedback、Broken Focus、Refresh State Loss、Misleading Count Mutation 必须触发失败；
6. Normal PASS → Mutation FAIL → Restore PASS；
7. AI Critique 可以发现问题，但不能改写 Deterministic Verdict。

---

## 13. Rollout

```text
SPEC
→ SHADOW Contracts / Runner
→ TodoMVC UX Mutation Proof
→ Advisory PR Gate
→ Blocking Candidate
```

Blocking 前必须满足：

- False-positive Benchmark；
- False-negative Mutation Proof；
- Independent Replay；
- Critical False Green = 0；
- Versioned Policy Event；
- Rollback Verified。

---

## 14. 验收 Gate

```text
ExperienceEnvironment Typed / Versioned / Hashable：true
Real Playwright Interaction：required
Evaluator Leakage：0
AI-only Blocker：0
Blocker without Oracle Clause：0
Blocker below E3：0
Sensitive Profile Inference：0
Production Personal Data Access：0
Replayable Critical Journeys：100%
Initial Mode：SHADOW
Human UAT Replaced：false
Critical False Green：0
```
