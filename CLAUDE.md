# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 开发命令

### 后端
```bash
cd portal/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 前端
```bash
cd portal/frontend
npm install
npm run dev   # 开发服务器 :5173，/api 代理到 :8000
npm run build # 生产构建
```

### 部署到测试服务器
```bash
# 必须在 test 分支上执行
cd ~/data-platform-test
bash scripts/deploy-to-test.sh
# 访问 http://192.168.1.3:8888
```

## 分支模型

| 分支 | 职责 |
|------|------|
| `main` | 纯净同步上游 `barryLiu199/data-platform-mvp`，不直接开发 |
| `dev` | 功能开发，只放通用功能代码，不放测试环境配置 |
| `test` | 测试环境部署验证，功能从 dev cherry-pick |
| `feature/` | 向上游贡献，必须基于 `upstream/main` |

- **test 不从 dev 合并**，只 cherry-pick 功能 commit
- 向上游发 PR 必须基于 `upstream/main`，不能基于 dev
- git 命令需要走本地代理：`git config http.proxy http://127.0.0.1:7890`

## 架构概览

### 整体结构

```
Browser → Nginx(:80) → portal-frontend (静态) + /api/* → portal-backend (FastAPI)
                                                              ↓
                                                    MySQL + DolphinScheduler
                                                              ↓
                                                    DataX Jobs (via DS SHELL节点)
```

### 后端关键设计

**无 Alembic 迁移**：数据库 schema 变更通过 `main.py` 中的 `_migrate_*()` 函数在启动时自动执行（`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`）。新增字段必须在这里加 migration 函数。

**DSL Translator**（`app/core/dsl_translator.py`）：Portal 的核心翻译层，把 Component（sql/python/shell/datax）和 Workflow DAG 翻译成 DolphinScheduler 原生 JSON。DataX 任务翻译为 DS SHELL 节点 + heredoc 临时 JSON，不使用 DS 原生 DataX 节点。

**DS Client**（`app/core/ds_client.py`）：封装对 DolphinScheduler REST API 的调用（创建/更新/发布/运行工作流）。

**API 层**（`app/api/`）：每个模块对应一个 FastAPI router，在 `main.py` 中统一注册。

### 前端关键设计

**`useFileTree.ts` composable**：类型颜色、渐变、缩写（SQ/PY/SH/DX）的单一来源，`SqlDev`、`DagNodePanel`、`DagCustomNode` 共用，不要在各组件里硬编码类型颜色。

**`LangIcon.vue`**：统一的类型徽章组件，从 `useFileTree` 读取配置，渐变背景 + 两字母缩写。

**`ContextMenu.vue`**：多级右键菜单，Teleport 挂载到 body，支持 hover 展开子菜单。

**DAG 画布**（`components/dag/`）：基于 Vue Flow，`DagCanvas.vue` 是主画布，`DagNodePanel.vue` 是左侧组件库，`DagCustomNode.vue` 是节点卡片，`DagContextMenu.vue` 是节点右键菜单。

**`vite.config.ts` 无 `resolve.alias`**：不能用 `@/` 路径别名，必须用相对路径（`../composables/useFileTree`）。

**SqlDev.vue 编辑注意**：Edit 工具在该文件上容易卡住，改用 Python 脚本（`python3 << 'EOF' ... EOF`）进行编辑。

### 组件类型

| type | 颜色 | 缩写 | 说明 |
|------|------|------|------|
| `sql` | 琥珀橙 `#D97706` | SQ | SQL 查询 |
| `python` | 蓝 `#3776AB` | PY | Python 脚本 |
| `shell` | 绿 `#4EAA25` | SH | Shell 脚本 |
| `datax` | 紫 `#7C3AED` | DX | DataX 同步 |
