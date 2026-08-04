# Stage 6 测试设计

单元覆盖分类优先级、环境故障、需求冲突、Locator、Fixture、State Probe、Flaky 历史以及安全补丁拒绝规则。

阶段集成先运行一个 Locator 错误测试确认失败，规则诊断为可修复 Test Defect，应用受限 Locator 补丁后测试通过；断言和业务 Oracle 未改变。

资产：`tests/assets/harness/stage-6/repair-golden.yaml`。
