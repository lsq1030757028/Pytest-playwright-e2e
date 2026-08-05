# GitHub Agent 云端研发、发布与验证优化建议

> 状态：`PROPOSAL`  
> 日期：`2026-08-05`  
> 适用范围：本仓库外部开发 Agent、GitHub Actions、制品发布、部署与发布后验证  
> 本文性质：仅记录现状、风险和实施建议，不直接改变现有运行时、CI、发布或权限策略  
> 建议保障等级：本文档变更为 `DEV0`；后续涉及 CI、发布和部署的实现变更至少为 `DEV2`，涉及生产批准、Secret、自动合并或供应链控制时为 `DEV3`

---

## 1. 结论

当前仓库已经跑通一条可审计的 GitHub 云端研发闭环：

```text
用户通过 Chat 提出目标
→ 外部 GPT / Agent 读取仓库
→ 创建 Branch、Commit 和 Pull Request
→ GitHub Actions 执行编译、Pytest、Playwright、Replay 和 Mutation Proof
→ Workflow Artifact 保存 JUnit、Trace、截图、视频和构建产物
→ Agent 读取 Check、Job、日志和 Artifact 元数据
→ 修复并重新提交
→ 合并到 main
→ 构建 Python Distribution 和 GHCR 镜像
→ 验证主干、发布结果并清理临时分支
```

关键边界是：

- GPT / Agent 主要负责分析、计划、修改仓库、读取执行结果和作出下一步决策；
- GitHub 保存代码、PR、Review、Commit、Check、Artifact 和 Release 等权威事实；
- GitHub-hosted Runner 才是真正执行 Linux 命令、安装 Chromium、编译包、启动进程和运行 Playwright 的计算环境；
- 当前已实现自动构建和制品发布，但尚未实现到真实 Kubernetes 或云环境的持续部署与运行时验证。

因此，当前架构应被准确描述为：

```text
External Agent + GitHub Control Plane + GitHub Actions Execution Plane
```

而不是“Agent 自身长期运行在 GitHub Actions 中”。

---

## 2. 当前已验证能力

### 2.1 云端开发

- 通过 `AGENTS.md`、研发 SSOT、状态和路线文档加载仓库级上下文；
- 使用 GitHub Branch 隔离实现；
- 通过 Commit 保存增量修改；
- 通过 PR 保存 Goal、Scope、DEV Profile、Test Obligation、Evidence 和回滚方案；
- Agent 可通过 GitHub API 或等价工具读取 PR、Commit、Check、Job、Artifact 和评论，并继续修复。

### 2.2 云端执行与验证

当前 `ci.yml` 已执行：

- `uv sync --extra test`；
- Playwright Chromium 及系统依赖安装；
- Ruff；
- Pytest Collect；
- Unit / API；
- Harness 3.0A—3.0E；
- Stage 3—7；
- Requirement-to-Verdict；
- Ledger 和构建校验；
- Replay Bundle；
- Browser Smoke；
- Live Browser Integration；
- 固定版本 TodoMVC Target；
- Mutation Proof；
- JUnit、Trace、截图、视频、日志和 `dist` 上传。

### 2.3 自动发布

当前合并到 `main` 后能够：

- 构建 wheel 和 sdist；
- 上传 Python Distribution Artifact；
- 构建并推送 GHCR 镜像；
- 生成 `main`、Commit SHA 和版本 Tag；
- 对 `v*` Tag 创建 GitHub Release；
- 清理明确列入允许列表的历史实现分支。

---

## 3. 当前主要风险

## 3.1 P0：Release 与 Main CI 并行启动

`ci.yml` 和 `release.yml` 都监听 `main` push，因此合并后可能发生：

```text
main push
├─ Main CI
└─ Build & Publish
```

这不是严格的发布 Gate。若主干 CI 最终失败，镜像可能已经推送到 GHCR。

### 建议

改成：

```text
main push
→ Main CI
→ delivery-gate SUCCESS
→ Build once
→ Publish
```

可选实现：

1. 单一 Workflow 中使用 `needs`；
2. Release Workflow 使用 `workflow_run`，仅在指定 Main CI 成功后触发；
3. 使用可复用 Workflow，将构建和验证组合成不可绕过的 DAG。

### 验收标准

- Main CI 未成功时不得产生新的可消费镜像标签；
- 发布记录必须绑定通过验证的 Commit SHA；
- 失败主干不得进入 `PUBLISHED` 或 `CLOSED`。

---

## 3.2 P0：平台级合并保护不足或不可验证

仓库 SSOT 已定义禁止直接写 `main`、Required Check、Review 和 DEV3 人工批准，但当前规则主要由仓库文件和 Agent 自律表达。

当前仍需平台侧明确验证或补齐：

- Branch Protection / Ruleset；
- Required Status Checks；
- 禁止直接 push；
- DEV2 / DEV3 Reviewer 要求；
- Conversation Resolution；
- Force Push 和 Branch Delete 限制；
- 管理员是否允许绕过。

### 建议

