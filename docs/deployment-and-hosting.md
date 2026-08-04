# 部署与托管

## 托管边界

- GitHub 私有仓库是唯一代码事实源；
- `main` 是可发布分支；
- GitHub Actions 保存 Python Distribution 与测试证据；
- GitHub Container Registry 保存可执行 CLI 镜像；
- 版本 Tag `v*` 同时创建 GitHub Release。

## 发布产物

1. `dist/*.whl` 与 `dist/*.tar.gz`；
2. `ghcr.io/lsq1030757028/pytest-playwright-e2e:main`；
3. Commit SHA 镜像标签；
4. 版本 Tag 镜像与 GitHub Release；
5. CI 上传的 JUnit、Replay、浏览器和 Mutation 证据。

## 容器运行

```bash
docker run --rm ghcr.io/lsq1030757028/pytest-playwright-e2e:main --help
```

需要测试外部项目时，将项目、输出目录和必要配置以只读/可写卷显式挂载。镜像默认使用非 root `pwuser`。

## 发布 Gate

只有 Consolidation PR 的完整 CI、Ledger 校验和所有阶段集成通过后才合并。合并后 `release-test-harness` 自动构建并推送镜像；若仓库未授予 Packages Write 权限，Release Job 会明确失败并在台账中标记基础设施阻塞，不会伪造发布成功。
