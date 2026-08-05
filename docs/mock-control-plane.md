# Mock 与测试环境控制平面

## 目标

Mock 的目的不是绕开被测逻辑，而是消除被测逻辑之外的不可控性。系统将需求编译为三份相互约束的声明：

- `TestSpec`：测什么、什么算正确；
- `EnvironmentSpec`：如何构造确定性运行环境；
- `MockPlan`：哪些依赖必须真实、哪些允许控制或虚拟化。

## 真实性边界

```yaml
truth_boundary:
  must_be_real:
    - todo.create
    - todo.persist
  may_be_mocked:
    - browser.storage
    - system.clock
    - telemetry_service
```

任何 `must_be_real` 组件被设置为 `control` 或 `virtualize` 时，验证器直接拒绝 Replay Bundle。

## 已实现能力

### 数据与浏览器存储

`DataSeedSpec` 可以声明业务 Fixture 和浏览器 LocalStorage。`env build` 会编译出 Playwright `storage_state.json`。

### 时间与随机数

`EnvironmentSpec` 可以固定时间和随机种子。控制平面会生成 Playwright Init Script，重写 `Date.now()`、无参 `Date()` 和 `Math.random()`。

### 契约化服务虚拟化

`MockPlan` 中的虚拟服务必须绑定：

- JSON Schema 契约；
- 契约文件 SHA-256；
- 明确的行为文件。

`mock verify` 会校验契约哈希和每个路由的响应；`mock serve` 可以启动 FastAPI 虚拟服务，并暴露调用记录。

### 独立重放

Replay Manifest 固定所有输入文件哈希和执行命令。重放前会再次检查：

- TestSpec 与 MockPlan 的真实性边界一致；
- Mock 没有覆盖被测业务逻辑；
- 契约和行为未被篡改；
- 所有 Replay 输入文件与 Manifest 一致。

## 命令

```bash
uv run test-workflow spec validate experiments/todomvc-golden-loop/spec/test-spec.yaml
uv run test-workflow mock verify experiments/todomvc-golden-loop
uv run test-workflow env build experiments/todomvc-golden-loop
uv run test-workflow bundle validate experiments/todomvc-golden-loop
uv run test-workflow replay experiments/todomvc-golden-loop
```

## 当前实验

`experiments/todomvc-golden-loop` 使用一份故意不完整的 Todo 需求作为输入，记录事实、假设和风险，并构造：

- 固定时间和随机数；
- 两条确定性的 LocalStorage 初始数据；
- 一个契约化遥测虚拟服务；
- 一份哈希锁定的 Replay Manifest；
- 两条可独立重放的环境证明测试。

这一阶段验证的是“测试世界可以被声明、校验和重放”。下一阶段会将公开 TodoMVC 实现作为真实业务目标，生成并验证业务回归代码和 Mutation。