为 `main` 建立平台级规则：

- Require pull request；
- Require `delivery-gate`；
- Require conversation resolution；
- 禁止 force push；
- DEV2 至少一名独立 Reviewer；
- DEV3 使用 GitHub Environment 或明确人工批准；
- Agent 不应同时充当实现者和唯一批准者。

### 验收标准

- 未通过 Required Check 的 PR 无法合并；
- 未满足批准规则的 DEV2 / DEV3 PR 无法合并；
- 直接写 `main` 被 GitHub 平台拒绝，而不只是被文档禁止。

---

## 3.3 P1：发布 Workflow 和镜像命名分裂

当前存在两套发布逻辑：

- `release.yml`：Python Distribution、主 Runner 镜像、GitHub Release；
- `publish-image.yml`：Runner 和 Demo 两类镜像。

同时存在多种镜像名称，而 Kubernetes Manifest 中的 Demo 镜像名称与 Workflow 产物不完全一致。

### 建议

统一为一个 canonical release pipeline：

```text
Build once
→ pytest-playwright-e2e-runner
→ pytest-playwright-e2e-demo
→ tag: sha-<commit>
→ optional mutable aliases: main / vX.Y.Z
→ record immutable digest
```

Kubernetes、Docker Compose、部署文档和 Ledger 都引用同一命名策略。

### 验收标准

- 同一个 Commit 只构建一次每类镜像；
- Runner、Demo、Kubernetes 和文档名称一致；
- 所有部署使用 Digest 或至少 Commit SHA Tag；
- Tag Workflow 不再重复构建同一产物。

---

## 3.4 P1：发布与部署状态混用

目前 GHCR 推送成功有时被表述为“部署完成”，但真实运行环境没有自动更新。

### 建议状态机

```text
BUILT
→ VERIFIED
→ PUBLISHED
→ DEPLOYED
→ RUNTIME_VERIFIED
→ CLOSED
```

定义：

- `BUILT`：构建成功；
- `VERIFIED`：构建产物通过对应证据；
- `PUBLISHED`：上传到 GHCR / Release；
- `DEPLOYED`：目标环境已运行该不可变版本；
- `RUNTIME_VERIFIED`：Smoke / Probe / Canary 成功；
- `CLOSED`：Ledger、回滚和清理全部完成。

### 验收标准

- 仅推镜像不得标记 `DEPLOYED`；
- PR、Release 和 Ledger 可追踪到具体环境和镜像 Digest；
- 运行时验证失败时状态停留在 `DEPLOYED` 或 `BLOCKED`，不得 `CLOSED`。

---

## 3.5 P1：缺少真实环境持续部署与发布后验证

仓库已有 Kubernetes Manifest，但仍需人工替换镜像名称并执行 `kubectl apply`。

### 建议

新增环境化部署流程：

```text
Publish immutable image
→ Deploy to staging GitHub Environment
→ readiness / liveness
→ CLI smoke
→ Browser smoke
→ Canary observation
→ optional production approval
→ deploy production
→ runtime verification
```

要求：

- 使用 GitHub Environment 保存审批和环境记录；
- 优先使用 OIDC 或短期凭证，不保存长期云密钥；
- 部署引用镜像 Digest；
- 自动生成回滚命令和上一版本引用；
- Production、Secret、真实设备或不可逆资源按 `DEV3` 处理。

---

## 3.6 P1：证据只保留 30 天

PR 和 Run ID 会长期存在，但 JUnit、Trace、视频和完整 Artifact 到期后无法继续审计或重放。

### 建议

将证据分层：

- 临时诊断证据：30 天；
- Release Evidence：随 GitHub Release 长期保存；
- Replay / Golden / Mutation Plan：版本化进入仓库；
- Evidence Index：写入 Ledger，记录 Run ID、Artifact ID、SHA-256、适用 Requirement 和失效状态；
- 高风险 DEV3 证据：进入长期对象存储或合规存档。

### 验收标准

- Release 关闭后仍能找到关键证据摘要和 Digest；
- Replay 所需固定输入不依赖即将过期的 Artifact；
- 证据失效、被替代或要求重跑时在 Ledger 中显式标记。

---

## 3.7 P2：CI 为单个大型串行 Job

当前所有检查集中在一个 `quality` Job 中，优点是简单，缺点是反馈慢、无法并行、失败重跑粒度大。

### 建议 DAG

```text
policy-static ─┐
unit-api ──────┤
harness ───────┤
replay-proof ──┤→ evidence-summary → delivery-gate
browser ───────┤
build ─────────┘
```

要求：

- 每个 Job 上传独立证据；
- `evidence-summary` 汇总结果和 Artifact Digest；
- `delivery-gate` 是唯一 Required Check；
- 变更特定 Evidence 与仓库回归仍保持分离；
- 未来可在可信 Change Map 成熟后做选择性回归，但不得静默降低保障级别。

---

## 3.8 P2：分支清理依赖硬编码允许列表

当前清理 Workflow 只删除预先写入数组的分支。

### 建议

