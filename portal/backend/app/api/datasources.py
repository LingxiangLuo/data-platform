from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.datasource import DataSource
from app.models.user import SysUser

router = APIRouter(prefix="/datasources", tags=["数据源"])


class DataSourceCreate(BaseModel):
    name: str
    type: str  # mysql / postgresql / sqlserver / oracle / clickhouse / mongodb / redis / hive
    host: str
    port: int
    database_name: str
    username: Optional[str] = None
    password: Optional[str] = None
    description: Optional[str] = None


class DataSourceUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    description: Optional[str] = None


def _serialize(ds: DataSource) -> dict:
    return {
        "id": ds.id,
        "name": ds.name,
        "type": ds.type,
        "host": ds.host,
        "port": ds.port,
        "database_name": ds.database_name,
        "username": ds.username,
        "description": ds.description,
        "status": ds.status,
        "last_check_time": str(ds.last_check_time) if ds.last_check_time else None,
        "created_at": str(ds.created_at) if ds.created_at else None,
    }


@router.get("")
def list_datasources(
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    query = db.query(DataSource)
    if keyword:
        query = query.filter(DataSource.name.contains(keyword))
    total = query.count()
    items = query.order_by(DataSource.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "items": [_serialize(ds) for ds in items]}


@router.post("")
def create_datasource(
    req: DataSourceCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    ds = DataSource(**req.model_dump(), created_by=current_user.id)
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return _serialize(ds)


@router.get("/{ds_id}")
def get_datasource(
    ds_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    ds = db.query(DataSource).filter(DataSource.id == ds_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return _serialize(ds)


@router.put("/{ds_id}")
def update_datasource(
    ds_id: int,
    req: DataSourceUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    ds = db.query(DataSource).filter(DataSource.id == ds_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    for key, value in req.model_dump(exclude_unset=True).items():
        setattr(ds, key, value)
    db.commit()
    db.refresh(ds)
    return _serialize(ds)


@router.delete("/{ds_id}")
def delete_datasource(
    ds_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    ds = db.query(DataSource).filter(DataSource.id == ds_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    db.delete(ds)
    db.commit()
    return {"message": "删除成功"}


@router.post("/{ds_id}/test")
def test_connection(
    ds_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    ds = db.query(DataSource).filter(DataSource.id == ds_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    from app.core.db_adapter import test_connection as adapter_test
    ok, msg = adapter_test(ds)
    ds.status = 1 if ok else 0
    db.commit()
    return {"message": msg, "status": ds.status}
