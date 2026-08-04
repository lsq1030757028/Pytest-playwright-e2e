# Phase 1 实施与验证报告

## 本次范围

本次实现将 Mock 与造数据能力正式纳入 Replay Bundle，完成以下可运行模块：

- `TestSpec`：事实、假设、风险、场景、Oracle 和真实性边界；
- `EnvironmentSpec`：固定时间、随机数、真实服务、虚拟服务和数据入口；
- `MockPlan`：依赖决策、契约哈希和行为文件；
- `DataSeedSpec`：业务 Fixture 和浏览器 LocalStorage；
- `ReplayManifest`：命令、运行信息和全部输入文件 SHA-256；
- Environment Control Plane：编译 Playwright Storage State 和 Init Script；
- Contract-backed Virtual Service：按 YAML 行为启动 FastAPI Mock，并记录调用；
- Replay Bundle：校验、篡改检测和无模型独立重放。

## 安全约束

系统会拒绝：

- MockPlan 与 TestSpec 的真实性边界不一致；
- 对 `must_be_real` 业务组件执行 `control` 或 `virtualize`；
- 未声明在 `may_be_mocked` 中的 Mock；
- 虚拟服务缺少契约或行为文件；
- 契约文件 SHA-256 漂移；
- Mock 响应不符合 JSON Schema；
- Replay 输入文件在 Manifest 创建后被修改、删除或新增。

## TodoMVC Golden Bundle

`experiments/todomvc-golden-loop` 包含：

- 一份故意潦草的中文需求；
- 独立的事实、假设和风险清单；
- TestSpec；
- 固定到 `2026-08-04T20:00:00+08:00` 的时钟；
- 固定随机种子 `20260804`；
- 两条 LocalStorage 初始数据；
- 遥测服务 JSON Schema 与确定性 Mock；
- 哈希锁定的 Replay Manifest；
- 两条环境证明测试。

本 Bundle 当前用于验证“测试世界可声明、可构建、可校验、可独立重放”。公开 TodoMVC 实现的真实业务 E2E、AI 需求编译和 Mutation 验证属于下一阶段。

## 验证结果

执行：

```bash
PYTHONPATH=src python -m compileall -q src tests experiments/todomvc-golden-loop/generated
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m test_workflow.cli spec validate experiments/todomvc-golden-loop/spec/test-spec.yaml
PYTHONPATH=src python -m test_workflow.cli mock verify experiments/todomvc-golden-loop
PYTHONPATH=src python -m test_workflow.cli env build experiments/todomvc-golden-loop
PYTHONPATH=src python -m test_workflow.cli bundle validate experiments/todomvc-golden-loop
PYTHONPATH=src python -m test_workflow.cli replay experiments/todomvc-golden-loop
```

结果：

- 项目测试：`25 passed, 1 skipped`；
- Replay Bundle 测试：`2 passed`；
- TestSpec：有效；
- MockPlan：有效，无警告；
- Replay Bundle：哈希和契约校验通过；
- 独立 Replay：退出码 `0`；
- 篡改测试：能够检测 Seed 文件变化；
- 真实性边界测试：能够拒绝 Mock `todo.create`；
- 契约漂移测试：能够检测契约文件变化。

Live E2E 按原有策略在本地环境跳过，由 GitHub Actions 的允许网络环境执行。

## 下一阶段

1. 固定一个公开 TodoMVC 版本作为真实被测目标；
2. 实现 Requirement Intake 和事实/假设/风险编译器；
3. 从 TestSpec 生成 Pytest + Playwright 回归代码；
4. 对正常版本执行独立 Replay；
5. 注入空白事项、持久化、筛选和清理逻辑 Mutation；
6. 验证 `GREEN → RED → GREEN`；
7. 统计 Critical False Green 和 Mutation 检出率。
