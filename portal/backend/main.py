import sys
import os
import bcrypt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.database import engine, Base, SessionLocal
from app.core.security import hash_password
from app.api import auth, datasources, sync_tasks, dashboard, ds_proxy, notifications, component, workflow, system, metadata, project

# 创建表
Base.metadata.create_all(bind=engine)


def _migrate_sync_task_columns():
    """sync_task 表按需新增列（项目分组 / 字段映射 / DataWorks 高级参数）"""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sync_task'"
        )).fetchall()
        existing = {r[0] for r in rows}
        adds = [
            ("project_id",    "ALTER TABLE sync_task ADD COLUMN project_id BIGINT NULL COMMENT '所属项目'"),
            ("field_mapping", "ALTER TABLE sync_task ADD COLUMN field_mapping TEXT NULL COMMENT '字段映射JSON'"),
            ("where_clause",  "ALTER TABLE sync_task ADD COLUMN where_clause TEXT NULL COMMENT '源端WHERE过滤'"),
            ("split_pk",      "ALTER TABLE sync_task ADD COLUMN split_pk VARCHAR(128) NULL COMMENT 'DataX splitPk'"),
            ("write_mode",    "ALTER TABLE sync_task ADD COLUMN write_mode VARCHAR(32) DEFAULT 'insert' COMMENT '写入模式'"),
            ("pre_sql",       "ALTER TABLE sync_task ADD COLUMN pre_sql TEXT NULL COMMENT '导入前SQL JSON数组'"),
            ("post_sql",      "ALTER TABLE sync_task ADD COLUMN post_sql TEXT NULL COMMENT '导入后SQL JSON数组'"),
        ]
        for col, ddl in adds:
            if col not in existing:
                conn.execute(text(ddl))
                conn.commit()


_migrate_sync_task_columns()


# 确保管理员密码正确
def _ensure_admin():
    from app.models.user import SysUser
    db = SessionLocal()
    try:
        admin = db.query(SysUser).filter(SysUser.username == "admin").first()
        if admin:
            # 更新密码为正确的 bcrypt hash
            admin.password = hash_password("admin123")
            db.commit()
        else:
            admin = SysUser(
                username="admin",
                password=hash_password("admin123"),
                real_name="系统管理员",
                role="admin",
                status=1,
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()


def _ensure_default_project():
    from app.api.project import ensure_default_project
    db = SessionLocal()
    try:
        ensure_default_project(db)
    finally:
        db.close()


_ensure_admin()
_ensure_default_project()

app = FastAPI(
    title="数据中台 MVP",
    description="金融行业离线数据中台统一门户 API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(datasources.router, prefix="/api")
app.include_router(sync_tasks.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(ds_proxy.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(component.router, prefix="/api")
app.include_router(workflow.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(metadata.router, prefix="/api")
app.include_router(project.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "portal-backend"}
