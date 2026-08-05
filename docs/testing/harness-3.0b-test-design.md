# 3.0B Registry 与 Artifact Store 测试设计

## 目标

验证 Capability 可按名称与语义版本稳定解析，Artifact 以不可变、内容寻址、可持久化和可篡改检测的方式管理。

## 单元测试

- 最新稳定 SemVer 解析；
- 重复注册和缺失版本拒绝；
- Descriptor 列表顺序稳定；
- 内存 Store 幂等写与不可变冲突；
- 文件 Store 重启恢复；
- 文件内容篡改检测；
- 缺失 Artifact 的专用错误。

## 集成测试

```text
register text.uppercase@1.0.0
→ persist TextInput
→ resolve capability
→ execute with StoreExecutionContext
→ persist TextOutput
→ reopen FileArtifactStore
→ verify output and event
```

## 测试资产

`tests/assets/harness/3.0b/asset-manifest.yaml` 记录集成场景中的输入和输出 Artifact，保留为回归资产。
