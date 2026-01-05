from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from uuid import uuid4
from ..database import get_db
from ..models import Task
from ..tasks import process_submission
import aiofiles
import os
import io

router = APIRouter()

@router.post("/")
async def submit_files(
    bib_file: UploadFile = File(...),
    tex_files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db)
):
    """
    Submit BIB matches and optional TEX files for processing.
    """
    task_id = str(uuid4())
    
    # Read BIB content
    bib_content = await bib_file.read()
    bib_text = bib_content.decode("utf-8")
    
    # Read TEX content (combine multiple files for simplicity in this prototype)
    tex_text = ""
    for tf in tex_files:
        content = await tf.read()
        tex_text += content.decode("utf-8") + "\n"
    
    # Create Task Record
    task = Task(id=task_id, status="pending", total_citations=0)
    db.add(task)
    db.commit()
    
    # Trigger Celery Task
    process_submission.delay(task_id, bib_text, tex_text)
    
    return {"task_id": task_id, "message": "Submission received"}
