# 固定被测目标与 TodoMVC Product Adapter

## 模块目标

为后续业务测试生成、Mutation 和独立 Replay 提供一个真实、版本固定、可重复启动的开源被测目标。

## 固定目标

- Repository: `percy/example-todomvc`
- Revision: `4a2344b2207a72c680e5c559c72617498fb5b75b`
- License: MIT
- Manifest: `targets/percy-example-todomvc/target.yaml`

目标代码不直接复制进本仓库。`TargetManager` 使用无 Shell 的参数列表执行：

1. 克隆仓库；
2. Checkout 精确提交；
3. 校验 `HEAD`；
4. 校验关键文件；
5. 安装依赖；
6. 分配随机端口并启动；
7. 轮询健康地址；
8. 测试完成后关闭进程并保留日志。

## Product Adapter

`TodoMVCAdapter` 只控制业务前置数据和状态读取，不替换 TodoMVC 的创建、完成、筛选、持久化或清理逻辑。

支持：

- 将 Todo 数据编码为目标应用使用的 LocalStorage 格式；
- 检测重复 ID 和损坏数据；
- 在浏览器中造数并刷新；
- 读取真实 LocalStorage 状态；
- 清理测试数据。

## 单元测试

- Manifest 路径逃逸拒绝；
- 本地 Git Fixture 精确版本物化；
- 静态目标实际启动和健康检查；
- Revision 漂移拒绝；
- Todo 状态编码/解码；
- 重复 ID 和损坏 Storage 拒绝。

## 阶段集成测试

`tests/integration/test_todomvc_target.py` 在 GitHub Actions 中：

1. 克隆固定上游提交；
2. 安装并启动真实应用；
3. Product Adapter 造两条 Todo 数据；
4. 验证计数、Active 筛选；
5. 通过真实 UI 完成事项；
6. 从 LocalStorage State Probe 验证状态；
7. 通过真实 UI 清理已完成事项；
8. 验证最终数据为空。

该模块完成后，下一模块可以直接开始业务 TestSpec → Playwright 代码生成以及 Mutation 的 `GREEN → RED → GREEN`。
