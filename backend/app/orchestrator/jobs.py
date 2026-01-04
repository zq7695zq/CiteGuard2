# 中文注释：本文件(backend/app/orchestrator/jobs.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
# 中文注释：负责创建 Job、解析输入、生成任务拆分，并写入初始进度与事件。
from __future__ import annotations
import json
from datetime import datetime
from sqlalchemy import select
from app.core.bib import parse_bibtex
from app.core.citation_locator import locate_citations
from app.core.schemas import BibEntry, CitationOccurrence
from app.db.models import Job, Task
from app.db.session import SessionLocal
from app.sse.events import emit_event
from app.storage.fs import Storage
from app.worker.tasks import enqueue_task


def create_job(paper_text: str, bib_text: str, config: dict) -> str:
    storage = Storage()
    with SessionLocal() as session:
        job = Job(
            status="PENDING",
            stage="INGEST_PARSE",
            config_json=config or {},
            progress_json={"done": 0, "total": 0},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(job)
        session.commit()
        job_id = job.id

    paper_path = f"jobs/{job_id}/inputs/paper.txt"
    bib_path = f"jobs/{job_id}/inputs/refs.bib"
    storage.write_text(paper_path, paper_text)
    storage.write_text(bib_path, bib_text)

    bib_entries = parse_bibtex(bib_text)
    occurrences = locate_citations(paper_text)
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        job.input_paper_uri = storage.to_uri(paper_path)
        job.input_bib_uri = storage.to_uri(bib_path)
        job.status = "RUNNING"
        job.stage = "VERIFY_BIB"
        job.started_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        session.add(job)
        session.commit()

    emit_event(job_id, "stage_changed", "info", {"stage": "VERIFY_BIB"})
    _create_tasks(job_id, bib_entries, occurrences)
    return job_id


def _create_tasks(job_id: str, bib_entries: list[BibEntry], occurrences: list[CitationOccurrence]) -> None:
    with SessionLocal() as session:
        for bib in bib_entries:
            snippets = [occ.context_snippet for occ in occurrences if bib.bibkey in occ.bibkeys]
            _ensure_task(
                session,
                job_id,
                "BIB_VERIFY",
                f"bib:{bib.bibkey}",
                {"bib": bib.model_dump(), "citations": snippets},
            )
        for occ in occurrences:
            for key in occ.bibkeys:
                _ensure_task(
                    session,
                    job_id,
                    "OCC_MATCH",
                    f"occ:{occ.occurrence_id}:{key}",
                    {"occurrence": occ.model_dump(), "bibkey": key},
                )
        _ensure_task(session, job_id, "BUILD_BIB", "build_bib", {})
        _ensure_task(session, job_id, "SUMMARIZE_ARTIFACTS", "summarize", {})
        total = len(bib_entries) + sum(len(occ.bibkeys) for occ in occurrences) + 2
        job = session.get(Job, job_id)
        if job:
            job.progress_json = {"done": 0, "total": total}
            job.updated_at = datetime.utcnow()
        session.commit()

    emit_event(job_id, "task_enqueued", "info", {"count": len(bib_entries) + len(occurrences)})
    enqueue_task(job_id)


def _ensure_task(session, job_id: str, task_type: str, key: str, payload: dict) -> None:
    existing = session.execute(
        select(Task).where(Task.job_id == job_id, Task.type == task_type, Task.key == key)
    ).scalar_one_or_none()
    if existing:
        return
    task = Task(
        job_id=job_id,
        type=task_type,
        key=key,
        status="PENDING",
        attempt=0,
        max_attempts=3,
        payload_json=payload,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(task)
