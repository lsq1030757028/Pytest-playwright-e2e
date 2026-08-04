# Module 3.0E：Existing Capability Adapters

> 状态：IMPLEMENTED，等待独立 CI 验证

## 交付

- `spec.validate`：现有 TestSpec Loader；
- `target.validate`：现有 TargetManifest Loader；
- `test.run`：受控 Pytest 子进程和结构化结果；
- `proof.run`：现有 MutationProofRunner；
- `register_existing_capabilities`；
- L1 TodoMVC Harness Golden Gate。

## 最小路径证明

L1 Gate 同时验证 Spec 和 Target，再运行一条选定测试。`proof.run` 已注册但不进入 DAG，从而证明 Harness 可按 Assurance Profile 裁剪执行，而不是调用所有可用能力。
