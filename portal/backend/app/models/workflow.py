from sqlalchemy import Column, BigInteger, String, Integer, Text, DateTime, JSON
from sqlalchemy.sql import func

from app.core.database import Base


class Workflow(Base):
    """线性工作流 — 串联多个 Component 形成可调度的流水线"""
    __tablename__ = "workflow"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    # 线性步骤数组,顺序即执行顺序
    # 每个步骤: {component_id: int, name: str (步骤别名,默认取 component 名字)}
    steps_json = Column(JSON, nullable=False, default=list)
    # 调度 (CRON 表达式,可选)
    cron_expression = Column(String(100))
    # 调度状态: ONLINE / OFFLINE (DS 调度开关,与 status 是两回事)
    schedule_status = Column(String(50), default="OFFLINE", nullable=False)
    # 工作流生命周期: draft -> tested -> online -> offline
    status = Column(String(50), default="draft", nullable=False)
    version = Column(Integer, default=1, nullable=False)
    # 发布后映射到 DS process-definition code (Phase 5/6 填入)
    ds_process_code = Column(BigInteger)
    # 调度 schedule id (Phase 5/6 填入)
    ds_schedule_id = Column(BigInteger)
    created_by = Column(BigInteger)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
