# TodoMVC Mutation 测试证明

## 目标

本模块验证回归代码不是“稳定通过的脚本”，而是能够发现对应业务缺陷的可执行证明。

状态机：

```text
Baseline × 3：必须全部 PASS
→ 逐个注入业务 Mutation：每个必须 FAIL
→ 每次恢复目标文件并核对 SHA-256
→ Restored × 3：必须全部 PASS
→ Critical False Green 必须为 0
```

## 被测业务规则

正式回归代码位于 `tests/regression/test_todomvc_business.py`，覆盖：

- 空白事项不得创建，标题需要去除首尾空格；
- Active / Completed 筛选与剩余数量必须准确；
- Clear completed 只能删除已完成事项；
- 新增事项刷新后必须保留。

## Mutation 集

`proofs/todomvc/plan.yaml` 定义五个确定性文本 Mutation：

1. 绕过空白校验和 Trim；
2. 反转 Active / Completed 筛选；
3. 把总数显示为剩余数；
4. Clear completed 错删 Active；
5. 禁用 LocalStorage 持久化。

Mutation 只能在固定上游 Checkout 的临时工作区中执行。每个 Mutation 要求目标文本精确匹配一次，执行后无论测试结果如何都恢复原始内容，并重新验证文件哈希。

## 执行

```bash
uv run test-workflow proof validate proofs/todomvc/plan.yaml
uv run test-workflow proof run proofs/todomvc/plan.yaml \
  --workspace .target-work/todomvc-proof \
  --output test-results/todomvc-proof
```

输出：

- 每次目标进程的 stdout / stderr；
- 每次 Pytest 的 JUnit、stdout、stderr；
- Playwright 失败 Trace 与截图；
- `proof-report.json`；
- `proof-report.md`。

只有 Baseline、全部 Mutation、Restored 和 Critical False Green 四个 Gate 同时满足，最终状态才是 `passed`。
