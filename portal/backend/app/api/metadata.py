"""元数据简版表 (Phase 8) — 直接连接 datasource 获取库表元信息

替代 OpenMetadata 的 MVP 方案: 按需 (on-demand) 走 information_schema 查表/字段
"""
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.permissions import check_resource_permission
from app.core.encrypt import decrypt_password
from app.models.datasource import DataSource
from app.models.user import SysUser

router = APIRouter(prefix="/metadata", tags=["元数据"])


def _connect_mysql(ds: DataSource, db_override: Optional[str] = None):
    import pymysql
    conn = pymysql.connect(
        host=ds.host,
        port=ds.port or 3306,
        user=ds.username,
        password=decrypt_password(ds.password) or "",
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
def list_tables_api(
    datasource_id: int = Query(..., description="数据源 ID"),
    keyword: Optional[str] = Query(None, description="表名模糊过滤"),
    limit: int = Query(50, ge=1, le=500, description="返回上限，默认 50（前端自动补全用）"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """列出数据源所有表（支持多种数据库）"""
    ds = _get_ds_or_404(db, datasource_id)
    if not check_resource_permission(db, current_user, "datasource", datasource_id, "read"):
        raise HTTPException(status_code=404, detail="数据源不存在")
    try:
        from app.core.db_adapter import list_tables as adapter_list_tables
        raw_tables = adapter_list_tables(ds)
        # keyword 过滤
        if keyword:
            kw = keyword.lower()
            raw_tables = [t for t in raw_tables if kw in t["name"].lower() or kw in t.get("comment", "").lower()]
        raw_tables = raw_tables[:limit]
        return {
            "datasource_id": ds.id,
            "datasource_name": ds.name,
            "database": ds.database_name,
            "total": len(raw_tables),
            "tables": [
                {
                    "name": t["name"],
                    "comment": t.get("comment", ""),
                    "type": t.get("type", "BASE TABLE"),
                    "rows": t.get("rows", 0),
                }
                for t in raw_tables
            ],
        }
    except HTTPException:
        raise
    except Exception:
        import logging
        logging.getLogger(__name__).error("读取元数据失败", exc_info=True)
        raise HTTPException(status_code=502, detail="读取元数据失败，请检查数据源连接")



@router.get("/columns")
def list_columns_api(
    datasource_id: int = Query(...),
    table: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """列出某张表的字段（支持多种数据库），含主键/唯一/索引/外键/自增标记"""
    ds = _get_ds_or_404(db, datasource_id)
    if not check_resource_permission(db, current_user, "datasource", datasource_id, "read"):
        raise HTTPException(status_code=404, detail="数据源不存在")
    import re
    if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)?", table):
        raise HTTPException(status_code=400, detail="表名格式非法：仅允许字母、数字、下划线和单点号")

    t = (ds.type or "").lower()
    schema = None
    tbl = table
    if "." in table:
        schema, tbl = table.split(".", 1)
    db_name = schema or ds.database_name

    conn = None
    try:
        from app.core.db_adapter import _connect
        conn = _connect(ds)
        cur = conn.cursor()

        columns = []
        if t == "mysql":
            cur.execute(
                "SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, EXTRA, COLUMN_COMMENT "
                "FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION",
                (db_name, tbl),
            )
            for r in cur.fetchall():
                columns.append({
                    "name": r[0],
                    "type": r[1],
                    "nullable": r[2] == "YES",
                    "primary_key": r[3] == "PRI",
                    "unique": r[3] == "UNI",
                    "index": r[3] == "MUL",
                    "auto_increment": "auto_increment" in (r[4] or ""),
                    "foreign_key": False,
                    "comment": r[5] or "",
                })
            # 外键
            cur.execute(
                "SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND REFERENCED_TABLE_NAME IS NOT NULL",
                (db_name, tbl),
            )
            fk_cols = {r[0] for r in cur.fetchall()}
            for c in columns:
                if c["name"] in fk_cols:
                    c["foreign_key"] = True

        elif t == "postgresql":
            cur.execute(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",
                (db_name, tbl),
            )
            for r in cur.fetchall():
                columns.append({
                    "name": r[0],
                    "type": r[1],
                    "nullable": r[2] == "YES",
                    "primary_key": False,
                    "unique": False,
                    "index": False,
                    "auto_increment": False,
                    "foreign_key": False,
                    "comment": "",
                })
            col_map = {c["name"]: c for c in columns}
            # 主键
            cur.execute(
                "SELECT kcu.column_name FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu ON tc.constraint_name=kcu.constraint_name "
                "AND tc.table_schema=kcu.table_schema WHERE tc.constraint_type='PRIMARY KEY' "
                "AND tc.table_schema=%s AND tc.table_name=%s",
                (db_name, tbl),
            )
            for r in cur.fetchall():
                if r[0] in col_map:
                    col_map[r[0]]["primary_key"] = True
            # 唯一
            cur.execute(
                "SELECT kcu.column_name FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu ON tc.constraint_name=kcu.constraint_name "
                "AND tc.table_schema=kcu.table_schema WHERE tc.constraint_type='UNIQUE' "
                "AND tc.table_schema=%s AND tc.table_name=%s",
                (db_name, tbl),
            )
            for r in cur.fetchall():
                if r[0] in col_map:
                    col_map[r[0]]["unique"] = True
            # 外键
            cur.execute(
                "SELECT kcu.column_name FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu ON tc.constraint_name=kcu.constraint_name "
                "AND tc.table_schema=kcu.table_schema WHERE tc.constraint_type='FOREIGN KEY' "
                "AND tc.table_schema=%s AND tc.table_name=%s",
                (db_name, tbl),
            )
            for r in cur.fetchall():
                if r[0] in col_map:
                    col_map[r[0]]["foreign_key"] = True
            # 普通索引 (pg_indexes)
            cur.execute(
                "SELECT indexdef FROM pg_indexes WHERE schemaname=%s AND tablename=%s",
                (db_name, tbl),
            )
            import re
            for r in cur.fetchall():
                m = re.search(r'\(([^)]+)\)', r[0] or "")
                if m:
                    for col in m.group(1).split(","):
                        cn = col.strip().strip('"')
                        if cn in col_map and not col_map[cn]["primary_key"]:
                            col_map[cn]["index"] = True
            # serial / identity
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=%s AND table_name=%s AND is_identity='YES'",
                (db_name, tbl),
            )
            for r in cur.fetchall():
                if r[0] in col_map:
                    col_map[r[0]]["auto_increment"] = True

        else:
            # 其他数据库回退到 db_adapter
            from app.core.db_adapter import list_columns as adapter_list_columns
            cols = adapter_list_columns(ds, table)
            for i, c in enumerate(cols):
                columns.append({
                    "name": c["name"],
                    "type": c["type"],
                    "nullable": c.get("nullable", True),
                    "primary_key": False,
                    "unique": False,
                    "index": False,
                    "auto_increment": False,
                    "foreign_key": False,
                    "comment": c.get("comment", ""),
                })

        conn.close()
        if not columns:
            raise HTTPException(status_code=404, detail=f"表 {table} 不存在或无字段")
        return {
            "datasource_id": ds.id,
            "database": ds.database_name,
            "table": table,
            "columns": [
                {
                    "name": c["name"],
                    "position": i + 1,
                    "type": c["type"],
                    "nullable": c["nullable"],
                    "primary_key": c.get("primary_key", False),
                    "unique": c.get("unique", False),
                    "index": c.get("index", False),
                    "auto_increment": c.get("auto_increment", False),
                    "foreign_key": c.get("foreign_key", False),
                    "comment": c.get("comment", ""),
                }
                for i, c in enumerate(columns)
            ],
        }
    except HTTPException:
        raise
    except Exception:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        import logging
        logging.getLogger(__name__).error("读取字段失败", exc_info=True)
        raise HTTPException(status_code=502, detail="读取字段失败，请检查数据源连接")



@router.get("/preview")
def preview_table(
    datasource_id: int = Query(...),
    table: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """前 N 行数据预览（支持多种数据库，通过 SQLAlchemy 执行）"""
    ds = _get_ds_or_404(db, datasource_id)
    if not check_resource_permission(db, current_user, "datasource", datasource_id, "read"):
        raise HTTPException(status_code=404, detail="数据源不存在")
    # 严格校验表名：仅允许 ASCII 字母、数字、下划线、点号（schema.table）
    import re
    if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)?", table):
        raise HTTPException(status_code=400, detail="表名格式非法：仅允许字母、数字、下划线和单点号")
    try:
        import sqlalchemy as sa
        from app.core.db_adapter import sqlalchemy_url
        t = (ds.type or "").lower()
        # MongoDB 用原生驱动
        if t == "mongodb":
            from app.core.db_adapter import _connect
            client = _connect(ds)
            try:
                coll = client[ds.database_name][table]
                docs = list(coll.find().limit(limit))
                columns = list(docs[0].keys()) if docs else []
                safe_rows = [{k: (str(v) if v is not None else None) for k, v in d.items()} for d in docs]
            finally:
                client.close()
            return {"datasource_id": ds.id, "table": table, "columns": columns, "rows": safe_rows, "count": len(safe_rows)}

        # Redis 用 SCAN
        if t == "redis":
            from app.core.db_adapter import _connect
            r = _connect(ds)
            keys = r.keys("*")[:limit]
            safe_rows = [{"key": k, "value": str(r.get(k))} for k in keys]
            r.close()
            return {"datasource_id": ds.id, "table": table, "columns": ["key", "value"], "rows": safe_rows, "count": len(safe_rows)}

        # 其他 SQL 数据库用 SQLAlchemy
        connect_args = {"connect_timeout": 10} if t in ("mysql", "postgresql") else {}
        engine = sa.create_engine(sqlalchemy_url(ds), pool_pre_ping=True, connect_args=connect_args)
        # 对已通过正则校验的表名做数据库特定引用
        def _quote_identifier(name: str, db_type: str) -> str:
            if db_type == "sqlserver":
                return f"[{name}]"
            if db_type == "oracle":
                return f'"{name.upper()}"'
            return f'"{name}"'

        quoted_table = _quote_identifier(table, t) if "." not in table else ".".join(_quote_identifier(p, t) for p in table.split(".", 1))

        # MySQL / ClickHouse: LIMIT n; SQLServer: TOP n; Oracle: FETCH FIRST n ROWS ONLY
        if t == "sqlserver":
            query = f"SELECT TOP {limit} * FROM {quoted_table}"
        elif t == "oracle":
            query = f"SELECT * FROM {quoted_table} FETCH FIRST {limit} ROWS ONLY"
        elif t == "clickhouse":
            query = f"SELECT * FROM {quoted_table} LIMIT {limit}"
        elif t == "postgresql":
            from app.core.db_adapter import _connect
            import psycopg2.extras
            conn = _connect(ds)
            try:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                # table 已通过正则校验，仅允许字母数字下划线和单点号
                if "." in table:
                    sch, tbl = table.split(".", 1)
                    cur.execute('SELECT * FROM %s.%s LIMIT %%s', (psycopg2.extensions.AsIs(f'"{sch}"'), psycopg2.extensions.AsIs(f'"{tbl}"'), limit))
                else:
                    # 先尝试 search_path，再 fallback schema-qualified
                    try:
                        cur.execute('SELECT * FROM %s LIMIT %%s', (psycopg2.extensions.AsIs(f'"{table}"'), limit))
                    except Exception:
                        conn.rollback()
                        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                        cur.execute('SELECT * FROM %s.%s LIMIT %%s', (psycopg2.extensions.AsIs(f'"{ds.database_name}"'), psycopg2.extensions.AsIs(f'"{table}"'), limit))
                rows = cur.fetchall()
                columns = list(rows[0].keys()) if rows else [desc[0] for desc in cur.description] if cur.description else []
            finally:
                conn.close()
            safe_rows = [{k: (str(v) if v is not None else None) for k, v in r.items()} for r in rows]
            return {"datasource_id": ds.id, "table": table, "columns": columns, "rows": safe_rows, "count": len(safe_rows)}
        else:
            query = f"SELECT * FROM {quoted_table} LIMIT {limit}"

        with engine.connect() as conn:
            res = conn.execute(sa.text(query))
            columns = list(res.keys())
            raw_rows = res.fetchmany(limit)
        engine.dispose()
        safe_rows = [{k: (str(v) if v is not None else None) for k, v in zip(columns, row)} for row in raw_rows]
        return {"datasource_id": ds.id, "table": table, "columns": columns, "rows": safe_rows, "count": len(safe_rows)}
    except HTTPException:
        raise
    except Exception:
        import logging
        logging.getLogger(__name__).error("数据预览失败", exc_info=True)
        raise HTTPException(status_code=502, detail="数据预览失败，请检查数据源连接")



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


def _generate_ddl_sql(db_type: str, table: str, columns: List[DDLColumn]) -> str:
    """根据数据库类型生成 CREATE TABLE DDL"""
    if not columns:
        raise HTTPException(status_code=400, detail="字段列表不能为空")
    t = db_type.lower()

    def _quote(name: str) -> str:
        if t == "sqlserver":
            return f"[{name}]"
        if t == "oracle":
            return f'"{name.upper()}"'
        return f"`{name}`"

    lines: List[str] = []
    pk_cols: List[str] = []
    for c in columns:
        ctype = c.type or ("VARCHAR2(255)" if t == "oracle" else "varchar(255)")
        null_part = "NULL" if c.nullable else "NOT NULL"
        comment_part = ""
        if c.comment:
            safe_comment = c.comment.replace("'", "''")  # 转义单引号防 SQL 注入
            if t == "oracle":
                comment_part = ""  # Oracle comment 单独加
            else:
                comment_part = f" COMMENT '{safe_comment}'"
        lines.append(f"  {_quote(c.name)} {ctype} {null_part}{comment_part}")
        if c.primary_key:
            pk_cols.append(_quote(c.name))

    if pk_cols:
        lines.append(f"  PRIMARY KEY ({', '.join(pk_cols)})")

    if t == "mysql":
        return (
            f"CREATE TABLE IF NOT EXISTS `{table}` (\n"
            + ",\n".join(lines) + "\n"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;"
        )
    if t == "postgresql":
        return f"CREATE TABLE IF NOT EXISTS {table} (\n" + ",\n".join(lines) + "\n);"
    if t == "sqlserver":
        return f"IF OBJECT_ID('{table}', 'U') IS NULL\nCREATE TABLE {table} (\n" + ",\n".join(lines) + "\n);"
    if t == "oracle":
        ddl = f"CREATE TABLE {table} (\n" + ",\n".join(lines) + "\n);"
        # Oracle comment 单独执行
        comments = [
            f"COMMENT ON COLUMN {table}.{_quote(c.name)} IS '{c.comment.replace(chr(39), chr(39)+chr(39))}'"
            for c in columns if c.comment
        ]
        if comments:
            ddl += "\n" + ";\n".join(comments) + ";"
        return ddl
    if t == "clickhouse":
        return f"CREATE TABLE IF NOT EXISTS {table} (\n" + ",\n".join(lines) + "\n) ENGINE=MergeTree() ORDER BY " + (", ".join(pk_cols) if pk_cols else "tuple()") + ";"
    # 默认 MySQL 风格
    return f"CREATE TABLE IF NOT EXISTS `{table}` (\n" + ",\n".join(lines) + "\n);"


@router.post("/generate-ddl")
def generate_ddl(
    req: GenerateDDLRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """根据字段列表生成 CREATE TABLE DDL（支持多种数据库）"""
    ds = _get_ds_or_404(db, req.datasource_id)
    if not check_resource_permission(db, current_user, "datasource", req.datasource_id, "read"):
        raise HTTPException(status_code=404, detail="数据源不存在")
    import re
    if not re.fullmatch(r"[A-Za-z0-9_]+", req.target_table):
        raise HTTPException(status_code=400, detail="表名格式非法：仅允许字母、数字和下划线")
    ddl = _generate_ddl_sql(ds.type or "mysql", req.target_table, req.columns)
    return {"datasource_id": ds.id, "target_table": req.target_table, "ddl": ddl}


@router.post("/execute-ddl")
def execute_ddl(
    req: ExecuteDDLRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """执行 DDL（只接受 CREATE TABLE 语句以减少风险）"""
    ds = _get_ds_or_404(db, req.datasource_id)
    if not check_resource_permission(db, current_user, "datasource", req.datasource_id, "write"):
        raise HTTPException(status_code=404, detail="数据源不存在")
    sql = (req.ddl or "").strip()
    # 严格校验：只允许 CREATE TABLE IF NOT EXISTS，禁止分号防多语句
    if ";" in sql:
        raise HTTPException(status_code=400, detail="DDL 中不允许包含分号")
    head = sql.lstrip().upper()
    if not head.startswith("CREATE TABLE IF NOT EXISTS"):
        raise HTTPException(status_code=400, detail="仅允许 CREATE TABLE IF NOT EXISTS 语句")
    try:
        import sqlalchemy as sa
        from app.core.db_adapter import sqlalchemy_url
        connect_args = {"connect_timeout": 10} if (ds.type or "").lower() in ("mysql", "postgresql") else {}
        engine = sa.create_engine(sqlalchemy_url(ds), pool_pre_ping=True, connect_args=connect_args)
        with engine.connect() as conn:
            conn.execute(sa.text(sql.rstrip(";")))
            conn.commit()
        engine.dispose()
        return {"ok": True, "message": "建表成功"}
    except Exception:
        import logging
        logging.getLogger(__name__).error("建表失败", exc_info=True)
        raise HTTPException(status_code=502, detail="建表失败，请检查 DDL 语法或数据源连接")


# ===== 统计 =====
@router.get("/stats")
def metadata_stats(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """数据资产统计（工作台用）"""
    from app.models.datasource import DataSource
    from app.models.word_root import WordRoot

    ds_count = db.query(DataSource).count()
    root_count = db.query(WordRoot).count()

    # 统计所有数据源的表数和总行数
    datasources = db.query(DataSource).filter(
        DataSource.host.isnot(None), DataSource.username.isnot(None)
    ).all()
    table_count = 0
    total_rows = 0
    ds_breakdown = []
    for ds in datasources:
        try:
            from app.core.db_adapter import list_tables as adapter_list_tables
            t_count = len(adapter_list_tables(ds))
            # 估算行数（MySQL 特有，其他数据库返回 0）
            t_rows = 0
            t = (ds.type or "").lower()
            if t == "mysql":
                import pymysql
                conn = pymysql.connect(
                    host=ds.host, port=ds.port or 3306,
                    user=ds.username, password=decrypt_password(ds.password) or "",
                    database=ds.database_name, connect_timeout=5,
                )
                cur = conn.cursor()
                cur.execute(
                    "SELECT COALESCE(SUM(TABLE_ROWS),0) "
                    "FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s",
                    (ds.database_name,)
                )
                t_rows = cur.fetchone()[0] or 0
                conn.close()
            table_count += t_count
            total_rows += t_rows
            ds_breakdown.append({"name": ds.name, "tables": t_count, "rows": t_rows})
        except Exception:
            ds_breakdown.append({"name": ds.name, "tables": 0, "rows": 0})

    # 格式化总行数
    if total_rows >= 100000000:
        rows_display = f"{total_rows / 100000000:.1f}亿"
    elif total_rows >= 10000:
        rows_display = f"{total_rows / 10000:.1f}w"
    else:
        rows_display = str(total_rows)

    return {
        "datasource_count": ds_count,
        "table_count": table_count,
        "total_rows": total_rows,
        "total_rows_display": rows_display,
        "word_root_count": root_count,
        "datasource_breakdown": ds_breakdown,
    }


# ===== 血缘 =====
@router.get("/lineage")
def get_lineage(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """自动解析组件/同步任务生成表级血缘"""
    from app.models.component import Component
    from app.models.sync_task import SyncTask
    import json as json_mod

    nodes_map = {}  # table_name → node info
    edges = []

    def add_node(name, ds_name=None):
        if not name or name in nodes_map:
            return
        # 推断层级
        lower = name.lower()
        if lower.startswith("ods_") or lower.startswith("ods."):
            layer = "ods"
        elif lower.startswith(("dim_", "dw_", "ads_", "dim.", "dw.", "ads.")):
            layer = "app"
        else:
            layer = "source"
        nodes_map[name] = {"id": name, "name": name, "datasource": ds_name, "layer": layer}

    # 1. SyncTask — 直接有 source_table / target_table
    sync_tasks = db.query(SyncTask).filter(SyncTask.status == "active").all()
    for t in sync_tasks:
        src = t.source_table
        tgt = t.target_table
        if src and tgt:
            add_node(src, "source")
            add_node(tgt, "target")
            edges.append({"source": src, "target": tgt, "type": "DataX", "task_name": t.name})

    # 2. Component (online) — 解析 SQL 和 DataX
    components = db.query(Component).filter(Component.status == "online").all()
    for c in components:
        cfg = c.config_json or {}
        if c.type == "datax":
            # 从 rawJson 解析 reader/writer table
            raw = cfg.get("rawJson", "")
            if raw:
                try:
                    job = json_mod.loads(raw) if isinstance(raw, str) else raw
                    content = job.get("job", {}).get("content", [{}])[0]
                    reader_tables = (content.get("reader", {}).get("parameter", {})
                                     .get("connection", [{}])[0].get("table", []))
                    writer_tables = (content.get("writer", {}).get("parameter", {})
                                     .get("connection", [{}])[0].get("table", []))
                    for st in (reader_tables if isinstance(reader_tables, list) else [reader_tables]):
                        for tt in (writer_tables if isinstance(writer_tables, list) else [writer_tables]):
                            if st and tt:
                                add_node(st)
                                add_node(tt)
                                edges.append({"source": st, "target": tt, "type": "DataX", "task_name": c.name})
                except Exception:
                    pass
        elif c.type == "sql":
            # 简单正则提取 FROM/JOIN/INSERT INTO
            sql_text = cfg.get("sql", "")
            if sql_text:
                import re
                # 提取 source tables (FROM / JOIN)
                sources = re.findall(
                    r'(?:FROM|JOIN)\s+[`"]?(\w+)[`"]?', sql_text, re.IGNORECASE
                )
                # 提取 target table (INSERT INTO / CREATE TABLE)
                targets = re.findall(
                    r'(?:INSERT\s+INTO|CREATE\s+TABLE)\s+[`"]?(\w+)[`"]?', sql_text, re.IGNORECASE
                )
                for s in sources:
                    add_node(s)
                for t in targets:
                    add_node(t)
                    for s in sources:
                        edges.append({"source": s, "target": t, "type": "SQL", "task_name": c.name})

    # 去重 edges
    seen = set()
    unique_edges = []
    for e in edges:
        key = f"{e['source']}→{e['target']}"
        if key not in seen:
            seen.add(key)
            unique_edges.append(e)

    return {
        "nodes": list(nodes_map.values()),
        "edges": unique_edges,
    }


# ===== 数据质量 =====
@router.get("/quality")
def table_quality(
    datasource_id: int = Query(...),
    table: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """表级数据质量分析（支持 MySQL / PostgreSQL）"""
    ds = _get_ds_or_404(db, datasource_id)
    if not check_resource_permission(db, current_user, "datasource", datasource_id, "read"):
        raise HTTPException(status_code=404, detail="数据源不存在")
    import re
    if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)?", table):
        raise HTTPException(status_code=400, detail="表名格式非法：仅允许字母、数字、下划线和单点号")

    t = (ds.type or "").lower()
    if t not in ("mysql", "postgresql"):
        raise HTTPException(status_code=400, detail="当前仅支持 MySQL / PostgreSQL 的数据质量分析")

    conn = None
    try:
        from app.core.db_adapter import _connect
        conn = _connect(ds)
        cur = conn.cursor()

        db_name = ds.database_name
        # 支持 schema.table 格式
        schema = None
        tbl = table
        if "." in table:
            schema, tbl = table.split(".", 1)

        # 1. 获取字段元数据（含 PK / INDEX / AUTO）
        columns_meta = {}
        if t == "mysql":
            cur.execute(
                "SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, EXTRA "
                "FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
                "ORDER BY ORDINAL_POSITION",
                (db_name, tbl),
            )
            for r in cur.fetchall():
                columns_meta[r[0]] = {
                    "type": r[1],
                    "nullable": r[2] == "YES",
                    "primary_key": r[3] == "PRI",
                    "unique": r[3] == "UNI",
                    "index": r[3] == "MUL",
                    "auto_increment": "auto_increment" in (r[4] or ""),
                }
        else:  # postgresql
            # 基础字段信息
            cur.execute(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_schema=%s AND table_name=%s "
                "ORDER BY ordinal_position",
                (schema or db_name, tbl),
            )
            for r in cur.fetchall():
                columns_meta[r[0]] = {
                    "type": r[1],
                    "nullable": r[2] == "YES",
                    "primary_key": False,
                    "unique": False,
                    "index": False,
                    "auto_increment": False,
                    "foreign_key": False,
                }
            # 主键 (information_schema 方式更可靠)
            cur.execute(
                "SELECT kcu.column_name "
                "FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name = kcu.constraint_name "
                "  AND tc.table_schema = kcu.table_schema "
                "WHERE tc.constraint_type = 'PRIMARY KEY' "
                "  AND tc.table_schema = %s "
                "  AND tc.table_name = %s",
                (schema or db_name, tbl),
            )
            for r in cur.fetchall():
                if r[0] in columns_meta:
                    columns_meta[r[0]]["primary_key"] = True
            # 唯一约束 (排除主键)
            cur.execute(
                "SELECT kcu.column_name "
                "FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name = kcu.constraint_name "
                "  AND tc.table_schema = kcu.table_schema "
                "WHERE tc.constraint_type = 'UNIQUE' "
                "  AND tc.table_schema = %s "
                "  AND tc.table_name = %s",
                (schema or db_name, tbl),
            )
            for r in cur.fetchall():
                if r[0] in columns_meta and not columns_meta[r[0]]["primary_key"]:
                    columns_meta[r[0]]["unique"] = True
            # 外键
            cur.execute(
                "SELECT kcu.column_name "
                "FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name = kcu.constraint_name "
                "  AND tc.table_schema = kcu.table_schema "
                "WHERE tc.constraint_type = 'FOREIGN KEY' "
                "  AND tc.table_schema = %s "
                "  AND tc.table_name = %s",
                (schema or db_name, tbl),
            )
            for r in cur.fetchall():
                if r[0] in columns_meta:
                    columns_meta[r[0]]["foreign_key"] = True
            # 普通索引 (通过 pg_indexes 获取)
            cur.execute(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname = %s AND tablename = %s",
                (schema or db_name, tbl),
            )
            for r in cur.fetchall():
                idx_def = r[0] or ""
                # 简单解析索引定义中的字段名
                if "CREATE INDEX" in idx_def.upper() or "CREATE UNIQUE INDEX" in idx_def.upper():
                    # 提取括号内的字段名
                    import re
                    m = re.search(r'\(([^)]+)\)', idx_def)
                    if m:
                        for col in m.group(1).split(','):
                            col_name = col.strip().strip('"')
                            if col_name in columns_meta and not columns_meta[col_name]["primary_key"]:
                                columns_meta[col_name]["index"] = True
            # serial / identity
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=%s AND table_name=%s "
                "AND is_identity='YES'",
                (schema or db_name, tbl),
            )
            for r in cur.fetchall():
                if r[0] in columns_meta:
                    columns_meta[r[0]]["auto_increment"] = True

        if not columns_meta:
            raise HTTPException(status_code=404, detail=f"表 {table} 不存在或无字段")

        # 2. 获取总行数（表名已通过正则校验，仅含字母数字下划线，安全引用）
        if t == "mysql":
            cur.execute(f"SELECT COUNT(*) FROM `{tbl}`")
        else:
            if schema:
                cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{tbl}"')
            else:
                cur.execute(f'SELECT COUNT(*) FROM "{tbl}"')
        total_rows = cur.fetchone()[0] or 0

        # 3. 对每个字段执行质量分析
        col_list = []
        for col_name, meta in columns_meta.items():
            col_type = meta["type"].lower()
            is_numeric = any(k in col_type for k in ("int", "float", "double", "decimal", "numeric", "real", "serial", "money"))
            is_date = any(k in col_type for k in ("date", "time", "timestamp", "year"))

            null_count = 0
            distinct_count = 0
            min_val = None
            max_val = None
            avg_val = None
            issues = []

            if total_rows > 0:
                if t == "mysql":
                    # NULL 和 DISTINCT
                    cur.execute(
                        f"SELECT COUNT(*) - COUNT(`{col_name}`), COUNT(DISTINCT `{col_name}`) FROM `{tbl}`"
                    )
                    row = cur.fetchone()
                    null_count = row[0] or 0
                    distinct_count = row[1] or 0

                    # 数值统计
                    if is_numeric:
                        cur.execute(
                            f"SELECT MIN(`{col_name}`), MAX(`{col_name}`), AVG(`{col_name}`) FROM `{tbl}`"
                        )
                        row = cur.fetchone()
                        min_val = str(row[0]) if row[0] is not None else None
                        max_val = str(row[1]) if row[1] is not None else None
                        avg_val = str(round(float(row[2]), 2)) if row[2] is not None else None

                else:  # postgresql
                    # NULL 和 DISTINCT
                    if schema:
                        cur.execute(
                            f'SELECT COUNT(*) - COUNT("{col_name}"), COUNT(DISTINCT "{col_name}") '
                            f'FROM "{schema}"."{tbl}"'
                        )
                    else:
                        cur.execute(
                            f'SELECT COUNT(*) - COUNT("{col_name}"), COUNT(DISTINCT "{col_name}") '
                            f'FROM "{tbl}"'
                        )
                    row = cur.fetchone()
                    null_count = row[0] or 0
                    distinct_count = row[1] or 0

                    # 数值统计
                    if is_numeric:
                        if schema:
                            cur.execute(
                                f'SELECT MIN("{col_name}"), MAX("{col_name}"), AVG("{col_name}") '
                                f'FROM "{schema}"."{tbl}"'
                            )
                        else:
                            cur.execute(
                                f'SELECT MIN("{col_name}"), MAX("{col_name}"), AVG("{col_name}") '
                                f'FROM "{tbl}"'
                            )
                        row = cur.fetchone()
                        min_val = str(row[0]) if row[0] is not None else None
                        max_val = str(row[1]) if row[1] is not None else None
                        avg_val = str(round(float(row[2]), 2)) if row[2] is not None else None

            # 计算评分和发现问题
            score = 100
            if null_count > 0:
                null_rate = null_count / total_rows if total_rows else 0
                score -= int(null_rate * 30)
                if null_rate > 0.2:
                    issues.append(f"NULL {null_count}行 ({int(null_rate*100)}%)")
                elif null_rate > 0:
                    issues.append(f"NULL {null_count}行")

            duplicate_count = total_rows - distinct_count
            if duplicate_count > 0 and not meta["primary_key"]:
                dup_rate = duplicate_count / total_rows if total_rows else 0
                score -= int(dup_rate * 20)
                if dup_rate > 0.1:
                    issues.append(f"重复 {duplicate_count}行 ({int(dup_rate*100)}%)")

            if meta["primary_key"] and distinct_count != total_rows:
                score -= 20
                issues.append(f"主键不唯一 {total_rows - distinct_count}行")

            col_list.append({
                "name": col_name,
                "type": meta["type"],
                "nullable": meta["nullable"],
                "primary_key": meta["primary_key"],
                "unique": meta["unique"],
                "index": meta["index"],
                "auto_increment": meta["auto_increment"],
                "total_rows": total_rows,
                "null_count": null_count,
                "null_rate": round(null_count / total_rows, 4) if total_rows else 0,
                "distinct_count": distinct_count,
                "duplicate_count": duplicate_count,
                "duplicate_rate": round(duplicate_count / total_rows, 4) if total_rows else 0,
                "min": min_val,
                "max": max_val,
                "avg": avg_val,
                "score": max(0, score),
                "issues": issues,
            })

        conn.close()
        return {
            "datasource_id": ds.id,
            "table": table,
            "total_rows": total_rows,
            "columns": col_list,
        }
    except HTTPException:
        raise
    except Exception:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        import logging
        logging.getLogger(__name__).error("数据质量分析失败", exc_info=True)
        raise HTTPException(status_code=502, detail="数据质量分析失败，请检查数据源连接")

