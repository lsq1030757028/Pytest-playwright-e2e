# Module 3.0B：Capability Registry 与 Artifact Store

> 状态：IMPLEMENTED，等待独立 CI 验证

## 交付

- Capability 名称/版本注册、精确解析和最新稳定版本解析；
- 重复注册与缺失能力的显式错误；
- `InMemoryArtifactStore`；
- `FileArtifactStore` 原子写、重启恢复与内容哈希验证；
- Artifact 不可变和幂等重复写；
- `StoreExecutionContext` 统一 Artifact 读写和 Event 收集。

## 边界

Store 不修改既有 Artifact。相同 ID、相同内容可以幂等复用；相同 ID、不同内容必须拒绝。文件内容或索引被修改时读取失败，不能静默信任损坏证据。
