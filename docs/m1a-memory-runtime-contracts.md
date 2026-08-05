# M1A Governed Memory Runtime Contracts

> 状态：`MERGED / CLOSED`  
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

## 已交付实现

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

内存参考适配器只用于证明契约，不是 M1B 生产 Store。本模块没有选择数据库、Embedding、Ranking、索引或分布式一致性方案。

## 安全不变量

- Namespace 在 ACL 与相关性之前裁决；
- Namespace 不匹配时，即使显式 ALLOW 或高相关性也拒绝；
- Campaign、Agent、Shared 与委派范围必须精确匹配，过期委派立即拒绝；
- 显式 DENY 覆盖 Principal、Group 和 Role 的 ALLOW；
- Promotion 只表示进入声明的检索范围；
- State Event 不得修改 Revision 内容；
- Revision 与 Provenance 的嵌套 JSON 在创建后也不可原地修改；
- 所有 Revision 只能 Append；
- CAS 冲突不会改变 Head；
- Same key / same payload 返回原结果，same key / different payload 拒绝；
- Compatibility 的代码、Schema 与 Capability 版本范围必须真实执行；
- Promotion 的 Actor、Evidence 与 Benchmark 引用必须可解析并相互绑定；
- Forget 删除有效内容，仅保留不含原文的 Tombstone；
- Audit Event 不保存 Memory 内容，并形成可验证链。

## 最终证据

```text
Goal：Issue #43
Implementation PR：#44
Merge Commit：0585e357aebda650ee50ee95ff962b3ac81f6d4c
PR M1A Runtime Gate：31018116312 — SUCCESS
PR Full Repository CI：31018117595 — SUCCESS
PR UX0 Shadow：31018115286 — SUCCESS
PR UX1 Mutation Proof：31018115295 — SUCCESS
Main M1A Runtime Gate：31018460853 — SUCCESS
Main Full Repository CI：31018460602 — SUCCESS
Main UX0 Shadow：31018460951 — SUCCESS
Main UX1 Mutation Proof：31018460698 — SUCCESS
Release：31018460644 — SUCCESS
Cleanup：31018460853 / 31018460929 — SUCCESS
Focused Tests：29 / 29 PASS
Deterministic Proof：15 / 15 PASS
Critical False Green：0
Unauthorized Namespace Actions：0
Unauthorized Promotion Actions：0
Review Threads：0
Implementation Branch：DELETED
```

Artifact Manifest、独立 Replay、Tamper 拒绝、Python Distribution 与 GHCR Build 均已验证，详细证据见 `docs/m1a-memory-runtime-contracts-delivery-ledger.yaml`。

## 真实边界与下一模块

M1A Runtime Contracts 已达到 `CLOSED`，因此 **M1B Store & Progressive Retrieval SPEC** 解锁并成为下一主模块。

仍然成立：

- 当前没有生产 Memory Store；
- 尚未选定数据库、向量检索、Embedding、Ranking 或索引方案；
- M1 Memory Gate 仍为 OPEN；
- 阶段产品交付仍为 NOT_READY；
- 用户可见变化仍需要 Human UAT；
- M1B 实现必须等待自己的 SPEC 审批与合并。
