# Stage 7：智能回归、资产晋升与 Benchmark

## 状态

`IMPLEMENTED`，等待最终集成 CI。

## 能力

- Candidate → Baseline Validated → Proof Verified → Regression → Deprecated；
- 未通过 Baseline、Mutation 或至少三次稳定重放的测试不能晋升；
- Requirement/Source/Domain 到 Test 的影响映射；
- L1 直接关联 + Smoke，L2 领域扩展，L3 强制 P0/P1；
- 显式审计遗漏的关键直接关联测试；
- Benchmark 输出 Critical Recall、Overall Recall、False Green 和执行时间缩减；
- 即使召回率为 100%，出现一个 False Green 仍判定失败。
