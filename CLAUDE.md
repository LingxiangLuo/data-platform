# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

数据中台门户，前端 Vue 3 + Arco Design，后端 FastAPI + SQLAlchemy，调度引擎对接 DolphinScheduler。

- 前端：`portal/frontend/` — Vite + Vue 3 + TypeScript + Arco Design
- 后端：`portal/backend/` — FastAPI + uvicorn，启动时自动执行 schema migration
- 部署：Docker Compose，nginx 统一入口（80 端口），内网测试服务器 `192.168.1.3`

## 常用命令

```bash
# 前端本地开发
cd portal/frontend && npm run dev

# 前端类型检查
cd portal/frontend && npx vue-tsc --noEmit

# 前端构建验证
cd portal/frontend && npx vite build

# 后端本地启动
cd portal/backend && uvicorn main:app --reload --port 8000

# 后端语法检查
cd portal/backend && find . -name "*.py" | xargs python -m py_compile

# 部署到测试服务器（内网 192.168.1.3）
bash scripts/deploy-to-test.sh

# 强制全量重建（依赖变化时）
bash scripts/deploy-to-test.sh --force
```

## 分支模型

```
upstream (barryLiu199/data-platform-mvp)
    │  CI 每 30 分钟自动同步
    ▼
  main  — 只读镜像，不直接提交，仅存放 .github/workflows/
    │  CI 自动 merge（无冲突时）
    ▼
   dev  — 唯一集成分支，所有功能在此汇聚，push 后自动部署测试环境
    ↑
 feature/xxx — 每个功能一个分支，PR 合并回 dev
```

**规则：**
- main 不直接提交，只有 CI 写入（upstream 同步 + 保留 .github/workflows/）
- dev 通过 PR 合并，不直接 push（紧急 hotfix 除外）
- feature/rbac-sso 分支存放未完成的 RBAC/SSO 功能，待后续继续开发
- 向上游贡献时，基于 upstream/main 创建 feature 分支，cherry-pick 通用功能 commit

## 功能开发流程

```bash
# 1. 从最新 dev 创建 feature 分支
git checkout dev && git pull origin dev
git checkout -b feature/xxx

# 2. 开发、小步提交
git add <files> && git commit -m "feat: xxx"

# 3. 推送并开 PR → dev
git push origin feature/xxx
gh pr create --base dev --title "feat: xxx"

# PR 合并后：CI 自动部署到测试服务器 → test-engineer 验证
```

## 向上游贡献

只贡献通用功能（对所有用户有价值，不含私有业务/测试环境配置）。

```bash
# 1. 基于 upstream/main 创建分支
git fetch upstream
git checkout -b feature/upstream-xxx upstream/main

# 2. cherry-pick 功能 commit（只挑功能，不挑部署/配置）
git cherry-pick <sha>

# 3. 向上游发 PR
git push origin feature/upstream-xxx
gh pr create --repo barryLiu199/data-platform-mvp --title "feat: xxx"
```

## CI/CD

三个工作流（均在 `.github/workflows/`，保存在 main 分支）：

| 文件 | 触发 | 运行环境 | 做什么 |
|------|------|----------|--------|
| `sync-upstream.yml` | 每 30 分钟 | ubuntu-latest | upstream → main → dev 自动同步 |
| `deploy-test.yml` | push dev | self-hosted (Mac) | rsync + docker compose 部署到测试服务器 |
| `pr-check.yml` | PR → dev | self-hosted (Mac) | 前端 tsc + build，后端语法检查 |

Self-hosted runner 运行在开发 Mac 上（launchd 开机自启），通过 SSH 内网直连测试服务器 `192.168.1.3`。

**Runner 管理：**
```bash
# 查看状态
cd ~/actions-runner && ./svc.sh status

# 启动 / 停止
cd ~/actions-runner && ./svc.sh start
cd ~/actions-runner && ./svc.sh stop

# 查看日志
tail -f ~/Library/Logs/actions.runner.LingxiangLuo-data-platform.mac-runner/Runner_*.log
```

**SSH 密钥：** `~/.ssh/test_server_key`（私钥，公钥已部署到 192.168.1.3）

## 代码审查

- 修改单函数/小 bug fix → `quick-code-reviewer`（主动触发，不等用户要求）
- 跨 3+ 文件 / 涉及 auth/权限/数据库模型 → `deep-code-reviewer`
- 合并前 / 发 PR 前 → `release-engineer`
- 部署后 → `test-engineer`

## 后端约定

- 数据库 migration 写在 `main.py` 的启动钩子里（`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`），不用 Alembic
- 新增 API 端点后需在 `main.py` 注册路由
- 权限控制：敏感端点叠加 `Depends(require_permission("xxx:yyy"))`，不改 `get_current_user`

## 前端约定

- API 函数统一在 `src/api/index.ts`，不在组件里直接 axios
- 路由定义在 `src/router/index.ts`，admin 子路由需加 `meta.permission`
- 组件库：Arco Design（`@arco-design/web-vue`），不引入其他 UI 库

## Git 代理

```bash
git config http.proxy http://127.0.0.1:7890
git config https.proxy http://127.0.0.1:7890
```

## GitHub 下载加速

下载 GitHub 资源（runner、release 附件等）时，在原始 URL 前加代理前缀：

```bash
curl -L -O "https://gh-proxy.com/https://github.com/user/repo/releases/download/v1.0/file.tar.gz"
```

备用节点：`https://v6.gh-proxy.org/`
