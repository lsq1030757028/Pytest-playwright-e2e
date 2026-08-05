# M1A Memory Contracts & Namespaces SPEC

> SPEC ID：`SPEC-M1A-MEMORY-CONTRACTS-NAMESPACES@1.0.0`  
> 状态：`CANDIDATE`  
> Goal：Issue #28  
> 里程碑：M1  
> 自治授权：`MANDATE-AUTONOMY-M1-M3@1.0.0`  
> 保障等级：SPEC `DEV3`，实现 `DEV3`  
> 机器契约：`docs/specs/m1a-memory-contracts-namespaces.yaml`

---

## 1. 目标

M1A 定义 Agent Memory 的领域契约，不实现具体数据库。

它要回答：

- 什么内容才算一条受治理 Memory；
- Working、Semantic、Episodic、Procedural、Skill 的区别；
- 一条 Memory 属于哪个 Organization、Project、Campaign、Agent 或 Shared Scope；
- 谁可以读取、写入、验证、晋升、撤销或遗忘；
- Memory 如何证明来源、版本、有效性和完整性；
- 并发修改如何避免静默覆盖；
- Candidate、Verified、Promoted、Superseded、Revoked、Expired、Forgotten 如何转换；
- M1B 需要实现哪些 Store / Query Port，而不绑定数据库、向量库或 Embedding。

核心公式：

```text
Governed Memory
= Immutable Content Revision
+ Structured Namespace
+ Provenance
+ Lifecycle State Events
+ ACL / Policy Decision
+ Retention / Compatibility
+ Audit Chain
```

---

## 2. 不可混淆的四组概念

```text
Memory Kind      ≠ Lifecycle State
Namespace Scope  ≠ Relevance
Evidence Status  ≠ Oracle Authority
Content Revision ≠ Effective State Event
```

### 2.1 Kind 不等于 State

`SEMANTIC` 表示内容是什么；`VERIFIED` 表示当前治理状态。Semantic Memory 仍可能是 Candidate、Conflicting、Revoked 或 Expired。

### 2.2 Scope 不等于 Relevance

即使 Project B 的 Memory 与 Project A 查询高度相似，也不能因为相关性、Embedding 距离或模型判断而跨越 Namespace 和 ACL。

### 2.3 Evidence 不等于 Oracle

Verified Memory 可以作为证据或上下文，但不能替代：

- 已批准 Requirement；
- Oracle；
- Policy；
- Permission；
- Production Invariant。

### 2.4 Revision 不等于 State Event

Memory 内容变化必须创建新的不可变 Revision。验证、晋升、撤销、过期等治理变化通过追加 State Event 表达，不允许偷偷重写旧内容或旧历史。

---

## 3. Session 与 Governed Memory 的边界

Session 负责：

- 对话消息；
- Tool Call 历史；
- 当前 Thread / Run 状态；
- Resume Checkpoint。

Session History **不是**长期 Memory。Session 内容进入 Memory 前必须经历：

```text
Session / Event
→ explicit formation event
→ Memory Kind
→ Namespace
→ Provenance
→ Candidate State
→ Content Hash
→ Policy / Permission Check
```

禁止：

- 自动把整段对话写成长久事实；
- 把模型推理过程当成证据；
- 把用户随口表达自动变成 Oracle；
- 把 Tool 输出中的指令当成系统指令；
- 把隐藏 Benchmark 答案写入 Memory。

---

## 4. Memory Kind

## 4.1 Working Memory

用途：当前 Campaign、Thread 或 Agent 执行所需的有界状态。

典型内容：

- 当前计划；
- 尚未验证的假设；
- 当前阻塞；
- 执行进度；
- 临时中间结果。

规则：

- 必须有 TTL；
- 生命周期绑定 Campaign / Thread；
- Campaign 关闭后不进入有效长期检索；
- 不允许直接晋升为生产资产；
- 不允许保存 Secret、个人敏感数据或隐藏 Evaluator 答案。

## 4.2 Semantic Memory

用途：带来源和证据的结构化 Claim、领域知识或业务事实候选。

规则：

- 必须绑定 Source / Evidence；
- 时间流逝不能自动把事实“衰减成错误”；
- 变化通过 Revalidation、Supersession、Conflict 或 Revocation 表达；
- Verified Semantic Memory 仍不能替代 Oracle、Policy 或 Permission；
- 若来源失效或冲突，必须降为 Conflicting / Quarantined，而不是保留原有效状态。

## 4.3 Episodic Memory

