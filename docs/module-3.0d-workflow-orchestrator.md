# Module 3.0D：Workflow Compiler / Orchestrator

> 状态：IMPLEMENTED，等待独立 CI 验证

## 交付

- `ExecutionNode`、`NodeOutputBinding`、`ExecutionPlan`；
- DAG 校验、稳定拓扑顺序和并行批次；
- `WorkflowCompiler` 对 Registry 中精确 Capability 版本进行解析；
- `Orchestrator` 在 Policy Gate 后执行 Capability；
- 上游 Artifact 绑定、结果持久化校验和 Budget 结算；
- `ExecutionCheckpoint`、暂停和恢复；
- `reset_checkpoint` 局部重置节点及后代；
- 失败传播、后代跳过和事件去重。

## 边界

3.0D 只提供通用 DAG 执行。业务风险路由、Campaign 状态和需求变化影响图将在后续模块以 Capability 接入，不写死进 Orchestrator。
