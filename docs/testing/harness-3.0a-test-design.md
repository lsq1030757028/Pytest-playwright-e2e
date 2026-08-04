# 3.0A Capability Contracts 测试设计

## 目标

证明 Harness 的跨模块协议具备严格 Schema、稳定序列化、安全默认值和可追踪执行链，避免后续模块通过非结构化字典或对话记忆传递状态。

## 测试层级

- 单元测试：字段约束、状态不变量、权限和上下文安全、重试规则、时间与哈希格式。
- 阶段集成：从版本化 Descriptor、Request、Result Golden Asset 恢复一条完整执行链。
- 回归资产：`tests/assets/harness/3.0a/`，长期保留并按 Schema Version 演进。

## 关键风险

| 风险 | 测试 |
|---|---|
| Capability 名称或版本不可解析 | 非法名称与 SemVer 拒绝 |
| 同一输入被重复引用 | 重复 Artifact ID 拒绝 |
| 路径逃逸或过宽权限 | `..` 与危险 wildcard 拒绝 |
| SUCCESS 携带 blocker/error | Result 状态不变量 |
| 时间不可审计 | naive datetime 拒绝 |
| 协议升级破坏旧资产 | Golden JSON round-trip |

## Gate

```text
Unit Contracts PASS
→ Golden Assets PASS
→ Full Existing CI PASS
→ 3.0A VERIFIED
```
