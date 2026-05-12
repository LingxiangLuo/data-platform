from typing import Optional, List, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
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
    schedule_cron: Optional[str] = None
    field_mapping: Optional[List[FieldMapping]] = None
    # ---- DataWorks 风格高级参数 ----
    where_clause: Optional[str] = None       # 源端 WHERE 过滤
    split_pk: Optional[str] = None           # DataX splitPk
    write_mode: Optional[str] = "insert"     # insert / replace / update
    pre_sql: Optional[List[str]] = None      # 导入前 SQL
    post_sql: Optional[List[str]] = None     # 导入后 SQL


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
        "schedule_cron": task.schedule_cron,
        "field_mapping": _parse_json(task.field_mapping),
        "where_clause": task.where_clause,
        "split_pk": task.split_pk,
        "write_mode": task.write_mode or "insert",
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
    current_user: SysUser = Depends(get_current_user),
):
    import json
    # 验证数据源存在
    source = db.query(DataSource).filter(DataSource.id == req.source_id).first()
    target = db.query(DataSource).filter(DataSource.id == req.target_id).first()
    if not source or not target:
        raise HTTPException(status_code=400, detail="数据源不存在")

    payload = req.model_dump()
    # JSON 化列表 / 复合字段
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
    current_user: SysUser = Depends(get_current_user),
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


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    task = db.query(SyncTask).filter(SyncTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    db.delete(task)
    db.commit()
    return {"message": "删除成功"}


# ============ DataX 预览 & 连接测试 ============

class DataXPreviewRequest(BaseModel):
    """未落库时基于表单数据生成预览"""
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
    table: Optional[str] = None  # 传表名时会同时验证表是否存在


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
    t = (ds.type or "").lower()
    try:
        if t == "mysql":
            import pymysql
            conn = pymysql.connect(
                host=ds.host, port=ds.port or 3306,
                user=ds.username, password=ds.password,
                database=ds.database_name,
                connect_timeout=5,
                charset="utf8mb4",
            )
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
                if req.table:
                    cur.execute(
                        "SELECT COUNT(*) FROM information_schema.TABLES "
                        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
                        (ds.database_name, req.table),
                    )
                    cnt = cur.fetchone()[0]
                    if cnt == 0:
                        conn.close()
                        return {"ok": False, "message": f"表 {req.table} 不存在"}
            conn.close()
        else:
            return {"ok": False, "message": f"暂不支持测试 {ds.type} 数据源"}
        return {"ok": True, "message": "连接成功"}
    except Exception as e:
        return {"ok": False, "message": f"连接失败：{e}"}


# ============ DataX 执行 ============

def _parse_datax_summary(log: str) -> dict:
    """从 DataX 控制台日志中抽取关键指标"""
    import re
    summary = {
        "total_read": None,
        "total_write": None,
        "failed_record": None,
        "duration_seconds": None,
        "speed_records_per_sec": None,
        "speed_bytes_per_sec": None,
    }
    # 任务结果汇总常见于日志尾部
    m = re.search(r"任务启动时刻[\s\S]+?读出记录总数\s*:\s*(\d+)", log)
    if m:
        summary["total_read"] = int(m.group(1))
    m = re.search(r"读写失败总数\s*:\s*(\d+)", log)
    if m:
        summary["failed_record"] = int(m.group(1))
    m = re.search(r"任务总计耗时\s*:\s*(\d+)\s*s", log)
    if m:
        summary["duration_seconds"] = int(m.group(1))
    m = re.search(r"记录写入速度\s*:\s*([\d.]+)\s*rec/s", log)
    if m:
        summary["speed_records_per_sec"] = float(m.group(1))
    m = re.search(r"字节写入速度\s*:\s*([\d.]+)\s*B/s", log)
    if m:
        summary["speed_bytes_per_sec"] = float(m.group(1))
    # write 数等于 read - failed
    if summary["total_read"] is not None and summary["failed_record"] is not None:
        summary["total_write"] = summary["total_read"] - summary["failed_record"]
    return summary


@router.post("/{task_id}/run")
def run_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """同步执行 DataX 任务（前台运行，限时 5 分钟）。

    架构：复用 dmp-ds 容器执行（它已自带 Java + DataX）。
    - portal-api 将 job.json 写到共享卷 /opt/datax/jobs/，dmp-ds 通过 ./datax:/opt/datax 看到同一路径
    - 通过 docker SDK 在 dmp-ds 内执行 datax.py
    - 解析 stdout，提取读/写/失败/耗时
    - 回写 last_run_time / last_run_status
    """
    import json, os, time, datetime
    from app.core.datax_builder import build_for_sync_task

    task = db.query(SyncTask).filter(SyncTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    src = db.query(DataSource).filter(DataSource.id == task.source_id).first()
    dst = db.query(DataSource).filter(DataSource.id == task.target_id).first()
    if not src or not dst:
        raise HTTPException(status_code=400, detail="任务关联的数据源已被删除")

    try:
        job = build_for_sync_task(task, src, dst, mask_password=False)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 共享卷：portal-api 与 dmp-ds 都能访问 /opt/datax/jobs/
    jobs_dir = os.environ.get("DATAX_JOBS_DIR", "/opt/datax/jobs")
    os.makedirs(jobs_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    job_filename = f"sync_{task_id}_{ts}.json"
    job_path = os.path.join(jobs_dir, job_filename)
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=2)

    # 通过 docker SDK 调起 dmp-ds 容器内的 datax
    ds_container = os.environ.get("DATAX_EXEC_CONTAINER", "dmp-ds")
    datax_home_in_ds = os.environ.get("DATAX_HOME", "/opt/datax")

    started_at = datetime.datetime.now()
    success = False
    out = ""
    exit_code = -1

    try:
        import docker
        client = docker.from_env(timeout=320)
        container = client.containers.get(ds_container)
        cmd = ["python", f"{datax_home_in_ds}/bin/datax.py", f"{datax_home_in_ds}/jobs/{job_filename}"]
        # exec_run 会一次性返回；DataX 通常单表几秒到几十秒
        result = container.exec_run(
            cmd,
            stdout=True, stderr=True, demux=False,
            environment={"DATAX_HOME": datax_home_in_ds, "LANG": "C.UTF-8"},
        )
        exit_code = result.exit_code if result.exit_code is not None else -1
        raw = result.output or b""
        try:
            out = raw.decode("utf-8", errors="replace")
        except Exception:
            out = str(raw)
        success = exit_code == 0
    except Exception as e:
        out = f"[ERROR] 调度 dmp-ds 执行 DataX 失败: {e}"
        success = False

    summary = _parse_datax_summary(out)
    log_path = job_path.replace(".json", ".log")
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(out)
    except Exception:
        pass

    task.last_run_time = started_at
    task.last_run_status = "success" if success else "failed"
    db.commit()

    tail = out[-8000:] if len(out) > 8000 else out
    return {
        "ok": success,
        "task_id": task_id,
        "started_at": str(started_at),
        "exit_code": exit_code,
        "job_path": job_path,
        "log_path": log_path,
        "summary": summary,
        "log_tail": tail,
    }
