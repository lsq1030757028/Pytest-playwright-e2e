# Stage 4：增量业务理解与损失场景

## 状态

`IMPLEMENTED`，等待最终集成 CI。

## 能力

- 只编译 Router 选中的局部业务范围；
- 资产、角色、状态转换、Fact、Assumption、Unknown；
- Production Invariant 与已知不变量优先；
- Loss Scenario 的资产、触发、失败模式、损失、恢复性和测试义务；
- Candidate → Supported → Reproduced → Proven → Controlled；
- P0 只有达到 E3/E4 才能阻断，E0/E1 只记录；
- Hidden Evaluator 检测 P0 漏报、缺失不变量和未经声明的 Oracle 假设。
