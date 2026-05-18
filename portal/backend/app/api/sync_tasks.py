from typing import Optional, List, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.permissions import require_permission
from app.models.sync_task import SyncTask
from app.models.datasource import DataSource
from app.models.user import SysUser

router = APIRouter(prefix="/sync-tasks", tags=["同步任务"])


class FieldMapping(BaseModel):
    kind: Optional[str] = "column"   # column / constant / variable
    src: str
    dst: str
    type: Optional[str] = None


class SyncTaskCreate(BaseModel):
    name: str
    project_id: Optional[int] = None
    source_id: int
    target_id: int
    source_table: str
    target_table: str
    sync_type: str = "full"
    increment_column: Optional[str] = None
    field_mapping: Optional[List[FieldMapping]] = None
    where_clause: Optional[str] = None
    split_pk: Optional[str] = None
    write_mode: Optional[str] = "insert"
    channel: Optional[int] = 3
    pre_sql: Optional[List[str]] = None
    post_sql: Optional[List[str]] = None


def _serialize(task: SyncTask) -> dict:
    import json
    def _parse_json(s):
        if not s:
            return None
        try:
            return json.loads(s)
        except Exception:
            return None
    return {
        "id": task.id,
        "name": task.name,
        "project_id": task.project_id,
        "source_id": task.source_id,
        "target_id": task.target_id,
        "source_table": task.source_table,
        "target_table": task.target_table,
        "sync_type": task.sync_type,
        "increment_column": task.increment_column,
        "field_mapping": _parse_json(task.field_mapping),
        "where_clause": task.where_clause,
        "split_pk": task.split_pk,
        "write_mode": task.write_mode or "insert",
        "channel": task.channel or 3,
        "pre_sql": _parse_json(task.pre_sql),
        "post_sql": _parse_json(task.post_sql),
        "ds_workflow_id": task.ds_workflow_id,
        "status": task.status,
        "last_run_time": str(task.last_run_time) if task.last_run_time else None,
        "last_run_status": task.last_run_status,
        "created_at": str(task.created_at) if task.created_at else None,
    }


