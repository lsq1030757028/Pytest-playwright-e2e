# Stage 5：AI TestSpec、候选代码与证明 Gate

## 状态

`IMPLEMENTED`，等待最终集成 CI。

## 能力

- 模型输出必须通过现有 TestSpec Schema 和 Oracle 来源校验；
- CompiledSpec 绑定 Requirement Revision 与 Understanding Hash；
- 生成代码显式标注 Requirement 和 Oracle ID；
- AST 验证拒绝网络、sleep、exec/eval、常量断言和无断言测试；
- Candidate Proof Gate 对真实免费时长逻辑执行 Baseline、`<=`→`<` Mutation 和 Restored；
- 源文件必须恢复到原始 SHA-256。
