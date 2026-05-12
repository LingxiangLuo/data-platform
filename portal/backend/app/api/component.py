from typing import Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.component import Component
from app.models.component_folder import ComponentFolder
from app.models.user import SysUser

router = APIRouter(prefix="/components", tags=["组件"])


# ===== 类型与状态常量 =====
VALID_TYPES = {"sql", "python", "shell", "datax"}
STATUS_DRAFT = "draft"
STATUS_TESTED = "tested"
STATUS_ONLINE = "online"
STATUS_OFFLINE = "offline"

# 允许编辑/删除的状态
EDITABLE_STATUSES = {STATUS_DRAFT, STATUS_TESTED}
DELETABLE_STATUSES = {STATUS_DRAFT, STATUS_OFFLINE}


# ===== Schemas =====
class ComponentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str
    description: Optional[str] = None
    config_json: Dict[str, Any] = Field(default_factory=dict)
    folder_id: Optional[int] = None


class ComponentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None
    folder_id: Optional[int] = None


def _serialize(c: Component) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "type": c.type,
        "description": c.description,
        "config_json": c.config_json or {},
        "version": c.version,
        "status": c.status,
        "ds_task_code": c.ds_task_code,
        "folder_id": c.folder_id,
        "created_at": str(c.created_at) if c.created_at else None,
        "updated_at": str(c.updated_at) if c.updated_at else None,
    }


def _get_or_404(db: Session, comp_id: int) -> Component:
    c = db.query(Component).filter(Component.id == comp_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="组件不存在")
    return c


