# AI Test Harness / Test Agent OS 实现状态

> 文档角色：项目状态单一事实源  
> 最近更新：2026-08-07  
> 当前状态：`FOUNDATION_BASELINE`  
> 阶段产品交付：`NOT_READY`  
> 当前里程碑：`M1 MEMORY_AND_CONTROLLED_EVOLUTION`  
> 已关闭主模块：`M1B STORE_AND_PROGRESSIVE_RETRIEVAL`  
> 当前主模块：`M1C MEMORY_FORMATION_SPEC`  
> 当前主模块阶段：`SPEC_NEXT`  
> UX Gate：`SHADOW_NONBLOCKING`  
> Human UAT：`REQUIRED`  
> 当前自治授权：`MANDATE-AUTONOMY-M1-M3@1.0.0 ACTIVE`

---

## 1. 状态结论

```text
M0 Harness Baseline：MERGED / CLOSED
M1.0 Memory Benchmark Harness：MERGED / CLOSED
M1A Memory Contracts & Namespaces：MERGED / CLOSED
M1A Runtime Contracts：MERGED / CLOSED
M1B Store & Progressive Retrieval：MERGED / CLOSED
M1C Memory Formation：NEXT / SPEC
M1D Shared Memory Governance：PLANNED
M1E Controlled Evolution：PLANNED
M1F Memory Gate：PLANNED
M1 Memory Gate：OPEN (0 / 1)
Stage Delivery：NOT_READY
```

M1B 已从“Memory 规则”推进到真实可运行的持久化与检索系统：SQLite WAL Primary Store、Hot/Warm/Cold Progressive Retrieval、派生索引、Primary Revalidation、Outbox Recovery、Index Rebuild、Replay/Tamper、Migration/Rollback 和 Benchmark 均已进入 `main` 并完成主干与发布验证。

这不等于 M1 Memory 已完成。M1C Formation、M1D Shared Governance、M1E Controlled Evolution 和 M1F Memory Gate 尚未关闭，因此 Memory Gate 继续保持 `OPEN`，阶段产品仍为 `NOT_READY`。

---

## 2. 当前推进链

```mermaid
flowchart LR
    A[✅ M0 Harness Baseline]
    --> B[✅ M1.0 Memory Benchmark]
    --> C[✅ M1A Memory Contracts]
    --> D[✅ M1A Runtime Contracts]
    --> E[✅ M1B Durable Store / Retrieval]
    --> F[🟡 M1C Memory Formation SPEC]
    --> G[⬜ M1D Shared Governance]
    --> H[⬜ M1E Controlled Evolution]
    --> I[⬜ M1F Memory Gate]
```

Memory 仍是当前产品主执行路径。Beta、UX 扩展和其它横向能力不得阻塞 M1C—M1F 的 Memory 主线。

---

## 3. M1B 已交付能力

### 3.1 Durable Primary Store

- SQLite WAL 作为可替换 Reference Profile 的权威 Primary Store；
- `synchronous=FULL`、事务写锁、Head CAS 和跨进程重启恢复；
- Revision、Head、Lifecycle、ACL、Audit、Idempotency、Tombstone、Invalidation、Outbox 持久化；
- 继续复用 M1A 已证明的权限、生命周期、Provenance、Compatibility 和 Forget 语义，而不是在存储层重写业务规则；
- Forget 会物理删除 Primary Revision 内容和可恢复内容的 Idempotency 结果，只保留必要 Tombstone / Audit / State 证据；
- 两个独立 Store 对同一 Head 竞争时，只允许一个 CAS Winner。

### 3.2 Authority-first Progressive Retrieval

- Hot / Warm / Cold 默认预算分别为 `24/6/2000/250ms`、`96/12/6000/1000ms`、`256/20/12000/3000ms`；
- ACL、Lifecycle、Retention、Forget 和 Compatibility 在 Keyword / Metadata / Vector / Graph 相关性之前执行；
- Exact Ref、Metadata、Keyword、Archive 已有确定性 Reference Channel；Vector / Graph 保持可替换 Adapter，不可用时显式 `DEGRADED`；
- Weighted RRF + 确定性 Tie-break；
- 每个结果在释放 Content 前再次向 Primary Store Revalidate；
- Cursor 绑定 Actor、Namespace、Read Mode、Primary/Index Snapshot、ACL Epoch、Forget Epoch 和算法版本并进行完整性保护；
- Exact / Required Ref 不受 256 条广义 Candidate Window 截断，257 条规模回归已证明 Exact Ref Recall 与 Precedence。

### 3.3 Resilience / Replay / Migration / Benchmark

