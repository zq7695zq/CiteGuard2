import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Task, Job

router = APIRouter()

@router.get("/{task_id}")
def get_status(task_id: str, db: Session = Depends(get_db)):
    """
    Get the status and progress of a task.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "id": task.id,
        "status": task.status,
        "current_phase": task.current_phase,
        "phases": {
            "1": {
                "name": "Paper Verification",
                "total": task.phase_1_total,
                "completed": task.phase_1_completed
            },
            "2": {
                "name": "Context Matching", 
                "total": task.phase_2_total,
                "completed": task.phase_2_completed
            },
            "3": {
                "name": "BIB Correction",
                "total": task.phase_3_total,
                "completed": task.phase_3_completed
            }
        },
        "total": task.total_citations,
        "completed": task.completed_citations,
        "progress": (task.completed_citations / task.total_citations * 100) if task.total_citations > 0 else 0
    }

@router.get("/{task_id}/details")
def get_details(task_id: str, db: Session = Depends(get_db)):
    """
    Get detailed job results for a task, grouped by citation key.
    """
    jobs = db.query(Job).filter(Job.task_id == task_id).all()
    
    # Group jobs by citation_key
    papers = {}
    for j in jobs:
        if j.citation_key not in papers:
            papers[j.citation_key] = {
                "citation_key": j.citation_key,
                "title": j.paper_title,
                "phases": {}
            }
        
        papers[j.citation_key]["phases"][str(j.phase)] = {
            "status": j.status,
            "result_status": j.result_status,
            "logs": j.logs,
            # Phase 1 specific
            "is_verified": j.is_verified if j.phase == 1 else None,
            "verification_message": j.verification_message if j.phase == 1 else None,
            "paper_abstract": j.paper_abstract if j.phase == 1 else None,
            # Phase 2 specific
            "context_matches": j.context_matches if j.phase == 2 else None,
            # Phase 3 specific
            "original_bib": j.original_bib if j.phase == 3 else None,
            "corrected_bib": j.corrected_bib if j.phase == 3 else None,
            "bib_changes": j.bib_changes if j.phase == 3 else None,
        }
    
    return {
        "task_id": task_id,
        "papers": list(papers.values())
    }

@router.get("/{task_id}/outputs")
def get_outputs(task_id: str, db: Session = Depends(get_db)):
    """
    Get final outputs (corrected BIB, reports) after task completion.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "task_id": task_id,
        "status": task.status,
        "corrected_bib": task.corrected_bib_content,
        "verification_report": task.verification_report,
        "context_report": task.context_report
    }

@router.get("/{task_id}/stream")
async def stream_task_logs(task_id: str):
    """
    Stream logs and status updates for a task using SSE.
    """
    async def event_generator():
        while True:
            db = next(get_db())
            try:
                task = db.query(Task).filter(Task.id == task_id).first()
                if not task:
                    yield f"event: error\ndata: Task not found\n\n"
                    break
                
                jobs = db.query(Job).filter(Job.task_id == task_id).all()
                
                # Group jobs by citation_key for frontend
                papers = {}
                for j in jobs:
                    if j.citation_key not in papers:
                        papers[j.citation_key] = {
                            "citation_key": j.citation_key,
                            "title": j.paper_title,
                            "phases": {}
                        }
                    
                    papers[j.citation_key]["phases"][str(j.phase)] = {
                        "status": j.status,
                        "result_status": j.result_status,
                        "logs": j.logs,
                        "is_verified": j.is_verified if j.phase == 1 else None,
                        "verification_message": j.verification_message if j.phase == 1 else None,
                        "paper_abstract": j.paper_abstract[:200] + "..." if j.phase == 1 and j.paper_abstract and len(j.paper_abstract) > 200 else (j.paper_abstract if j.phase == 1 else None),
                        "context_matches": j.context_matches if j.phase == 2 else None,
                        "original_bib": j.original_bib if j.phase == 3 else None,
                        "corrected_bib": j.corrected_bib if j.phase == 3 else None,
                        "bib_changes": j.bib_changes if j.phase == 3 else None,
                    }
                
                # Construct payload
                payload = {
                    "task_status": task.status,
                    "current_phase": task.current_phase,
                    "phases": {
                        "1": {
                            "name": "Paper Verification",
                            "total": task.phase_1_total,
                            "completed": task.phase_1_completed
                        },
                        "2": {
                            "name": "Context Matching",
                            "total": task.phase_2_total,
                            "completed": task.phase_2_completed
                        },
                        "3": {
                            "name": "BIB Correction",
                            "total": task.phase_3_total,
                            "completed": task.phase_3_completed
                        }
                    },
                    "total": task.total_citations,
                    "completed": task.completed_citations,
                    "papers": list(papers.values()),
                    # Include outputs if completed
                    "outputs": {
                        "corrected_bib": task.corrected_bib_content is not None,
                        "verification_report": task.verification_report is not None,
                        "context_report": task.context_report is not None
                    } if task.status == "completed" else None
                }
                
                yield f"data: {json.dumps(payload)}\n\n"
                
                if task.status in ["completed", "failed", "stopped"]:
                    if task.status == "completed":
                        yield f"event: complete\ndata: Task completed\n\n"
                
            except Exception as e:
                yield f"event: error\ndata: {str(e)}\n\n"
            finally:
                db.close()
            
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
