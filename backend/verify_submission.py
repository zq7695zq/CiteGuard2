import os
import time
import glob
from app.database import SessionLocal
from app.models import Task, Job
from app.tasks import process_submission
from app.celery_app import celery_app

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def main():
    print("Starting verification...")
    
    # 1. Load Data
    data_dir = r"d:\CiteGuard\data"
    ref_dir = r"d:\CiteGuard\ref"
    
    bib_path = os.path.join(ref_dir, "refs.bib")
    if not os.path.exists(bib_path):
        print(f"Error: {bib_path} not found.")
        return

    print(f"Reading BIB file: {bib_path}")
    bib_content = read_file(bib_path)
    
    tex_content = ""
    tex_files = glob.glob(os.path.join(data_dir, "*.tex"))
    print(f"Found {len(tex_files)} TEX files in {data_dir}")
    
    for tex_file in tex_files:
        print(f"Reading TEX file: {tex_file}")
        tex_content += read_file(tex_file) + "\n"
        
    # 2. Submit Task
    print("Submitting task to Celery...")
    
    # Create Task record directly first (usually API does this)
    db = SessionLocal()
    task_id = "verify_test_" + str(int(time.time()))
    new_task = Task(id=task_id, status="pending")
    db.add(new_task)
    db.commit()
    db.close()
    
    # Submit to Celery
    async_result = process_submission.delay(task_id, bib_content, tex_content)
    print(f"Task submitted. Celery ID: {async_result.id}, Database Task ID: {task_id}")
    
    # 3. Poll Status
    print("Polling task status...")
    max_retries = 60
    for i in range(max_retries):
        db = SessionLocal()
        task = db.query(Task).filter(Task.id == task_id).first()
        Jobs = db.query(Job).filter(Job.task_id == task_id).all()
        completed_jobs = [j for j in Jobs if j.status in ["completed", "failed"]]
        
        print(f"[{i+1}/{max_retries}] Task Status: {task.status}, Jobs: {len(completed_jobs)}/{task.total_citations if task.total_citations else '?'}")
        
        if task.status == "completed":
            print("\nTask Completed Successfully!")
            print(f"Total Citations: {task.total_citations}")
            print(f"Verified Jobs: {len([j for j in Jobs if j.result_status == 'verified'])}")
            print(f"Fake/Failed Jobs: {len([j for j in Jobs if j.result_status != 'verified'])}")
            break
        elif task.status == "failed":
            print("\nTask Failed!")
            break
            
        db.close()
        time.sleep(2)
    else:
        print("\nTimeout waiting for task completion.")

if __name__ == "__main__":
    main()
