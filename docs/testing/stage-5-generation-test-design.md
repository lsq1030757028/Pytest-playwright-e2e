# Stage 5 测试设计

单元覆盖 TestSpec 编译、未知 Oracle Basis 拒绝、Requirement/Oracle 可追踪代码、代码 Hash、AST 安全规则和 Mutation 唯一匹配。

阶段集成生成免费时长 120 秒边界测试：正常实现 PASS，`<=` 改为 `<` 后 FAIL，恢复后 PASS，且源文件 Hash 一致。

资产：`tests/assets/harness/stage-5/generation-proof.yaml`。
