"""元数据简版表 (Phase 8) — 直接连接 datasource 获取库表元信息

替代 OpenMetadata 的 MVP 方案: 按需 (on-demand) 走 information_schema 查表/字段
"""
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.datasource import DataSource
from app.models.user import SysUser

router = APIRouter(prefix="/metadata", tags=["元数据"])


def _connect_mysql(ds: DataSource, db_override: Optional[str] = None):
    import pymysql
    conn = pymysql.connect(
        host=ds.host,
        port=ds.port or 3306,
        user=ds.username,
        password=ds.password,
        database=db_override or ds.database_name,
        connect_timeout=5,
        charset="utf8mb4",
        use_unicode=True,
        cursorclass=pymysql.cursors.DictCursor,
    )
    with conn.cursor() as cur:
        cur.execute("SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    return conn


def _get_ds_or_404(db: Session, ds_id: int) -> DataSource:
    ds = db.query(DataSource).filter(DataSource.id == ds_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if not ds.host or not ds.username:
        raise HTTPException(status_code=400, detail="数据源未完整配置 (缺少 host/username)")
    return ds


@router.get("/tables")
def list_tables(
    datasource_id: int = Query(..., description="数据源 ID"),
    keyword: Optional[str] = Query(None, description="表名模糊过滤"),
    limit: int = Query(50, ge=1, le=500, description="返回上限，默认 50（前端自动补全用）"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """列出数据源所有表 (MySQL: information_schema.tables)"""
    ds = _get_ds_or_404(db, datasource_id)
    if ds.type != "mysql":
        raise HTTPException(status_code=400, detail=f"暂不支持的数据源类型: {ds.type}")
    try:
        conn = _connect_mysql(ds, db_override="information_schema")
        with conn.cursor() as cur:
            if keyword:
                cur.execute(
                    "SELECT TABLE_NAME, TABLE_TYPE, TABLE_ROWS, TABLE_COMMENT, "
                    "CREATE_TIME, UPDATE_TIME, DATA_LENGTH, INDEX_LENGTH "
                    "FROM TABLES WHERE TABLE_SCHEMA = %s "
                    "AND (TABLE_NAME LIKE %s OR TABLE_COMMENT LIKE %s) "
                    "ORDER BY TABLE_NAME LIMIT %s",
                    (ds.database_name, f"%{keyword}%", f"%{keyword}%", limit),
                )
            else:
                cur.execute(
                    "SELECT TABLE_NAME, TABLE_TYPE, TABLE_ROWS, TABLE_COMMENT, "
                    "CREATE_TIME, UPDATE_TIME, DATA_LENGTH, INDEX_LENGTH "
                    "FROM TABLES WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME LIMIT %s",
                    (ds.database_name, limit),
                )
            rows = cur.fetchall()
        conn.close()
        tables = [
            {
                "name": r["TABLE_NAME"],
                "type": r["TABLE_TYPE"],
                "rows": int(r["TABLE_ROWS"] or 0),
                "comment": r["TABLE_COMMENT"] or "",
                "create_time": str(r["CREATE_TIME"]) if r["CREATE_TIME"] else None,
                "update_time": str(r["UPDATE_TIME"]) if r["UPDATE_TIME"] else None,
                "data_length": int(r["DATA_LENGTH"] or 0),
                "index_length": int(r["INDEX_LENGTH"] or 0),
            }
            for r in rows
        ]
        return {
            "datasource_id": ds.id,
            "datasource_name": ds.name,
            "database": ds.database_name,
            "total": len(tables),
            "tables": tables,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"读取元数据失败: {e}")


@router.get("/columns")
def list_columns(
    datasource_id: int = Query(...),
    table: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """列出某张表的字段 (含主键/comment/类型)"""
    ds = _get_ds_or_404(db, datasource_id)
    if ds.type != "mysql":
        raise HTTPException(status_code=400, detail=f"暂不支持的数据源类型: {ds.type}")
    # 安全: table 名只允许字母数字下划线
    if not table.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="表名格式非法")
    try:
        conn = _connect_mysql(ds, db_override="information_schema")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COLUMN_NAME, ORDINAL_POSITION, COLUMN_TYPE, IS_NULLABLE, "
                "COLUMN_KEY, COLUMN_DEFAULT, EXTRA, COLUMN_COMMENT "
                "FROM COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                "ORDER BY ORDINAL_POSITION",
                (ds.database_name, table),
            )
            rows = cur.fetchall()
        conn.close()
        if not rows:
            raise HTTPException(status_code=404, detail=f"表 {table} 不存在")
        return {
            "datasource_id": ds.id,
            "database": ds.database_name,
            "table": table,
            "columns": [
                {
                    "name": r["COLUMN_NAME"],
                    "position": r["ORDINAL_POSITION"],
                    "type": r["COLUMN_TYPE"],
                    "nullable": r["IS_NULLABLE"] == "YES",
                    "primary_key": r["COLUMN_KEY"] == "PRI",
                    "default": r["COLUMN_DEFAULT"],
                    "extra": r["EXTRA"] or "",
                    "comment": r["COLUMN_COMMENT"] or "",
                }
                for r in rows
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"读取字段失败: {e}")


@router.get("/preview")
def preview_table(
    datasource_id: int = Query(...),
    table: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """前 N 行数据预览 (只读)"""
    ds = _get_ds_or_404(db, datasource_id)
    if ds.type != "mysql":
        raise HTTPException(status_code=400, detail=f"暂不支持的数据源类型: {ds.type}")
    if not table.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="表名格式非法")
    try:
        conn = _connect_mysql(ds)
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM `{table}` LIMIT %s", (limit,))
            rows = cur.fetchall()
            columns = [d[0] for d in cur.description] if cur.description else []
        conn.close()
        # rows 是 DictCursor 已返回 dict;保证可序列化
        safe_rows = []
        for r in rows:
            safe_rows.append({k: (str(v) if v is not None else None) for k, v in r.items()})
        return {
            "datasource_id": ds.id,
            "table": table,
            "columns": columns,
            "rows": safe_rows,
            "count": len(safe_rows),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"数据预览失败: {e}")


# ============ 自动建表（DataWorks「一键建表」对标）============

class DDLColumn(BaseModel):
    name: str
    type: str
    nullable: Optional[bool] = True
    primary_key: Optional[bool] = False
    comment: Optional[str] = None


class GenerateDDLRequest(BaseModel):
    datasource_id: int
    target_table: str
    columns: List[DDLColumn]


class ExecuteDDLRequest(BaseModel):
    datasource_id: int
    ddl: str


def _generate_mysql_ddl(table: str, columns: List[DDLColumn]) -> str:
    if not columns:
        raise HTTPException(status_code=400, detail="字段列表不能为空")
    lines: List[str] = []
    pk_cols: List[str] = []
    for c in columns:
        ctype = c.type or "varchar(255)"
        null_part = "NULL" if c.nullable else "NOT NULL"
        comment_part = f" COMMENT '{c.comment}'" if c.comment else ""
        lines.append(f"  `{c.name}` {ctype} {null_part}{comment_part}")
        if c.primary_key:
            pk_cols.append(f"`{c.name}`")
    if pk_cols:
        lines.append(f"  PRIMARY KEY ({', '.join(pk_cols)})")
    return (
        f"CREATE TABLE IF NOT EXISTS `{table}` (\n"
        + ",\n".join(lines)
        + "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;"
    )


@router.post("/generate-ddl")
def generate_ddl(
    req: GenerateDDLRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """根据字段列表生成 CREATE TABLE DDL（仅返回 SQL，不执行）"""
    ds = _get_ds_or_404(db, req.datasource_id)
    if ds.type != "mysql":
        raise HTTPException(status_code=400, detail=f"暂不支持的数据源类型: {ds.type}")
    if not req.target_table.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="表名格式非法")
    ddl = _generate_mysql_ddl(req.target_table, req.columns)
    return {"datasource_id": ds.id, "target_table": req.target_table, "ddl": ddl}


@router.post("/execute-ddl")
def execute_ddl(
    req: ExecuteDDLRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """执行 DDL（只接受 CREATE TABLE 语句以减少风险）"""
    ds = _get_ds_or_404(db, req.datasource_id)
    if ds.type != "mysql":
        raise HTTPException(status_code=400, detail=f"暂不支持的数据源类型: {ds.type}")
    sql = (req.ddl or "").strip()
    head = sql.lstrip().upper()
    if not head.startswith("CREATE TABLE"):
        raise HTTPException(status_code=400, detail="仅允许 CREATE TABLE 语句")
    try:
        conn = _connect_mysql(ds)
        with conn.cursor() as cur:
            cur.execute(sql.rstrip(";"))
        conn.commit()
        conn.close()
        return {"ok": True, "message": "建表成功"}
    except Exception as e:
        return {"ok": False, "message": f"建表失败: {e}"}
