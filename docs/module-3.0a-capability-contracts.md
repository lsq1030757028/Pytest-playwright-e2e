# Module 3.0A：Capability Contracts

> 状态：IMPLEMENTED，等待远端 CI 验证

## 交付

- `CapabilityDescriptor` 与语义版本引用；
- `CapabilityRequest` / `CapabilityResult`；
- `ArtifactRef` 与有效性状态；
- `ContextRequest` 四级渐进上下文；
- `ExecutionBudget`；
- `PermissionScope`；
- `RetryPolicy`、`ExecutionMetrics`、`DomainEvent`；
- `Capability` 与 `CapabilityExecutionContext` Protocol。

## 设计边界

- Capability 不接收可任意修改的全局 Campaign；
- 所有跨模块对象默认冻结并拒绝额外字段；
- 模型、浏览器、网络和子进程访问必须同时由 Descriptor 与 Permission 声明；
- Artifact 使用安全相对 ID、内容哈希、来源 Revision 和创建 Capability；
- Result 状态通过确定性不变量约束。

## 测试资产

`tests/assets/harness/3.0a/` 保存 Descriptor、Request、Result 和资产清单，作为后续 Registry、Orchestrator 与兼容性测试的固定输入。
