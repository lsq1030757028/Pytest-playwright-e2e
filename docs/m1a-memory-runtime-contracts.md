# M1A Governed Memory Runtime Contracts

> 状态：`IMPLEMENTING`  
> Goal：Issue #43  
> SPEC：`SPEC-M1A-MEMORY-CONTRACTS-NAMESPACES@1.0.0`  
> Approval：`APPROVAL-M1A-MEMORY-CONTRACTS-NAMESPACES-SPEC@1.0.0`  
> Profile：`DEV3 / UX0`

## 业务目标

本模块把已批准的 Memory 规范变成可执行契约，确保未来无论采用文件、SQLite、PostgreSQL、Redis、文档、图或向量后端，都不能改变以下业务真相：

- 会话历史不会自动成为长期记忆；
- 项目、Agent、Campaign 与共享范围默认隔离；
- DENY 永远优先于 ALLOW，相关性和向量相似度不能授予权限；
- Candidate Memory 不能直接晋升，也不能成为 Fact、Oracle、Policy 或 Permission；
- 所有 Revision、来源、证据、状态变化和冲突都有稳定身份与可验证 Hash；
- 陈旧并发写入必须产生 Conflict，禁止最后写入静默覆盖；
- 过期、撤销和遗忘后的内容不能继续有效读取；
- Procedural 与 Skill Memory 不能成为无限制代码执行通道。

## 当前实现边界

已实现的运行时组件：

```text
Frozen Domain Models
→ Canonical Serialization / SHA-256
→ Namespace Boundary
→ ACL Decision
→ Lifecycle / Promotion Decision
→ Effective Read / Compatibility Filter
→ CAS / Idempotency / Conflict
→ Audit Chain
→ Revoke / Expire / Forget Tombstone
→ Vendor-neutral Ports
→ Deterministic In-memory Reference Adapter
→ Proof / Manifest / Independent Replay
```

内存参考适配器只用于证明契约，不是 M1B 生产 Store。当前模块不选择数据库、Embedding、Ranking、索引或分布式一致性方案。

## 安全不变量

- Namespace 在 ACL 与相关性之前裁决；
- Namespace 不匹配时，即使显式 ALLOW 或高相关性也拒绝；
- 显式 DENY 覆盖 Principal、Group 和 Role 的 ALLOW；
- Promotion 只表示进入声明的检索范围；
- State Event 不得修改 Revision 内容；
- 所有 Revision 只能 Append；
- CAS 冲突不会改变 Head；
- Same key / same payload 返回原结果，same key / different payload 拒绝；
- Forget 删除有效内容，仅保留不含原文的 Tombstone；
- Audit Event 不保存 Memory 内容，并形成可验证链。

## 证据

专用 GitHub Action 执行：

- 领域模型、Hash、Namespace、ACL、Lifecycle、Promotion 与 Compatibility Unit/Contract；
- 参考适配器真实 write/read/transition/query/conflict/revoke/forget Integration；
- 十项确定性 Runtime Contract Proof；
- Artifact Manifest、独立 Replay 与 Tamper 拒绝；
- 全仓库回归。

## 完成边界

达到 `CLOSED` 还需要：专用门禁和全量 CI 通过、Review Thread 为 0、合并到 `main`、Python/GHCR 发布成功、证据台账更新和实现分支清理。

完成后只会解锁 **M1B Store & Progressive Retrieval SPEC**；不会关闭 M1 Memory Gate，也不会把阶段产品标记为 Ready。
