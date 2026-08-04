# Stage 7 测试设计

单元覆盖资产不可变、晋升门槛、L1/L2/L3 选测策略、关键漏选审计，以及 False Green 对 Benchmark 的一票否决。

阶段集成对 TodoMVC 清理与持久化两类关键变化选测，要求 Critical Recall 100%、Overall Recall 100%、False Green 0，并相对全量回归平均减少至少 70% 预计执行时间。

资产：`tests/assets/harness/stage-7/benchmark-golden.yaml`。
