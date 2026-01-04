# 中文注释：本文件(backend/app/sse/events.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
from __future__ import annotations
from datetime import datetime
from sqlalchemy import select, func
from app.db.session import SessionLocal
from app.db.models import Event


def next_seq(session) -> int:
    current = session.execute(select(func.max(Event.seq))).scalar() or 0
    return current + 1


def emit_event(job_id: str, event_type: str, level: str, data: dict, task_id: str | None = None) -> None:
    with SessionLocal() as session:
        seq = next_seq(session)
        event = Event(
            job_id=job_id,
            task_id=task_id,
            seq=seq,
            ts=datetime.utcnow(),
            event_type=event_type,
            level=level,
            data_json=data,
        )
        session.add(event)
        session.commit()