# ===== CRUD =====
@router.get("")
def list_components(
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    q = db.query(Component)
    if keyword:
        q = q.filter(Component.name.contains(keyword))
    if type:
        q = q.filter(Component.type == type)
    if status:
        q = q.filter(Component.status == status)
    total = q.count()
    items = q.order_by(Component.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "items": [_serialize(c) for c in items]}


@router.post("")
def create_component(
    req: ComponentCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    if req.type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"非法组件类型,允许:{','.join(sorted(VALID_TYPES))}")
    # 校验 folder_id
    if req.folder_id:
        folder = db.query(ComponentFolder).filter(ComponentFolder.id == req.folder_id).first()
        if not folder:
            raise HTTPException(status_code=400, detail="文件夹不存在")
    c = Component(
        name=req.name,
        type=req.type,
        description=req.description,
        config_json=req.config_json,
        folder_id=req.folder_id,
        status=STATUS_DRAFT,
        version=1,
        created_by=current_user.id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _serialize(c)


@router.get("/{comp_id}")
def get_component(
    comp_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    return _serialize(_get_or_404(db, comp_id))


@router.put("/{comp_id}")
def update_component(
    comp_id: int,
    req: ComponentUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    c = _get_or_404(db, comp_id)
    if c.status not in EDITABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"组件状态 {c.status},只有 draft/tested 状态允许编辑;请先下线",
        )
    updates = req.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(c, key, value)
    # 编辑后状态回到 draft (需要重新测试)
    if "config_json" in updates:
        c.status = STATUS_DRAFT
        c.version = (c.version or 1) + 1
    db.commit()
    db.refresh(c)
    return _serialize(c)


@router.delete("/{comp_id}")
def delete_component(
    comp_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    c = _get_or_404(db, comp_id)
    if c.status not in DELETABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"组件状态 {c.status},只有 draft/offline 状态允许删除;请先下线",
        )
    db.delete(c)
    db.commit()
    return {"message": "删除成功"}


# ===== 状态机操作 =====
@router.post("/{comp_id}/run")
def run_component(
    comp_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """手动运行组件 (Phase 3: 占位实现,Phase 5+ 接 DS API)"""
    c = _get_or_404(db, comp_id)
    # TODO Phase 5+: 调 DS 执行
    return {
        "message": f"已触发运行 (Phase 3 占位,实际执行待 Phase 5+ 接入)",
        "component_id": c.id,
        "type": c.type,
    }


@router.post("/{comp_id}/test")
def test_component(
    comp_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """测试组件 — 通过后状态转为 tested"""
    c = _get_or_404(db, comp_id)
    if c.status not in {STATUS_DRAFT, STATUS_TESTED}:
        raise HTTPException(status_code=400, detail=f"状态 {c.status} 下不允许测试")
    # TODO Phase 5+: 实际执行测试,根据结果决定是否切到 tested
    # Phase 3: 假定测试通过
    c.status = STATUS_TESTED
    db.commit()
    db.refresh(c)
    return {"message": "测试通过 (Phase 3 占位)", **_serialize(c)}


@router.post("/{comp_id}/publish")
def publish_component(
    comp_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """发布组件 — tested 才能发布,发布后状态为 online"""
    c = _get_or_404(db, comp_id)
    if c.status != STATUS_TESTED:
        raise HTTPException(
            status_code=400,
            detail=f"只有 tested 状态可发布,当前状态 {c.status},请先测试",
        )
    # TODO Phase 5+: 翻译成 DS Task + 创建/更新 ds process-definition,把 task_code 写回
    c.status = STATUS_ONLINE
    db.commit()
    db.refresh(c)
    return {"message": "已发布 (Phase 3 占位,DS 同步待 Phase 5+ 接入)", **_serialize(c)}


@router.post("/{comp_id}/offline")
def offline_component(
    comp_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """下线组件"""
    c = _get_or_404(db, comp_id)
    if c.status != STATUS_ONLINE:
        raise HTTPException(status_code=400, detail=f"只有 online 状态可下线,当前 {c.status}")
    # TODO Phase 5+: 同步下线 DS 调度
    c.status = STATUS_OFFLINE
    db.commit()
    db.refresh(c)
    return {"message": "已下线", **_serialize(c)}


# ─────────────────────────────────────────────
# 文件夹管理 (ComponentFolder)
# ─────────────────────────────────────────────

class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    type: str
    parent_id: Optional[int] = None


class FolderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)


@router.get("/folders")
def list_folders(
    type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """列出组件文件夹（支持按类型过滤）"""
    q = db.query(ComponentFolder)
    if type:
        q = q.filter(ComponentFolder.type == type)
    items = q.order_by(ComponentFolder.depth.asc(), ComponentFolder.id.asc()).all()
    return [
        {
            "id": f.id,
            "name": f.name,
            "type": f.type,
            "parent_id": f.parent_id,
            "depth": f.depth,
            "created_at": str(f.created_at) if f.created_at else None,
        }
        for f in items
    ]


@router.post("/folders")
def create_folder(
    req: FolderCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """创建文件夹（最多三级嵌套）"""
    if req.type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"非法类型,允许:{','.join(sorted(VALID_TYPES))}")

    depth = 0
    if req.parent_id:
        parent = db.query(ComponentFolder).filter(ComponentFolder.id == req.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="父文件夹不存在")
        if parent.depth >= 2:
            raise HTTPException(status_code=400, detail="最多三级嵌套")
        depth = parent.depth + 1

    folder = ComponentFolder(
        name=req.name,
        type=req.type,
        parent_id=req.parent_id,
        depth=depth,
        created_by=current_user.id,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return {
        "id": folder.id,
        "name": folder.name,
        "type": folder.type,
        "parent_id": folder.parent_id,
        "depth": folder.depth,
    }


@router.put("/folders/{folder_id}")
def update_folder(
    folder_id: int,
    req: FolderUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """重命名文件夹"""
    folder = db.query(ComponentFolder).filter(ComponentFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="文件夹不存在")
    if req.name:
        folder.name = req.name
    db.commit()
    db.refresh(folder)
    return {"id": folder.id, "name": folder.name}


@router.delete("/folders/{folder_id}")
def delete_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """删除文件夹（会自动将子文件夹和组件移出）"""
    folder = db.query(ComponentFolder).filter(ComponentFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="文件夹不存在")

    # 将文件夹内的组件移出
    db.query(Component).filter(Component.folder_id == folder_id).update(
        {Component.folder_id: None}, synchronize_session=False
    )

    # 递归删除子文件夹
    child_ids = [folder_id]
    to_delete = [folder_id]
    while child_ids:
        children = db.query(ComponentFolder.id).filter(
            ComponentFolder.parent_id.in_(child_ids)
        ).all()
        child_ids = [c[0] for c in children]
        to_delete.extend(child_ids)

    db.query(ComponentFolder).filter(ComponentFolder.id.in_(to_delete)).delete(
        synchronize_session=False
    )
    db.commit()
    return {"message": "删除成功"}


# ─────────────────────────────────────────────
# SQL 即席查询
# ─────────────────────────────────────────────

class RunSqlRequest(BaseModel):
    datasource_id: int
    sql: str = Field(..., min_length=1)


def _connect_mysql(host: str, port: int, user: str, password: str, database: str):
    import pymysql
    return pymysql.connect(
        host=host, port=port or 3306,
        user=user, password=password,
        database=database,
        connect_timeout=10, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


@router.post("/run-sql")
def run_sql_adhoc(
    req: RunSqlRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """SQL 即席查询 / 执行（仅限 SELECT / INSERT / UPDATE / DELETE）"""
    from app.models.datasource import DataSource

    ds = db.query(DataSource).filter(DataSource.id == req.datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if ds.type != "mysql":
        raise HTTPException(status_code=400, detail=f"暂不支持 {ds.type} 数据源")

    sql = req.sql.strip()
    upper = sql.upper()

    # 安全校验：只允许 DQL / DML，禁止 DDL / DCL
    dangerous = ['DROP ', 'TRUNCATE ', 'ALTER ', 'CREATE ', 'GRANT ', 'REVOKE ']
    for kw in dangerous:
        if kw in upper:
            raise HTTPException(status_code=400, detail=f"禁止执行危险操作: {kw.strip()}")

    import time
    start = time.time()

    try:
        conn = _connect_mysql(ds.host, ds.port, ds.username, ds.password, ds.database_name)
        with conn.cursor() as cur:
            cur.execute(sql)

            if upper.startswith("SELECT"):
                rows = cur.fetchall()
                columns = [d[0] for d in cur.description] if cur.description else []
                # 确保可序列化
                safe_rows = []
                for r in rows:
                    safe_rows.append({k: (str(v) if v is not None else None) for k, v in r.items()})
                return {
                    "type": "table",
                    "columns": columns,
                    "rows": safe_rows,
                    "row_count": len(safe_rows),
                    "duration_ms": round((time.time() - start) * 1000, 1),
                }
            else:
                conn.commit()
                return {
                    "type": "rowcount",
                    "affected": cur.rowcount,
                    "duration_ms": round((time.time() - start) * 1000, 1),
                }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"执行失败: {e}")
    finally:
        try:
            conn.close()
        except:
            pass


# ─────────────────────────────────────────────
# 组件快速发布
# ─────────────────────────────────────────────

@router.post("/{comp_id}/quick-publish")
def quick_publish_component(
    comp_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """快速发布：跳过测试直接发布上线（开发调试用）"""
    c = _get_or_404(db, comp_id)
    if c.status == STATUS_ONLINE:
        raise HTTPException(status_code=400, detail="组件已上线")
    c.status = STATUS_ONLINE
    db.commit()
    db.refresh(c)
    return {"message": "已快速发布上线", **_serialize(c)}
