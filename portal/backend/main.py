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
from app.models.component_folder import ComponentFolder  # noqa: F401 — 确保 create_all 创建该表

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


def _migrate_component_columns():
    """component 表按需新增 folder_id 列"""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'component'"
        )).fetchall()
        existing = {r[0] for r in rows}
        if 'folder_id' not in existing:
            conn.execute(text(
                "ALTER TABLE component ADD COLUMN folder_id BIGINT NULL COMMENT '所属文件夹'"
            ))
            conn.commit()


_migrate_component_columns()


def _migrate_workflow_run_columns():
    """workflow 表按需新增优先级和运行缓存列"""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'workflow'"
        )).fetchall()
        existing = {r[0] for r in rows}
        adds = [
            ("priority", "ALTER TABLE workflow ADD COLUMN priority INT NOT NULL DEFAULT 3 COMMENT '优先级 1=P1高 2=P2中 3=P3低'"),
            ("last_run_status", "ALTER TABLE workflow ADD COLUMN last_run_status VARCHAR(50) NULL COMMENT '最近运行状态'"),
            ("last_run_time", "ALTER TABLE workflow ADD COLUMN last_run_time DATETIME NULL COMMENT '最近运行时间'"),
            ("last_run_duration", "ALTER TABLE workflow ADD COLUMN last_run_duration INT NULL COMMENT '最近运行耗时秒'"),
        ]
        for col, ddl in adds:
            if col not in existing:
                conn.execute(text(ddl))
                conn.commit()


_migrate_workflow_run_columns()


