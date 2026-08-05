# UX0 Synthetic User Agent Test Design

> Goal：Issue #29  
> SPEC：`SPEC-UX0-SYNTHETIC-USER@1.0.0`  
> Mandate：`MANDATE-AUTONOMY-M1-M3@1.0.0`  
> Assurance：SPEC `DEV3`

## 1. 测试目标

证明 Synthetic User 体系不会退化为“模型看截图后主观评论”，并且能在 Human UAT 前以可重放证据发现：

- Critical Journey 无法完成；
- Forbidden / Irreversible Outcome；
- 缺少反馈、错误恢复或状态持久化；
- Keyboard、Focus、Semantic Accessibility 阻塞；
- 反复、回退、死路和异常摩擦；
- AI 误报、漏报和越权晋升。

## 2. 主要失败模式

| ID | 失败模式 | 结果 |
|---|---|---|
| UX-T01 | Agent 只叙述假想操作 | 无真实边界证据 |
| UX-T02 | AI 主观意见直接 Block | 大量误报、阻塞交付 |
| UX-T03 | Experience Oracle 泄漏给 Actor | Agent 作弊通过 Journey |
| UX-T04 | 相似 Persona 使用敏感人口属性 | 歧视和不可信模拟 |
| UX-T05 | Trace / Screenshot 与状态不一致 | 证据不可审计 |
| UX-T06 | Journey 完成但关键反馈缺失 | UAT 才发现用户不确定 |
| UX-T07 | Keyboard / Focus 无法完成任务 | 可访问性阻塞 |
| UX-T08 | Refresh / Interruption 丢状态 | 恢复性缺陷 |
| UX-T09 | Network Failure 后无法恢复 | 异常体验缺陷 |
| UX-T10 | Step Budget 被随意设定 | 正常流程被误判 |
| UX-T11 | Blocking 模式无 Benchmark 晋升 | 不成熟 Gate 阻断发布 |
| UX-T12 | Human UAT 被标记为不需要 | 合成用户越权替代真实验收 |
| UX-T13 | UX Finding 修改 Oracle/Requirement | 主观意见改变产品真相 |
| UX-T14 | 全量 Journey 每个 PR 都跑 | 成本失控、反馈过慢 |

## 3. SPEC 阶段义务

- ExperienceEnvironment 字段、Pin、Hash 和敏感属性禁令；
- Experience Oracle 与 Actor 输入隔离；
- SyntheticUserAgent Capability / Permission / Side-effect Contract；
- Interaction Event 和 Deterministic Metric Contract；
- AI Candidate Finding 限权；
- E0—E4 和 Finding Lifecycle；
- UX0—UX3；
- SHADOW → ADVISORY → BLOCKING Promotion；
- PR / Stage / Nightly / Human UAT 节奏；
- TodoMVC Vertical Slice 和 Mutation Plan；
- TestSpec、Harness、Campaign、Memory、Regression 集成边界。

## 4. 实现阶段证据

### Contract / Unit

- Environment canonical hash；
- Persona / Journey schema；
- Forbidden sensitive fields；
- UX Level Router；
- Finding and Verdict precedence；
- AI self-promotion rejection；
- Replay manifest integrity。

### Boundary Integration

- Playwright real page actions；
- DOM / Accessibility Snapshot；
- Keyboard-only journey；
- Refresh / State Recovery；
- Network failure injection；
- Trace / Screenshot / State Hash correlation。

### Mutation Proof

```text
Normal PASS
→ Missing Feedback FAIL
→ Restore PASS

Normal PASS
→ Broken Focus FAIL
→ Restore PASS

Normal PASS
→ State Loss After Refresh FAIL
→ Restore PASS
```

### Benchmark

- Known-good UX variations must not create blockers；
- Known-bad mutations must be found；
- AI Candidate findings are compared with hidden evaluator labels；
- Blocking threshold is not enabled until acceptable false-positive / false-negative evidence exists。

## 5. Hidden Evaluator

Actor receives user goal, profile and visible UI only. It never receives：

- expected action sequence；
- target locator；
- mutation identity；
- scoring key；
- forbidden shortcut；
- hidden success state。

Evaluator independently reads Oracle and evidence bundle。

## 6. Initial Gate

SPEC PR only validates contracts and governance. It does not claim：

- Synthetic User Runtime exists；
- TodoMVC UX Proof exists；
- UX Gate can block；
- Human UAT is replaced。

## 7. Acceptance

```text
Machine SPEC Contract：PASS
Experience Environment Pins：complete
Evaluator Leakage：0
AI-only Blocker Paths：0
Sensitive Persona Fields：0
Blocking Before Benchmark：0
Human UAT Replaced：0
M1.0 / Existing Regression：PASS
```
