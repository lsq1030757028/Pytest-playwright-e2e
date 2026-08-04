# Pytest + Skill + Playwright 测试工作流

这是一个可直接运行的测试工程 MVP，核心职责分工如下：

- **Skill**：定义测试流程、质量规则、证据要求、失败分类和安全边界。
- **Pytest**：负责 Fixture、参数化、Marker、执行编排和 JUnit 报告。
- **Playwright**：负责浏览器操作、语义化定位、自动等待、Trace、截图和视频。
- **Workflow CLI**：负责环境预检、受控执行、失败分类和质量门禁报告。

## 快速开始

```bash
uv sync --extra test
uv run playwright install chromium
uv run pytest tests/unit tests/api
uv run pytest tests/e2e -m "smoke or regression" \
  --browser chromium \
  --tracing retain-on-failure \
  --screenshot only-on-failure \
  --video retain-on-failure \
  --output test-results
```

## CLI

```bash
uv run test-workflow preflight --config config/local.yaml
uv run test-workflow run --config config/local.yaml --marker smoke --browser chromium
uv run test-workflow classify failure-evidence.json
uv run test-workflow report test-results/junit.xml --output test-results/report.md
```

## 测试分层

- `tests/unit`：配置、失败分类、报告等纯逻辑测试。
- `tests/api`：业务规则与接口边界测试。
- `tests/e2e`：页面对象、业务 Flow 和 Playwright 场景。
- `integration` Marker：浏览器调用真实服务的 Live E2E，仅在允许浏览器访问目标服务的环境执行。

默认 Smoke 使用真实页面结构与受控 API Double，保证本地和 PR 流水线稳定；GitHub Actions 另外执行 Live E2E，验证浏览器到后端服务的真实链路。

## 部署

- `Dockerfile`：Playwright 测试运行器镜像。
- `Dockerfile.demo`：示例服务镜像。
- `docker-compose.yml`：本地服务与测试运行器编排。
- `.github/workflows/publish-image.yml`：发布 Runner 和 Demo 镜像到 GHCR。
- `deploy/k8s/deployment.yaml`：Kubernetes Deployment 与 Service 示例。

## 关键质量约束

1. 不允许为了让流水线变绿而修改预期结果。
2. 产品缺陷、测试缺陷、环境缺陷和数据缺陷必须分开统计。
3. 浏览器失败必须保留 Trace、截图、控制台和失败请求证据。
4. 组合型业务规则优先放在单元/API 层，E2E 只保留关键用户链路。
5. 生产环境默认只读，破坏性操作必须显式授权。
