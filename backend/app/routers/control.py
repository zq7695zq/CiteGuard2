from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Task, Job
from ..celery_app import celery_app
from ..tasks import verify_paper_job, context_match_job, correct_bib_job

router = APIRouter()

@router.post("/{task_id}/stop")
def stop_task(task_id: str, db: Session = Depends(get_db)):
    """
    Stop a running task. Marks pending jobs as canceled.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status in ["completed", "stopped"]:
        return {"message": f"Task already {task.status}"}
        
    # Mark all pending jobs across all phases as canceled
    pending_jobs = db.query(Job).filter(
        Job.task_id == task_id, 
        Job.status == "pending"
    ).all()
    
    for job in pending_jobs:
        job.status = "canceled"
    
    task.status = "stopped"
    db.commit()
    
    return {"message": f"Task stopped. {len(pending_jobs)} pending jobs canceled."}


@router.post("/{task_id}/pause")
def pause_task(task_id: str, db: Session = Depends(get_db)):
    """
    Pause a running task. Workers will skip new jobs until resumed.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != "processing":
        raise HTTPException(status_code=400, detail=f"Cannot pause task with status: {task.status}")
    
    task.status = "paused"
    db.commit()
    
    return {
        "message": "Task paused. Processing will stop after current job completes.",
        "current_phase": task.current_phase
    }


@router.post("/{task_id}/resume")
def resume_task(task_id: str, db: Session = Depends(get_db)):
    """
    Resume a paused task. Re-dispatches pending jobs for current phase.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != "paused":
        raise HTTPException(status_code=400, detail=f"Cannot resume task with status: {task.status}")
    
    task.status = "processing"
    db.commit()
    
    # Re-dispatch pending jobs for current phase
    current_phase = task.current_phase
    pending_jobs = db.query(Job).filter(
        Job.task_id == task_id,
        Job.phase == current_phase,
        Job.status == "pending"
    ).all()
    
    contexts_by_key = task.contexts_json or {}
    
    for job in pending_jobs:
        if current_phase == 1:
            verify_paper_job.delay(
                job_id=job.id,
                title=job.paper_title or "",
                author=job.paper_author or "",
                year=job.paper_year or ""
            )
        elif current_phase == 2:
            contexts = contexts_by_key.get(job.citation_key, [])
            context_match_job.delay(
                job_id=job.id,
                contexts=contexts
            )
        elif current_phase == 3:
            correct_bib_job.delay(job_id=job.id)
    
    return {
        "message": f"Task resumed. {len(pending_jobs)} Phase {current_phase} jobs re-dispatched.",
        "current_phase": current_phase
    }


@router.post("/{task_id}/skip-phase")
def skip_phase(task_id: str, db: Session = Depends(get_db)):
    """
    Skip remaining jobs in current phase and move to next phase.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in ["processing", "paused"]:
        raise HTTPException(status_code=400, detail=f"Cannot skip phase for task with status: {task.status}")
    
    current_phase = task.current_phase
    if current_phase >= 3:
        raise HTTPException(status_code=400, detail="Already at final phase")
    
    # Mark remaining pending jobs as skipped
    pending_jobs = db.query(Job).filter(
        Job.task_id == task_id,
        Job.phase == current_phase,
        Job.status == "pending"
    ).all()
    
    for job in pending_jobs:
        job.status = "skipped"
        job.result_status = "skipped"
    
    # Update phase completion count
    setattr(task, f"phase_{current_phase}_completed", getattr(task, f"phase_{current_phase}_total"))
    
    # Move to next phase
    task.current_phase = current_phase + 1
    task.status = "processing"
    db.commit()
    
    # Start next phase
    from ..tasks import start_phase_2, start_phase_3, generate_final_outputs
    
    if current_phase == 1:
        start_phase_2(task_id, db)
    elif current_phase == 2:
        start_phase_3(task_id, db)
    
    return {
        "message": f"Phase {current_phase} skipped. {len(pending_jobs)} jobs marked as skipped.",
        "new_phase": current_phase + 1
    }


@router.get("/{task_id}/download/bib")
def download_corrected_bib(task_id: str, db: Session = Depends(get_db)):
    """
    Download the corrected BIB file.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.corrected_bib_content:
        raise HTTPException(status_code=404, detail="Corrected BIB not available yet")
    
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=task.corrected_bib_content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=corrected_{task_id}.bib"}
    )


@router.get("/{task_id}/download/verification-report")
def download_verification_report(task_id: str, db: Session = Depends(get_db)):
    """
    Download the verification report as Markdown.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.verification_report_md:
        raise HTTPException(status_code=404, detail="Verification report not available yet")
    
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=task.verification_report_md,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=verification_report_{task_id}.md"}
    )


@router.get("/{task_id}/download/context-report")
def download_context_report(task_id: str, db: Session = Depends(get_db)):
    """
    Download the context matching report as Markdown.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.context_report_md:
        raise HTTPException(status_code=404, detail="Context report not available yet")
    
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=task.context_report_md,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=context_report_{task_id}.md"}
    )