- Derived Index 健康检查、陈旧/损坏检测和从 Primary + Outbox 重建；
- Outbox Gap 检测与幂等恢复；
- Primary 不可用时 Fail Closed，禁止仅凭缓存/索引给出 authoritative 内容；
- Replay Manifest / Evidence Digest / Tamper Rejection；
- Migration 前后 Store Manifest 与 Shadow Retrieval 等价验证；
- 回滚不得复活 Target-only Forget；
- M1B Benchmark 验证 Unauthorized / Forgotten Release、Exact / Required Recall、Noncritical Recall / Precision、Replay、Deterministic Ordering 和 Latency；
- 100 次协调 CAS / Outbox 并发竞争全部证明单赢家，无双写静默覆盖。

---

## 4. M1B 权威交付事实

```text
SPEC Goal：Issue #62 — CLOSED
SPEC PR：#68 — MERGED
SPEC Merge：f0c25b75b9bd2308e862a7ce8ad7d8092de7091f

Implementation Goal：Issue #69 — CLOSURE_PENDING
I1 Primary Store PR：#70 — MERGED
I1 Merge：54da6db80a9e7d099a8acb27b031c62a9b484148
I2 Progressive Retrieval PR：#71 — MERGED
I2 Merge：517c4dc5ad3d0ccd72530dec80947774d5fb0e21
Exact-ref Correctness Repair PR：#73 — MERGED
Repair Merge：69b31907d48241b59f05d311030a69c33e2825b6
I3 Resilience PR：#72 — MERGED
Final Runtime Head：9600ed4924ddb8b8f76322f8547c4864e71b3e67

Main M1B Gate：31146450584 — SUCCESS
Main Full Quality：31146450631 — SUCCESS
Main Secret Scan：31146450593 — SUCCESS
Main CodeQL：31146450576 — SUCCESS
Release：31146450614 — SUCCESS
Cleanup Baseline Run：31146450571 — SUCCESS

Python Distribution Artifact：8981646972
Python Digest：sha256:1ae404deab52790a5f0fad0d8acc3b7b17c7c168afa30ebd030f2ca782b9b375
GHCR Build Record：8981662218
GHCR Build Record Digest：sha256:2d345a90028414febc44f55c35de0ce09f60f096d7238b87e11abba4f90c1eb3

Focused Tests：36 / 36 PASS
Coordinated CAS / Outbox Races：100 / 100 PASS
Critical Double Winners：0
Unauthorized Critical Release：0
Forgotten Content Release：0
Exact Ref Recall：100%
Required Authority Recall：100%
Deterministic Replay：100%
Review Threads：0
```

`Cleanup Baseline Run` 本身成功，但当时尚未登记 M1B 新增分支；本 Closure PR 将统一登记并在合并后验证实际分支清理，因此 Issue #69 只有在 Closure PR、主干检查和分支清理完成后才可正式关闭。

---

## 5. 当前主模块：M1C Memory Formation SPEC

M1C Goal：Issue #75。

目标不是让模型“自由记忆”，而是把真实工作过程形成可审计、可去重、可冲突隔离、可重放的 `CANDIDATE` Memory：

- Hot Path 只记录必须立即持久化的确认事实、显式决策、Blocker、Action/Result 和 Evidence；
- Background Formation 负责 Episodic / Semantic / Working Candidate 的提取、去重、冲突识别和受控压缩；
- 模型推导内容只能成为 `CANDIDATE`，不能直接变成 Fact、Oracle、Policy、Permission 或 Promoted Memory；
- 禁止持久化内部 Chain-of-Thought；
- 每条 Candidate 必须绑定 Source Ref、Source Hash、Formation Event、Actor、Namespace 和 Provenance；
- 重复输入必须 Idempotent，矛盾输入不得 Last-write-wins；
- 后台 Formation 中断后必须通过 M1B Durable Store 恢复而不重复接受 Revision；
- M1C 实现继续被 SPEC Approval Gate 阻塞。

---

## 6. 安全边界

`MANDATE-AUTONOMY-M1-M3@1.0.0` 继续覆盖 M1—M3 的 Goal、SPEC、实现、测试、Benchmark、Review、Merge、Release、Ledger 和 Cleanup。

仍禁止：生产/个人数据、Secret、破坏性生产迁移、不可逆外部动作、未经授权的 Oracle / Policy / Permission 修改、失败 Gate 绕过、直接 `main` 写入，以及把 Candidate Memory 自动提升为权威事实。

---

## 7. 近期执行顺序

```text
1. M1B Closure / Cleanup / Goal #69 CLOSE
2. M1C Memory Formation SPEC
3. M1C implementation / verification / closure
4. M1D Shared Memory Governance
5. M1E Controlled Evolution
6. M1F Memory Gate
```

---

## 8. M1 / Stage 交付条件

M1 只有在 M1C—M1F 全部关闭且完整 Memory Gate 通过后才可以标记 PASS。全局仍要求：Critical False Green 0、未授权 Oracle / Policy / Permission 修改 0、关键 Evidence 可重放率 100%、Memory Asset 可追溯且自动晋升资产可回滚。

阶段产品只有在 M1、M2、M3 与 Global Safety Gate 全部通过后，才可从 `FOUNDATION_BASELINE` 晋升。