- 开启 GitHub 原生 `delete_branch_on_merge`；或
- 根据合并 PR 的 Head Ref 精确删除；
- 保护 `main`、Dependabot、长期 Release 和 Experiment 分支；
- 不枚举并删除任意未合并分支。

### 验收标准

- 已合并临时 Agent 分支自动清理；
- 未合并、受保护或仍被其他 PR 依赖的分支不会删除；
- 清理动作在 PR 或 Ledger 中可追踪。

---

## 3.9 P2：供应链完整性仍可加强

### 建议

- GitHub Actions 使用 Commit SHA 固定第三方 Action，而不是只固定 major Tag；
- 生成 SBOM；
- 对镜像和 Python Distribution 生成 Provenance；
- 使用 Sigstore / Cosign 或 GitHub Artifact Attestation；
- 增加依赖和镜像漏洞扫描；
- 将构建 Digest、源码 Commit、Workflow Run 和 Release 相互绑定；
- 严格最小化 Workflow `permissions`。

---

## 4. 推荐目标架构

```text
┌───────────────────────────────┐
│ User Goal / Approved Issue    │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ External GPT / Coding Agent   │
│ Plan / Edit / Commit / PR     │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ GitHub PR Control Plane       │
│ Scope / Review / Policy       │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ GitHub Actions Execution      │
│ Static / Unit / Integration   │
│ Browser / Replay / Mutation   │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ Evidence Summary              │
│ JUnit / Trace / Video / Hash  │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ Required delivery-gate        │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ Merge + Main Verification     │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ Build Once / Sign / Publish   │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ GitHub Environment Deployment │
│ Staging → Approval → Prod     │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ Smoke / Probe / Canary        │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ Ledger / Release / Closure    │
└───────────────────────────────┘
```

---

## 5. 分阶段实施顺序

## Phase 1：发布安全基线

优先级：`P0`

- Release 必须依赖 Main CI；
- 建立唯一 `delivery-gate`；
- 验证或配置 `main` Branch Protection；
- 明确 DEV2 / DEV3 Reviewer 和批准要求。

完成条件：失败主干无法发布，未满足平台 Gate 的 PR 无法合并。

## Phase 2：统一制品和状态模型

优先级：`P1`

- 合并两套发布 Workflow；
- 统一 Runner / Demo / K8s 镜像命名；
- 使用 Commit SHA 和 Digest；
- 引入 `BUILT → VERIFIED → PUBLISHED → DEPLOYED → RUNTIME_VERIFIED`。

完成条件：同一 Commit 的制品、Tag、Digest、Release 和状态唯一可追踪。

## Phase 3：真实环境部署闭环

优先级：`P1`

- 建立 Staging GitHub Environment；
- 自动部署 Kubernetes；
- 增加 readiness、CLI Smoke、Browser Smoke；
- 增加 Production 人工批准和回滚。

完成条件：系统能够证明某个 Digest 已在指定环境运行并通过运行时验证。

## Phase 4：效率和长期治理

优先级：`P2`

- 拆分并行 CI；
- Evidence Summary 和长期索引；
- 自动安全分支清理；
- SBOM、签名、Provenance 和漏洞扫描；
- 根据可信 Change Map 逐步引入选择性回归。

---

## 6. 后续实施的 DEV Profile 建议

| 变更 | 最低建议 Profile | 说明 |
|---|---:|---|
| 将 CI 拆分为并行 Jobs | DEV2 | 改变 GitHub Actions 和回归 Gate |
| Release 依赖 Main CI | DEV2 | 改变制品发布顺序 |
| 合并镜像发布 Workflow | DEV2 | 改变构建和发布边界 |
| 配置 Branch Protection | DEV3 | 改变合并和发布控制面 |
| 新增 Staging 自动部署 | DEV2 | 新增真实环境边界 |
| 新增 Production 部署和批准 | DEV3 | 涉及生产权限、Secret 和 Release Gate |
| OIDC、签名、Provenance | DEV3 | 涉及供应链和权限边界 |
| Artifact 长期索引 | DEV2 | 改变证据和 Ledger 契约 |

每个后续 PR 应独立完成：

- Change Map；
- Test Obligation；
- 失败模式；
- 实际执行证据；
- 回滚方案；
- Main 和 Release 验证；
- Ledger 更新。

---

## 7. 本建议文档的完成边界

本文只完成：

- 当前 Agent、GitHub 和 GitHub Actions 职责边界说明；
- 已验证能力总结；
- 风险和优先级排序；
- 目标架构；
- 分阶段实施路线；
- 后续变更的 DEV Profile 建议。

本文不声称以下内容已经实现：

- Main CI 阻断发布；
- Branch Protection；
- 统一镜像 Workflow；
- Kubernetes 自动部署；
- Staging / Production GitHub Environment；
- Canary、签名、SBOM 或长期证据存储。

这些内容必须通过后续独立 PR、GitHub Actions 证据和发布后验证完成后，才能从 `PROPOSAL` 晋升为已实施状态。
