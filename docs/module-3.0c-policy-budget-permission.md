# Module 3.0C：Policy、Budget 与 Permission

> 状态：IMPLEMENTED，等待独立 CI 验证

## 交付

- `PermissionGuard`：读写、执行、网络、模型、浏览器、子进程和 Secret 权限；
- `PolicyEngine`：确定性 ALLOW / DENY 决策和审计事件；
- 上下文等级上限控制；
- Capability 引用一致性；
- 外部访问对应的最小 Budget；
- `BudgetAccount`：累计消耗、剩余预算和超限原子拒绝。

最终执行器必须先得到 `ALLOW`，不能依赖 Capability 自觉遵守权限或预算。