@router.get("")
def list_tasks(
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    project_id: Optional[int] = Query(None, description="按项目过滤；传 0 表示未分组（project_id IS NULL）"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    query = db.query(SyncTask)
    if keyword:
        query = query.filter(SyncTask.name.contains(keyword))
    if status:
        query = query.filter(SyncTask.status == status)
    if project_id is not None:
        if project_id == 0:
            query = query.filter(SyncTask.project_id.is_(None))
        else:
            query = query.filter(SyncTask.project_id == project_id)
    total = query.count()
    items = query.order_by(SyncTask.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "items": [_serialize(t) for t in items]}


@router.post("")
def create_task(
    req: SyncTaskCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_permission("sync:write")),
):
    import json
    source = db.query(DataSource).filter(DataSource.id == req.source_id).first()
    target = db.query(DataSource).filter(DataSource.id == req.target_id).first()
    if not source or not target:
        raise HTTPException(status_code=400, detail="数据源不存在")

    payload = req.model_dump()
    fm = payload.pop("field_mapping", None)
    if fm:
        payload["field_mapping"] = json.dumps(fm, ensure_ascii=False)
    if payload.get("pre_sql") is not None:
        payload["pre_sql"] = json.dumps(payload["pre_sql"], ensure_ascii=False)
    if payload.get("post_sql") is not None:
        payload["post_sql"] = json.dumps(payload["post_sql"], ensure_ascii=False)
    task = SyncTask(**payload, created_by=current_user.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return _serialize(task)


@router.get("/{task_id}")
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    task = db.query(SyncTask).filter(SyncTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _serialize(task)


@router.put("/{task_id}")
def update_task(
    task_id: int,
    req: SyncTaskCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_permission("sync:write")),
):
    import json
    task = db.query(SyncTask).filter(SyncTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    data = req.model_dump(exclude_unset=True)
    if "field_mapping" in data:
        fm = data.pop("field_mapping")
        data["field_mapping"] = json.dumps(fm, ensure_ascii=False) if fm else None
    if "pre_sql" in data:
        v = data.pop("pre_sql")
        data["pre_sql"] = json.dumps(v, ensure_ascii=False) if v else None
    if "post_sql" in data:
        v = data.pop("post_sql")
        data["post_sql"] = json.dumps(v, ensure_ascii=False) if v else None
    for key, value in data.items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return _serialize(task)


@router.patch("/{task_id}/status")
def set_task_status(
    task_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_permission("sync:write")),
):
    """切换同步任务状态：active / draft / paused"""
    allowed = {"draft", "active", "paused"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail=f"不支持的状态: {status}")
    task = db.query(SyncTask).filter(SyncTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    task.status = status
    db.commit()
    db.refresh(task)
    return _serialize(task)


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_permission("sync:write")),
):
    from app.models.component import Component
    from app.models.workflow import Workflow

    task = db.query(SyncTask).filter(SyncTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 清理关联的 datax Component（及其引用的 Workflow）
    comps = db.query(Component).filter(
        Component.type == "datax",
        Component.config_json.contains(f'"sync_task_id": {task_id}'),
    ).all()
    for comp in comps:
        # 删除引用该组件的 Workflow
        wfs = db.query(Workflow).filter(
            Workflow.steps_json.contains(f'"component_id": {comp.id}'),
        ).all()
        for wf in wfs:
            db.delete(wf)
        db.delete(comp)

    db.delete(task)
    db.commit()
    return {"message": "删除成功"}


# ============ DataX 预览 & 连接测试 ============

class DataXPreviewRequest(BaseModel):
    source_id: int
    target_id: int
    source_table: str
    target_table: str
    sync_type: str = "full"
    increment_column: Optional[str] = None
    field_mapping: List[FieldMapping]
    where_clause: Optional[str] = None
    split_pk: Optional[str] = None
    write_mode: Optional[str] = "insert"
    pre_sql: Optional[List[str]] = None
    post_sql: Optional[List[str]] = None


class TestConnectionRequest(BaseModel):
    datasource_id: int
    table: Optional[str] = None


@router.get("/{task_id}/preview-datax")
def preview_datax(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """基于已保存的任务生成 DataX job.json（密码已打码）"""
    from app.core.datax_builder import build_for_sync_task
    task = db.query(SyncTask).filter(SyncTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    src = db.query(DataSource).filter(DataSource.id == task.source_id).first()
    dst = db.query(DataSource).filter(DataSource.id == task.target_id).first()
    if not src or not dst:
        raise HTTPException(status_code=400, detail="任务关联的数据源已被删除")
    try:
        job = build_for_sync_task(task, src, dst, mask_password=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"task_id": task_id, "datax": job}


@router.post("/preview")
def preview_unsaved(
    req: DataXPreviewRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """向导第 4 步：基于未落库的表单生成 DataX 预览"""
    from app.core.datax_builder import build_datax_job
    src = db.query(DataSource).filter(DataSource.id == req.source_id).first()
    dst = db.query(DataSource).filter(DataSource.id == req.target_id).first()
    if not src or not dst:
        raise HTTPException(status_code=400, detail="数据源不存在")
    try:
        job = build_datax_job(
            source_ds=src,
            source_table=req.source_table,
            target_ds=dst,
            target_table=req.target_table,
            field_mapping=[m.model_dump() for m in req.field_mapping],
            sync_type=req.sync_type,
            increment_column=req.increment_column,
            where_clause=req.where_clause,
            split_pk=req.split_pk,
            write_mode=req.write_mode or "insert",
            pre_sql=req.pre_sql,
            post_sql=req.post_sql,
            mask_password=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"datax": job}


@router.post("/test-connection")
def test_connection(
    req: TestConnectionRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """测试数据源连接 & 表存在性"""
    ds = db.query(DataSource).filter(DataSource.id == req.datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    from app.core.db_adapter import test_connection as adapter_test
    ok, msg = adapter_test(ds, table=req.table)
    return {"ok": ok, "message": msg}


@router.post("/{task_id}/publish-as-workflow")
async def publish_as_workflow(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_permission("sync:write")),
):
    """兼容端点：将同步任务发布为工作流（委托给 Component.publish-as-workflow）。"""
    from app.models.component import Component
    from app.api.component import publish_component_as_workflow

    comps = db.query(Component).filter(Component.type == "datax").all()
    comp = next(
        (c for c in comps if (c.config_json or {}).get("sync_task_id") == task_id),
        None,
    )
    if not comp:
        raise HTTPException(status_code=404, detail="未找到关联的 datax 组件，请先保存任务")

    return await publish_component_as_workflow(comp.id, db, current_user)