def _migrate_alert_rule_table():
    """按需创建 alert_rule 表"""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'alert_rule'"
        )).fetchall()
        if not rows:
            conn.execute(text("""
                CREATE TABLE alert_rule (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(128) NOT NULL,
                    target_type VARCHAR(32) NOT NULL DEFAULT 'all',
                    target_id BIGINT NULL,
                    trigger_type VARCHAR(32) NOT NULL,
                    trigger_value INT NULL,
                    notify_type VARCHAR(32) NOT NULL,
                    notify_config JSON NOT NULL,
                    enabled TINYINT NOT NULL DEFAULT 1,
                    created_by BIGINT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            conn.commit()


_migrate_alert_rule_table()


def _migrate_word_root_table():
    """按需创建 word_root 表"""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'word_root'"
        )).fetchall()
        if not rows:
            conn.execute(text("""
                CREATE TABLE word_root (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    en VARCHAR(64) NOT NULL COMMENT '英文词根',
                    cn VARCHAR(64) NOT NULL COMMENT '中文名',
                    category VARCHAR(32) NOT NULL DEFAULT 'business' COMMENT 'business/technical/metric',
                    description VARCHAR(255) NULL COMMENT '说明',
                    example VARCHAR(255) NULL COMMENT '示例用法',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_en (en)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            conn.commit()


_migrate_word_root_table()




# ─── RBAC 种子数据 ──────────────────────────────────────────────────────────

_BUILTIN_PERMISSIONS = [
    ("user:manage",       "用户管理",       "user",       "manage"),
    ("role:manage",       "角色管理",       "role",       "manage"),
    ("system:config",     "系统配置",       "system",     "config"),
    ("datasource:read",   "数据源查看",     "datasource", "read"),
    ("datasource:write",  "数据源编辑",     "datasource", "write"),
    ("component:read",    "组件查看",       "component",  "read"),
    ("component:create",  "组件创建",       "component",  "create"),
    ("component:write",   "组件编辑",       "component",  "write"),
    ("component:publish", "组件发布/下线",  "component",  "publish"),
    ("workflow:read",     "工作流查看",     "workflow",   "read"),
    ("workflow:create",   "工作流创建",     "workflow",   "create"),
    ("workflow:write",    "工作流编辑",     "workflow",   "write"),
    ("workflow:publish",  "工作流发布/下线","workflow",   "publish"),
    ("sync:read",         "数据同步查看",   "sync",       "read"),
    ("sync:write",        "数据同步编辑",   "sync",       "write"),
    ("metadata:read",     "数据资产查看",   "metadata",   "read"),
    ("metadata:write",    "数据资产编辑",   "metadata",   "write"),
    ("monitor:read",      "系统监控查看",   "monitor",    "read"),
    ("monitor:write",     "监控规则编辑",   "monitor",    "write"),
]

_BUILTIN_ROLES = {
    "admin": {
        "name": "管理员",
        "description": "拥有所有权限",
        "permissions": [p[0] for p in _BUILTIN_PERMISSIONS],
    },
    "developer": {
        "name": "开发者",
        "description": "可管理数据源、组件、工作流、数据同步",
        "permissions": [
            "datasource:read", "datasource:write",
            "component:read", "component:create", "component:write", "component:publish",
            "workflow:read", "workflow:create", "workflow:write", "workflow:publish",
            "sync:read", "sync:write",
            "metadata:read", "metadata:write", "monitor:read", "monitor:write",
        ],
    },
    "analyst": {
        "name": "分析师",
        "description": "可查看数据资产和运行实例",
        "permissions": ["metadata:read", "monitor:read", "workflow:read", "component:read"],
    },
    "viewer": {
        "name": "只读用户",
        "description": "只能查看数据资产",
        "permissions": ["metadata:read"],
    },
}


def _seed_roles_and_permissions():
    from app.models.role import SysRole, SysPermission, SysRolePermission
    db = SessionLocal()
    try:
        for code, name, resource_type, action in _BUILTIN_PERMISSIONS:
            if not db.query(SysPermission).filter(SysPermission.code == code).first():
                db.add(SysPermission(code=code, name=name, resource_type=resource_type, action=action))
        db.flush()

        for role_code, role_info in _BUILTIN_ROLES.items():
            role = db.query(SysRole).filter(SysRole.code == role_code).first()
            if not role:
                role = SysRole(
                    code=role_code,
                    name=role_info["name"],
                    description=role_info["description"],
                    is_system=True,
                )
                db.add(role)
                db.flush()

            existing_perm_ids = {
                rp.permission_id
                for rp in db.query(SysRolePermission).filter(SysRolePermission.role_id == role.id).all()
            }
            for perm_code in role_info["permissions"]:
                perm = db.query(SysPermission).filter(SysPermission.code == perm_code).first()
                if perm and perm.id not in existing_perm_ids:
                    db.add(SysRolePermission(role_id=role.id, permission_id=perm.id))

        db.commit()
    finally:
        db.close()


_seed_roles_and_permissions()


# 确保管理员账号存在并关联 RBAC admin 角色
def _ensure_admin():
    from app.models.user import SysUser
    from app.models.role import SysRole, SysUserRole
    db = SessionLocal()
    try:
        admin = db.query(SysUser).filter(SysUser.username == "admin").first()
        if not admin:
            admin = SysUser(
                username="admin",
                password=hash_password("admin123"),
                real_name="系统管理员",
                role="admin",
                status=1,
            )
            db.add(admin)
            db.flush()

        # 确保 admin 用户关联了 RBAC admin 角色
        admin_role = db.query(SysRole).filter(SysRole.code == "admin").first()
        if admin_role:
            exists = db.query(SysUserRole).filter(
                SysUserRole.user_id == admin.id,
                SysUserRole.role_id == admin_role.id,
            ).first()
            if not exists:
                db.add(SysUserRole(user_id=admin.id, role_id=admin_role.id))

        # 保持 legacy role 字段与 RBAC 一致
        if admin.role != "admin":
            admin.role = "admin"
        if admin.status != 1:
            admin.status = 1

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

from app.api import alert_rules
app.include_router(alert_rules.router, prefix="/api")

from app.api import word_roots
app.include_router(word_roots.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "portal-backend"}
