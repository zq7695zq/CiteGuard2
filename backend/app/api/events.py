# 中文注释：本文件(backend/app/api/events.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
# 中文注释：提供 SSE 事件流接口，支持 after_seq 断线续传与前端实时渲染。
from __future__ import annotations
import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from app.db.models import Event
from app.db.session import SessionLocal

router = APIRouter()


def _format_sse(event: dict) -> str:
    payload = json.dumps(event, ensure_ascii=False)
    return f"data: {payload}\n\n"


@router.get("/jobs/{job_id}/events")
async def stream_events(job_id: str, after_seq: int = 0):
    async def event_generator():
        last_seq = after_seq
        while True:
            with SessionLocal() as session:
                events = (
                    session.execute(
                        select(Event)
                        .where(Event.job_id == job_id, Event.seq > last_seq)
                        .order_by(Event.seq)
                    )
                    .scalars()
                    .all()
                )
            if events:
                for event in events:
                    last_seq = event.seq
                    yield _format_sse(
                        {
                            "seq": event.seq,
                            "ts": event.ts.isoformat(),
                            "type": event.event_type,
                            "level": event.level,
                            "data": event.data_json,
                        }
                    )
            await asyncio.sleep(1)
    return StreamingResponse(event_generator(), media_type="text/event-stream")
