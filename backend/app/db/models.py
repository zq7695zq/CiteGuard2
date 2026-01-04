# 中文注释：本文件(backend/app/db/models.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
import uuid
from datetime import datetime
from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String, nullable=False)
    stage = Column(String, nullable=False)
    config_json = Column(JSON, nullable=False, default=dict)
    input_paper_uri = Column(String, nullable=True)
    input_bib_uri = Column(String, nullable=True)
    progress_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    last_error_code = Column(String, nullable=True)
    last_error_message = Column(Text, nullable=True)

    tasks = relationship("Task", back_populates="job")
    artifacts = relationship("Artifact", back_populates="job")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("job_id", "type", "key", name="uq_task_key"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    type = Column(String, nullable=False)
    key = Column(String, nullable=False)
    status = Column(String, nullable=False)
    attempt = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    retry_after_at = Column(DateTime, nullable=True)
    payload_json = Column(JSON, nullable=False, default=dict)
    result_uri = Column(String, nullable=True)
    error_json = Column(JSON, nullable=True)
    heartbeat_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    job = relationship("Job", back_populates="tasks")


class Event(Base):
    __tablename__ = "events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=True)
    seq = Column(BigInteger, nullable=False)
    ts = Column(DateTime, nullable=False, default=datetime.utcnow)
    event_type = Column(String, nullable=False)
    level = Column(String, nullable=False)
    data_json = Column(JSON, nullable=False, default=dict)


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    name = Column(String, nullable=False)
    uri = Column(String, nullable=False)
    sha256 = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    job = relationship("Job", back_populates="artifacts")
