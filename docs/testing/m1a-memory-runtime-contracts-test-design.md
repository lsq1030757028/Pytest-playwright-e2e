# M1A Memory Runtime Contracts Test Design

## 1. Authority

- Goal：Issue #43
- SPEC：`SPEC-M1A-MEMORY-CONTRACTS-NAMESPACES@1.0.0`
- Approval：`APPROVAL-M1A-MEMORY-CONTRACTS-NAMESPACES-SPEC@1.0.0`
- Mandate：`MANDATE-AUTONOMY-M1-M3@1.0.0`
- Profile：`DEV3 / UX0`

测试 Oracle 来自已批准 SPEC。实现、测试和参考适配器不能修改 Oracle、Policy、Permission 或 M1 Memory Gate。

## 2. Test obligations

| Obligation | Failure mode | Evidence |
|---|---|---|
| Canonical Hash | Key 顺序或存储元数据改变业务 Hash | Unit + proof |
| Immutable Revision | 原 Revision 或嵌套 JSON 被原地修改 | Model validation + immutability proof + CAS integration |
| Session boundary | 原始会话自动成为 Memory | Required formation/provenance validation |
| Namespace isolation | 跨项目、Campaign、Agent、Shared 或委派范围泄漏 | Negative contract + proof |
| ACL precedence | ALLOW 绕过 DENY | Negative contract + proof |
| Provenance | 不可解析来源被当成可信 Memory | Reference adapter integration + proof |
| Lifecycle | Candidate 直接 Promoted 或 Forgotten 复活 | Transition contract + proof |
| Promotion | Actor 冒充、Evidence/Benchmark 未解析或 Memory 变成受保护权威 | Promotion contract + adversarial proof + scoped query integration |
| Retention | Expired/Revoked/Forgotten 仍可读取 | Integration + proof |
| CAS | 陈旧写入静默覆盖 Head | Conflict integration + proof |
| Idempotency | 同 Key 不同 Payload 被接受 | Negative integration + proof |
| Compatibility | 架构、代码、Schema、Capability、权限或环境不兼容的 Procedure/Skill 被执行 | Unit + effective-read filter + proof |
| Executable boundary | Skill 嵌入无限制脚本 | Adversarial validation + proof |
| Ports | 领域接口绑定具体数据库 | Runtime Protocol checks + source assertion |
| Audit | Mutation 成功但证据链断裂 | Audit-chain integration |
| Replay | 报告或 Manifest 被篡改仍通过 | Independent replay + tamper test |

## 3. Selected layers

- **Static/Lint**：类型、导入和代码质量；
- **Unit/Property-like**：Canonicalization、Hash、Value Object 和状态图；
- **Contract**：Namespace、ACL、Promotion、Compatibility 和 Ports；
- **Boundary Integration**：确定性内存参考适配器，观察真实状态变化；
- **Replay/Adversarial**：十五项 Proof、Manifest、独立重放和篡改拒绝；
- **Repository Regression**：保护现有 Harness、Memory Benchmark 和 UX 基线。

未选择数据库、网络或浏览器 Integration，因为本模块不实现这些边界。它们属于 M1B 或后续模块。

## 4. False-green controls

- 失败 Mutation 不得写入 Success Audit；
- ACL、Namespace、Promotion、CAS 和 Forget 均校验最终有效状态，而不仅检查返回文案；
- Proof 报告绑定 Semantic Digest；
- Manifest 绑定文件字节 Hash；
- Replay 使用独立进程重新执行场景；
- Tamper 测试必须导致 Replay Failed；
- Critical False Green 必须为 0。

## 5. Exit criteria

- Focused tests 全绿；
- Runtime Proof 10/10 PASS；
- Independent Replay PASS；
- Tamper rejection PASS；
- Unauthorized Namespace/Promotion 0；
- Stale overwrite 0；
- Forgotten content read 0；
- Full CI、Review、Main、Release、Ledger、Cleanup 全部成功。