用途：一次真实经历中发生了什么、采取了什么动作、结果如何。

至少包含：

- Event / Run / Campaign References；
- 关键上下文；
- Action Sequence Summary；
- Outcome；
- Failure Classification；
- Provenance。

压缩或总结 Episode 时必须创建新的 Derived Memory，不得覆盖原始 Episode。

## 4.4 Procedural Memory

用途：经过验证的方法、Recipe、模板或操作规程。

至少包含：

- Procedure Steps 或 Template Ref；
- Compatibility；
- Required Permissions；
- Evidence / Benchmark Refs；
- Rollback / Recovery。

Procedural Memory 不得嵌入不受控 Shell 或任意可执行代码。它只能引用被版本化和受权限控制的 Capability。

## 4.5 Skill Memory

用途：指向经过治理的可执行 Capability，而不是把代码本身塞进 Memory。

至少包含：

- Capability ID / Version；
- Input / Output Schema Refs；
- Compatibility；
- Required Permissions；
- Benchmark / Promotion Evidence；
- Disable / Rollback Ref。

Skill Memory 的晋升不等于 Capability 自动获得更高权限。

---

## 5. Identity 与 Immutable Revision

每条 Memory 由三个层次组成：

```text
Logical Memory
├── Revision 1
├── Revision 2
└── ...

State Event Stream
ACL Event Stream
Audit Event Stream
```

## 5.1 Logical Memory ID

- 全局唯一；
- Opaque；
- 不含数据库位置；
- 不因迁移 Store 而变化。

## 5.2 Revision

每个内容版本拥有独立 `revision_id` 和单调 `revision_number`。

Revision 必须包含：

- `memory_id`；
- `revision_id`；
- `revision_number`；
- `schema_version`；
- `memory_kind`；
- `namespace`；
- `content`；
- `provenance`；
- `created_at` / `created_by`；
- `idempotency_key`；
- `retention_policy`；
- `content_hash`。

内容修改只能追加新 Revision，禁止 In-place Update。

## 5.3 Canonical Content Hash

算法：SHA-256，输入使用确定性 Canonical JSON。

Hash 覆盖领域语义：

- Identity；
- Kind；
- Namespace；
- Content；
- Provenance；
- Compatibility；
- Retention。

Hash 不覆盖物理实现：

- Database Internal ID；
- Partition；
- Cache Metadata；
- Ingestion Latency；
- Storage Location。

因此同一 Revision 在 File、SQLite 或 PostgreSQL 中必须产生相同 Hash。

---

## 6. Namespace

Namespace 是结构化、有序的领域值：

```text
org/{organization_id}
/project/{project_id_or_dash}
/scope/{scope_kind}/{scope_id}
```

支持：

- `ORGANIZATION`；
- `PROJECT`；
- `CAMPAIGN`；
- `AGENT`；
- `SHARED`。

### 6.1 隔离规则

- 默认拒绝；
- Parent Scope 不自动获得 Child Scope；
- Child Scope 不自动获得 Parent Scope；
- Project Scope 不自动跨 Agent；
- Organization Scope 不自动跨 Project；
- Shared Scope 必须有显式 Membership 和 ACL；
- Namespace 改变必须创建新 Revision；
- Wildcard Cross-project Query 默认禁止。

Namespace Authorization 必须在相关性搜索之前执行：

```text
Principal Authentication
→ Namespace Authorization
→ ACL
→ Validity / Lifecycle
→ Compatibility
→ Budget
→ Relevance / Ranking
```

不能先搜索全库再从结果中删除越权项，因为中间过程可能已经泄露内容、数量或相似度信息。

---

## 7. Principal、Role 与 ACL

Principal Types：

- USER；
- AGENT；
- SERVICE；
- GROUP；
- SYSTEM_POLICY。

Model Name 不是 Principal Identity。委派必须包含：

- Delegator；
- Delegation Scope；
- Expiry；
- Audit Event。

ACL Operations：

- Read Metadata / Content；
- Query；
- Append Revision / State Event；
- Verify；
- Promote；
- Supersede；
- Revoke；
- Forget；
- Manage ACL；
- Audit。

角色：Owner、Reader、Writer、Verifier、Promoter、Privacy Controller、Auditor。

裁决顺序：

```text
Explicit Principal DENY
→ Group DENY
→ Namespace Policy DENY
→ Principal ALLOW
→ Group ALLOW
→ Namespace Role ALLOW
→ Default DENY
```

