# Data Platform MVP · 数据中台

> 一个面向中小团队的轻量级一站式数据中台，覆盖数据集成、代码开发、调度编排、数据资产全链路。

---

## 功能截图概览

| 模块 | 说明 |
|---|---|
| 工作台 | 任务运行概览、调度日历、成功率趋势 |
| 数据集成 | 多数据源管理（MySQL），向导式离线同步任务，DataX 驱动 |
| 代码开发 | 多标签 SQL/Python/Shell IDE，Monaco Editor，带表名/字段智能补全 |
| 调度中心 | 基于 DolphinScheduler，工作流可视化，补数/重跑 |
| 数据资产 | 表资产、字段资产、数据血缘（OpenMetadata） |
| 系统监控 | 各服务健康状态、DS Worker 资源占用 |

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                         Browser                             │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP :80
                ┌──────────▼──────────┐
                │      Nginx          │  静态资源 + 反向代理
                └──┬───────┬──────────┘
          /api/*   │       │  /ds/* /om/*
     ┌─────────────▼─┐  ┌──▼──────────────┐
     │ Portal Backend │  │  DS / OM 透传   │
     │   FastAPI      │  └─────────────────┘
     └────┬──────┬────┘
          │      │
    ┌─────▼─┐ ┌──▼──────────────────┐
    │ MySQL │ │  DolphinScheduler   │──── DataX Jobs
    │  8.0  │ │  (调度 + 执行引擎)  │
    └───────┘ └─────────────────────┘
          │
    ┌─────▼─────────────┐
    │  OpenMetadata      │──── Elasticsearch
    │  (数据治理 / 血缘) │
    └───────────────────┘
          │
       Redis 7  (DS 分布式协调)
```

### 组件说明

| 组件 | 版本 | 职责 |
|---|---|---|
| **Vue 3** + Arco Design | Vue 3.x | 前端 SPA，组件库 |
| **Monaco Editor** | latest | 代码编辑器，SQL/Python/Shell 智能补全 |
| **FastAPI** | 0.100+ | Portal 后端 REST API，认证、元数据、同步任务管理 |
| **SQLAlchemy** | 2.x | ORM，MySQL 连接 |
| **MySQL 8.0** | 8.0 | Portal 元数据库 + DS 元数据库 + OpenMetadata |
| **Redis 7** | 7-alpine | DolphinScheduler 分布式锁/队列 |
| **DolphinScheduler** | 3.2.2 | 工作流调度引擎，内置 DataX 执行 |
| **DataX** | 3.x | 离线数据同步框架（阿里开源） |
| **OpenMetadata** | latest | 数据治理、血缘追踪 |
| **Elasticsearch** | 7.17 | OpenMetadata 搜索引擎依赖 |
| **Nginx** | 1.25 | 统一入口，静态文件服务 + API 反代 |
| **Docker Compose** | v2 | 一键编排所有服务 |

---

## 项目结构

```
data-platform-mvp/
├── docker-compose.yml          # 全局编排
├── docker/
│   ├── mysql/init.sql          # 数据库初始化
│   └── ds/Dockerfile           # DS + DataX 合并镜像
├── nginx/nginx.conf            # Nginx 路由配置
├── datax/                      # DataX 安装目录 + jobs
├── portal/
│   ├── backend/                # FastAPI 后端
│   │   ├── app/
│   │   │   ├── api/            # 路由（datasources/sync_tasks/components...）
│   │   │   ├── core/           # datax_builder, security, database
│   │   │   └── models/         # SQLAlchemy 模型
│   │   └── main.py
│   └── frontend/               # Vue 3 前端
│       └── src/
│           ├── views/          # 页面（SqlDev, SyncTask, Workflow...）
│           ├── components/     # 公共组件（CodeEditor, FieldMappingCanvas...）
│           ├── api/index.ts    # 所有接口封装
│           └── router/
└── scripts/                    # 运维脚本
```

---

## 快速部署

### 前置要求

- Docker 24+ & Docker Compose v2
- 服务器 ≥ 8 核 16 GB（DolphinScheduler + OpenMetadata + ES 较重）
- 开放端口：`80`（唯一对外端口）

### 一键启动

```bash
# 1. 克隆项目
git clone https://github.com/your-username/data-platform-mvp.git
cd data-platform-mvp

# 2. 复制并编辑环境变量
cp .env.example .env
# 修改 MYSQL_ROOT_PASSWORD / REDIS_PASSWORD / PORTAL_SECRET_KEY

# 3. 构建前端静态文件
docker compose build portal-frontend
docker compose run --rm portal-frontend

# 4. 启动所有服务（首次约需 3-5 分钟等待 DS/OM 就绪）
docker compose up -d

# 5. 访问
# 数据中台 Portal:  http://<your-ip>
# 默认账号:  admin / admin123
```

### 环境变量说明（.env）

```env
MYSQL_ROOT_PASSWORD=your_strong_password
REDIS_PASSWORD=your_redis_password
PORTAL_SECRET_KEY=your_jwt_secret_key_32chars+
```

---

## 核心功能说明

### 数据集成 · 离线同步

- 支持 MySQL 数据源，可视化字段映射（拖拽连线）
- 字段支持「常量」「调度变量」（如 `${bizdate}`）
- 一键生成并执行 `CREATE TABLE`（目标表不存在时）
- 生成标准 DataX JSON，由 DolphinScheduler 驱动执行
- 上线/下线状态锁定，防止运行中任务被误改

### 代码开发 · IDE

- SQL / Python / Shell 多语言多标签编辑器
- SQL 智能补全：关键字、函数（含窗口函数）、**表名**、**字段名**（联调后端元数据接口实时获取）
- 选中部分 SQL 单独执行，结果表格展示
- 文件夹树组织，最多三级嵌套
- 一键发布为「组件」供工作流复用

### 调度中心

- 基于 DolphinScheduler 3.2 standalone 模式
- 支持 DAG 工作流、定时 CRON、补数（历史日期批跑）、重跑
- 任务日志实时查看

### 数据资产

- 表级元数据浏览（行数、大小、注释）
- 字段资产搜索
- 数据血缘图谱（OpenMetadata）

---

## 设计取舍

| 决策 | 原因 |
|---|---|
| 单节点 DolphinScheduler standalone | 降低运维复杂度，适合中小团队；需高可用时可切换集群模式 |
| Portal 不引入 Redis | 当前无需分布式 Session，JWT 无状态已够用 |
| OpenMetadata 按需集成 | 血缘/治理功能渐进引入，不强依赖 |
| DataX 内置于 DS 容器 | 减少容器数量，DS 与 DataX 版本统一管理 |
| Nginx 唯一对外端口 | 安全隔离，所有内部服务不暴露端口 |

---

## License

MIT
