# Stage 6：证据诊断与有限安全修复

## 状态

`IMPLEMENTED`，等待最终集成 CI。

## 能力

- 规则优先分类 Environment、Requirement Conflict、Test Defect、Product Defect、Flaky 和 Unknown；
- 独立 State Probe 与确认 Oracle 冲突时判定产品缺陷；
- 只有 Locator、同步、Fixture、测试数据、清理和语法问题允许候选修复；
- 禁止修改生产文件、删除断言、修改 Oracle、增加固定 sleep 或重试；
- 修复候选必须先复现失败，再应用补丁并重跑；未修复成功时自动恢复原文件。