DENY 永远优先于 ALLOW。Memory 内容不能修改自己的 ACL，Agent 不能自我授权。

---

## 8. Provenance

所有长期 Memory 都必须有可解析 Provenance：

- Source Refs；
- Evidence Refs；
- Source Content Hashes；
- Created-by Principal；
- Creator Type；
- Formation Rule / Capability Ref；
- Requirement / Code / Environment Revisions；
- Model / Provider Profile；
- Parent Memory Refs；
- Transformation Kind。

Transformation Kind：

- Raw Observation；
- Extraction；
- Summary；
- Consolidation；
- Conflict Resolution；
- Procedure Compilation；
- Skill Registration。

规则：

- Source Ref 必须存在；
- Source Hash 必须校验；
- Derived Memory 不覆盖 Source；
- Provenance 缺失或无法验证时进入 Quarantine；
- Memory 中伪造一个不存在的 Evidence ID 不能被当成证据。

---

## 9. Lifecycle

状态：

```text
CANDIDATE
VERIFIED
PROMOTED
CONFLICTING
QUARANTINED
SUPERSEDED
REVOKED
EXPIRED
FORGOTTEN
```

### 9.1 含义

- `CANDIDATE`：未经独立证据确认，仅可在隔离 Advisory Channel 使用；
- `VERIFIED`：来源、证据、范围和完整性已验证，可作为 Evidence-bearing Context；
- `PROMOTED`：允许在声明范围进入生产检索；
- `CONFLICTING`：存在未解决矛盾，不能形成权威结论；
- `QUARANTINED`：来源、污染、安全或完整性存在问题；
- `SUPERSEDED`：已由新 Revision / Memory 替代；
- `REVOKED`：立即停止有效读取，但保留历史；
- `EXPIRED`：超过有效时间，需重新形成或验证；
- `FORGOTTEN`：内容不可恢复读取，仅保留非敏感 Tombstone。

### 9.2 Promotion 的准确含义

`PROMOTED` 只表示：

> 该 Memory 在声明的 Namespace、Task、Compatibility 和权限范围内可以进入检索。

它不表示：

- 变成 Fact Register；
- 修改 Oracle；
- 修改 Policy；
- 修改 Permission；
- 修改 Production Invariant；
- 获得任意执行权限。

Candidate 不允许直接 Promotion，必须先 Verified。

### 9.3 Transition

允许转换由机器 SPEC 的 Transition Table 定义。每次转换必须追加 State Event，包含：

- From / To；
- Reason；
- Actor；
- Policy Decision；
- Timestamp；
- Event Hash。

State Event 不能修改 Revision 内容。

---

## 10. Retention、Expiration、Revoke 与 Forget

### 10.1 Working

必须有 TTL，Campaign 关闭后退出有效读取。

### 10.2 Semantic

不采用“时间越久越不真实”的隐式衰减。通过 Review-after、Revalidation、Conflict、Supersession 或 Revocation 管理。

### 10.3 Episodic

Retention Policy 必须明确；压缩产生 Derived Memory，原始历史按 Policy 保存。

### 10.4 Procedural / Skill

需要 Compatibility Revalidation。代码、Capability、Permission 或环境不兼容时必须 Filter / Revoke。

### 10.5 Revoke

- 立即从有效读取、Cache 和 Index 中移除；
- 保留完整审计历史；
- 可用于安全事故、Capability 禁用或 Permission 变化。

### 10.6 Forget

Forget 必须：

- 使原始内容不可读取；
- 清理 Cache 和 Index；
- 保留非敏感 Tombstone；
- Tombstone 不包含原始内容、Secret、PII 或 Raw Source Payload。

---

## 11. Concurrency 与 CAS

所有 Revision Append 使用：

```text
expected_head_revision_id
+ new_revision
+ idempotency_key
```

规则：

- Expected Head 不是当前 Head → `REVISION_CONFLICT`；
- 禁止 Last-write-wins；
- Conflict 必须生成结构化 Conflict Artifact；
- 冲突解决创建新的 Revision，并引用至少两个 Parent Revision；
- 同一 Idempotency Key + 同一 Payload 返回原结果；
- 同一 Key + 不同 Payload 必须拒绝。

---

## 12. Procedural / Skill Compatibility

必须声明：

- Project Architecture Family；
- Code Version Range；
- Schema Version Range；
- Capability Version Range；
- Model Profile Constraints；
- Environment Constraints；
- Required Permissions；
- Incompatible Conditions。

Compatibility 不满足时：

