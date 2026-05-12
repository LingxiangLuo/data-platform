from typing import Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.component import Component
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


class ComponentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None


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
    c = Component(
        name=req.name,
        type=req.type,
        description=req.description,
        config_json=req.config_json,
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
