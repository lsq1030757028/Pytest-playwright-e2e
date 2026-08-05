# 3.0E Existing Capability Adapters 测试设计

## 目标

验证现有 TestSpec、Target、Pytest 和 Mutation Proof 能力可以通过统一 Harness 协议复用，并证明 L1 Workflow 只加载和执行最小充分节点。

## 单元测试

- `spec.validate` 复用 TestSpec Loader 并统计 Case / Oracle；
- `target.validate` 复用 TargetManifest Loader；
- `test.run` 只允许 `tests/` 内路径和有限 Pytest 参数；
- Selected Pytest 成功和路径越界拒绝；
- `proof.run` 使用可替换 Runner 并持久化结构化报告；
- Existing Capability Registry 完整性。

## 阶段集成

```text
SpecSource + TargetSource
→ [spec.validate || target.validate]
→ test.run selected asset
→ SUCCEEDED
```

L1 Gate 明确不加入 `proof.run`、浏览器探索或 Deep Context。测试资产登记于 `tests/assets/harness/3.0e/`。
