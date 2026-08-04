# 3.0C Policy、Budget 与 Permission 测试设计

## 目标

验证 Harness 在 Capability 执行前通过确定性规则拒绝越权、上下文升级和资源超支，且拒绝决策可审计。

## 单元测试

- 精确 Scope 与尾部 Prefix Scope；
- 缺失读写、执行和网络权限；
- 模型、浏览器和子进程显式授权；
- Context `METADATA → DEEP` 越级拒绝；
- Secret 权限；
- Capability 引用不一致；
- Budget 累计、剩余计算与原子拒绝；
- Timeout 大于 Wall-time Budget。

## 集成测试

```text
Descriptor + Request
→ PolicyEngine
→ ALLOW + Audit Event
→ BudgetAccount.consume
→ Remaining Budget
```

Golden Asset：`tests/assets/harness/3.0c/`。
