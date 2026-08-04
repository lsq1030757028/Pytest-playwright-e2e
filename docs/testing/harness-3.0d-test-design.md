# 3.0D Workflow Compiler / Orchestrator 测试设计

## 目标

证明 Workflow 是稳定编译出的 Capability DAG，而不是固定串行脚本；执行过程能够绑定上游 Artifact、暂停恢复、隔离失败并局部重置。

## 单元测试

- 未知依赖、循环依赖、自依赖和 Binding 泄漏拒绝；
- 稳定拓扑顺序与并行批次；
- 未注册 Capability 拒绝；
- 上游输出绑定到下游 Request；
- `max_nodes` 暂停与恢复不重复执行完成节点；
- 局部重置只影响选中节点及后代；
- 失败节点的后代跳过。

## 集成测试

```text
FileArtifactStore
→ seed node
→ checkpoint PAUSED
→ serialize checkpoint
→ reopen store
→ resume plan node
→ verify output and attempts
```

Golden Asset：`tests/assets/harness/3.0d/execution-plan.yaml`。
