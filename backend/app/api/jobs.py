# 中文注释：本文件(backend/app/api/jobs.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
# 中文注释：提供 Job/Task/Artifact 的 REST API，并对外暴露暂停、继续、重试等控制能力。
from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from app.storage.fs import Storage
from sqlalchemy import select
from app.api.deps import get_db
from app.db.models import Job, Task, Artifact
from app.orchestrator.jobs import create_job
from app.worker.tasks import enqueue_task

router = APIRouter()


@router.get("/jobs")
def list_jobs(db=Depends(get_db)):
    jobs = db.execute(select(Job).order_by(Job.created_at.desc())).scalars().all()
    return [
        {
            "job_id": job.id,
            "status": job.status,
            "stage": job.stage,
            "progress": job.progress_json,
            "created_at": job.created_at.isoformat(),
        }
        for job in jobs
    ]


@router.post("/jobs")
def create_job_endpoint(payload: dict):
    job_id = create_job(payload["paper_text"], payload["bib_text"], payload.get("config", {}))
    return {"job_id": job_id, "status": "RUNNING"}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db=Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "job_id": job.id,
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress_json,
        "current": job.stage,
        "last_error": {"code": job.last_error_code, "message": job.last_error_message},
    }


@router.get("/jobs/{job_id}/tasks")
def list_tasks(job_id: str, type: str | None = None, status: str | None = None, db=Depends(get_db)):
    query = select(Task).where(Task.job_id == job_id)
    if type:
        query = query.where(Task.type == type)
    if status:
        query = query.where(Task.status == status)
    tasks = db.execute(query).scalars().all()
    return [
        {
            "id": task.id,
            "type": task.type,
            "key": task.key,
            "status": task.status,
            "attempt": task.attempt,
            "error": task.error_json,
            "result_uri": task.result_uri,
        }
        for task in tasks
    ]


@router.get("/jobs/{job_id}/tasks/{task_id}")
def get_task(job_id: str, task_id: str, db=Depends(get_db)):
    task = db.get(Task, task_id)
    if not task or task.job_id != job_id:
        raise HTTPException(status_code=404, detail="task not found")
    return {
        "id": task.id,
        "type": task.type,
        "key": task.key,
        "status": task.status,
        "attempt": task.attempt,
        "error": task.error_json,
        "result_uri": task.result_uri,
    }


@router.post("/jobs/{job_id}/pause")
def pause_job(job_id: str, db=Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    job.status = "PAUSED"
    job.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/jobs/{job_id}/resume")
def resume_job(job_id: str, db=Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    job.status = "RUNNING"
    job.updated_at = datetime.utcnow()
    db.commit()
    enqueue_task(job_id)
    return {"ok": True}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, db=Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    job.status = "CANCELLED"
    db.commit()
    return {"ok": True}


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str, payload: dict, db=Depends(get_db)):
    task_ids = payload.get("task_ids")
    if task_ids:
        tasks = db.execute(select(Task).where(Task.id.in_(task_ids))).scalars().all()
    else:
        tasks = db.execute(select(Task).where(Task.job_id == job_id, Task.status == "FAILED")).scalars().all()
    for task in tasks:
        task.status = "RETRY_PENDING"
        task.retry_after_at = datetime.utcnow()
    db.commit()
    enqueue_task(job_id)
    return {"ok": True, "count": len(tasks)}


@router.post("/jobs/{job_id}/skip")
def skip_job(job_id: str, payload: dict, db=Depends(get_db)):
    task_ids = payload.get("task_ids", [])
    tasks = db.execute(select(Task).where(Task.id.in_(task_ids))).scalars().all()
    for task in tasks:
        task.status = "SKIPPED"
    db.commit()
    return {"ok": True, "count": len(tasks)}


@router.get("/jobs/{job_id}/artifacts")
def list_artifacts(job_id: str, db=Depends(get_db)):
    artifacts = db.execute(select(Artifact).where(Artifact.job_id == job_id)).scalars().all()
    return [{"name": art.name, "uri": art.uri, "sha256": art.sha256} for art in artifacts]


@router.get("/jobs/{job_id}/artifacts/{name}")
def get_artifact(job_id: str, name: str, db=Depends(get_db)):
    artifact = db.execute(
        select(Artifact).where(Artifact.job_id == job_id, Artifact.name == name)
    ).scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="artifact not found")
    storage = Storage()
    path = storage.from_uri(artifact.uri)
    return FileResponse(path, filename=artifact.name)
