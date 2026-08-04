# Module 02 实施与验证报告：TodoMVC Mutation 测试证明

> 状态：`VERIFIED`，尚未合并  
> 分支：`agent/todomvc-mutation-proof`  
> PR：#9  
> 验证流水线：GitHub Actions Run #23

## 1. 模块目标

验证回归代码不仅能够在正常版本上通过，而且能够稳定发现目标业务缺陷，并在恢复原始代码后重新通过。

最终状态机：

```text
Baseline GREEN × 3
→ Mutation RED × 5
→ 每次恢复文件并校验 SHA-256
→ Restored GREEN × 3
→ Mutation Score = 100%
→ Critical False Green = 0
```

## 2. 已实现能力

- `MutationProofPlan`：声明固定目标、回归命令、稳定运行次数和 Mutation 集；
- `TextMutation`：要求目标文本精确匹配一次，限制路径不能逃出目标目录；
- Mutation 应用和恢复的 SHA-256 校验；
- Baseline、Mutation、Restored 三阶段确定性执行；
- 每次执行独立启动固定目标服务；
- 每次执行生成 JUnit、stdout、stderr、Playwright 失败证据和目标进程日志；
- 结构化 `proof-report.json` 和可读 `proof-report.md`；
- CI 质量门禁：存在任一 Survived Mutation、Baseline 失败或 Restored 失败时退出非零。

## 3. 回归代码覆盖

`tests/regression/test_todomvc_business.py` 覆盖四类业务行为：

1. 空白事项不得创建，正常标题需要去除首尾空格；
2. Active / Completed 筛选与剩余数量正确；
3. Clear completed 只能删除已完成事项；
4. 新增事项刷新后仍然存在。

## 4. 缺陷注入

| Mutation | 业务风险 | 结果 |
|---|---|---|
| `allow-blank-item` | 空白事项被创建且标题未 Trim | `KILLED` |
| `reverse-filters` | Active 与 Completed 语义反转 | `KILLED` |
| `count-completed-as-active` | 剩余数量把已完成事项计入 | `KILLED` |
| `clear-active-instead-of-completed` | 清理完成项时误删未完成事项 | `KILLED` |
| `disable-persistence` | 页面显示成功但刷新后数据丢失 | `KILLED` |

所有 Mutation 均标记为 Critical。

## 5. 远端验证结果

固定目标版本：

```text
percy/example-todomvc
4a2344b2207a72c680e5c559c72617498fb5b75b
```

实际结果：

```text
Baseline：3 / 3 PASS
Mutation：5 / 5 KILLED
Restored：3 / 3 PASS
Mutation Score：100%
Critical False Green：0
最终状态：PASSED
```

每个 Mutation 执行后，`dist/bundle.js` 的恢复 SHA-256 都与应用 Mutation 前一致：

```text
da0c2047d16173b16769d9b84aea5797116ec57e64f6aef87904f531b5085415
```

## 6. 单元测试

新增单元测试覆盖：

- Mutation 精确应用和原样恢复；
- 找不到目标文本时拒绝执行；
- 目标文本出现多次时拒绝执行；
- 路径逃逸拒绝；
- No-op Mutation 拒绝；
- 重复 Mutation ID 拒绝；
- False Green 在报告中显式暴露；
- 子进程使用当前 Python 解释器。

本地全量结果：

```text
37 passed, 6 skipped
```

## 7. 当前边界

本模块使用人工编写的确定性业务回归和 Mutation Plan，尚未实现：

- AI 从粗糙需求自动生成业务理解；
- AI 自动生成 TestSpec；
- AI 自动生成回归代码；
- AI 根据业务风险自动设计 Mutation；
- 失败后的证据诊断与安全修复。

这些能力将在后续模块中建立，但其输出必须继续经过本模块的确定性证明 Gate。