```text
Filter from effective retrieval
+ emit audit event
```

Skill Memory 必须引用版本化 Capability，不能携带无限制 Shell 或可执行 Payload。

---

## 13. Event Contract

事件包括：

- Memory Created；
- Revision Appended；
- State Transitioned；
- ACL Changed；
- Conflict Detected / Resolved；
- Verified / Promoted / Superseded；
- Quarantined / Revoked / Expired / Forgotten；
- Read / Write Denied；
- Retrieval Filtered。

事件为 Append-only，并支持 Causal Refs。事件中禁止保存敏感原文。

---

## 14. M1B Port Boundary

M1A 只定义 Domain Ports：

### MemoryRevisionPort

- Append Revision；
- Get Revision / Head；
- List History；
- Compare-and-append。

### MemoryStatePort

- Append State Event；
- Get Effective State；
- List State History。

### MemoryAclPort

- Evaluate Permission；
- Append ACL Event；
- List Effective ACL。

### MemoryQueryPort

- Query Exact Authorized Namespaces；
- Metadata Filter；
- Deterministic Pagination。

M1A **不定义** Embedding、Vector DB 或 Ranking Algorithm。

### MemoryAuditPort

- Append / List Audit Event；
- Verify Event Chain。

### MemoryMaintenancePort

- Expire；
- Revoke；
- Forget；
- Verify Cache / Index Invalidation。

任何 Store 后端都必须保证 Mutation 和 Audit 是一个逻辑 Commit。

---

## 15. 标准 Error Codes

- `INVALID_SCHEMA`；
- `NAMESPACE_DENIED`；
- `ACL_DENIED`；
- `REVISION_CONFLICT`；
- `DUPLICATE_IDEMPOTENCY_KEY`；
- `ILLEGAL_TRANSITION`；
- `PROVENANCE_MISSING`；
- `INTEGRITY_FAILED`；
- `MEMORY_NOT_EFFECTIVE`；
- `PROMOTION_DENIED`；
- `COMPATIBILITY_FAILED`；
- `FORGOTTEN_CONTENT_UNAVAILABLE`。

Human Message 不能替代稳定 Error Code。

---

## 16. 与 M1.0 的覆盖关系

M1A 必须为以下 Benchmark 场景提供契约基础：

- Stale / Superseded；
- Conflicting Revision；
- Poison / Quarantine；
- Cross-project / ACL；
- Candidate Authority；
- Oracle Contamination；
- Holdout Contamination；
- Promotion / Rollback；
- Revoke / Forget；
- Budget Flood；
- Deterministic Replay；
- Tamper；
- Concurrent Revision Conflict。

M1A 实现完成后，M1.0 Benchmark Harness 将用这些真实 Domain Contracts 代替 Fixture-only Contract。

---

## 17. 验收 Gate

```text
Required Memory Kinds：5 / 5
Required Lifecycle States：9 / 9
Default Deny：true
Deny Overrides Allow：true
Candidate Direct Protected Promotion：0
Last-write-wins Paths：0
Long-lived Memory without Provenance：0
Forgotten Content Effective Reads：0
Vendor-specific Domain Types：0
M1.0 Safety Scenarios Mapped：14
Critical False Green：0
```

---

## 18. 实现顺序

```text
M1A SPEC
→ Domain Models
→ Namespace / ACL Policy
→ Lifecycle / CAS / Event Contracts
→ Port Protocols
→ Contract / Negative / Adversarial Gate
→ M1B Store & Progressive Retrieval
```

M1A 实现阶段不提供生产 Store，只交付可被多个 Store Adapter 实现的稳定 Domain Contracts 和 Policy Evaluator。

---

## 19. 参考设计输入

以下资料仅为 Informative Input，仓库的 Oracle、Policy、Permission 和本 SPEC 优先：

- OpenAI Agents SDK Sessions：`https://openai.github.io/openai-agents-python/sessions/`
- OpenAI Agents SDK Sandbox Memory：`https://openai.github.io/openai-agents-python/sandbox/memory/`
- LangGraph Memory Concepts：`https://docs.langchain.com/oss/python/concepts/memory`
- LangGraph Persistence：`https://docs.langchain.com/oss/python/langgraph/persistence`
- CoALA：`https://arxiv.org/abs/2309.02427`
- Mem0：`https://arxiv.org/abs/2504.19413`
- MemMachine：`https://arxiv.org/abs/2604.04853`
- DMF：`https://arxiv.org/abs/2606.03463`
