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

    try:
        t = (ds.type or "").lower()
        if t == "mysql":
            import pymysql
            conn = pymysql.connect(
                host=ds.host, port=ds.port, user=ds.username,
                password=ds.password, database=ds.database_name, connect_timeout=5,
            )
            conn.close()
        elif t == "postgresql":
            import psycopg2
            conn = psycopg2.connect(
                host=ds.host, port=ds.port, user=ds.username,
                password=ds.password, dbname=ds.database_name, connect_timeout=5,
            )
            conn.close()
        elif t == "sqlserver":
            import pymssql
            conn = pymssql.connect(
                server=ds.host, port=str(ds.port), user=ds.username,
                password=ds.password, database=ds.database_name, login_timeout=5,
            )
            conn.close()
        elif t == "oracle":
            import cx_Oracle
            dsn = cx_Oracle.makedsn(ds.host, ds.port, service_name=ds.database_name)
            conn = cx_Oracle.connect(user=ds.username, password=ds.password or "", dsn=dsn)
            conn.close()
        elif t == "clickhouse":
            from clickhouse_driver import Client
            client = Client(host=ds.host, port=ds.port, user=ds.username, password=ds.password or "", database=ds.database_name)
            client.execute("SELECT 1")
        elif t == "mongodb":
            from pymongo import MongoClient
            uri = f"mongodb://{ds.username}:{ds.password}@{ds.host}:{ds.port}/{ds.database_name}"
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            client.close()
        elif t == "redis":
            import redis
            r = redis.Redis(host=ds.host, port=ds.port, password=ds.password or None, decode_responses=True, socket_connect_timeout=5)
            r.ping()
        elif t == "hive":
            # Hive 通过 pyhive 或标记为可用，暂用 impyla
            from impala.dbapi import connect
            conn = connect(host=ds.host, port=ds.port, user=ds.username, password=ds.password or "", database=ds.database_name, auth_mechanism="PLAIN", timeout=5)
            conn.close()
        else:
            ds.status = 1
            db.commit()
            return {"message": f"{ds.type} 暂不支持自动连接测试，已标记为可用", "status": 1}

        ds.status = 1
        db.commit()
        return {"message": "连接测试成功", "status": 1}
    except Exception as e:
        ds.status = 0
        db.commit()
        return {"message": f"连接测试失败: {str(e)}", "status": 0}
