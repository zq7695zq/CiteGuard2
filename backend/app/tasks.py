import asyncio
import os
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from .celery_app import celery_app
from .database import SessionLocal
from .models import Task, Job
from .core.citeguard.bib_parser import BibParser
from .core.citeguard.paper_search import PaperSearcher
from .core.citeguard.latex_parser import LatexParser
from .core.citeguard.llm_client import LLMClient
from .config import settings

logger = logging.getLogger(__name__)

def get_db_session():
    return SessionLocal()


def detect_reference_type(entry) -> str:
    """
    Detect special reference types that need different verification handling.
    
    Returns:
        - "web_resource": @misc with URL (GitHub repos, datasets, websites)
        - "technical_report": @techreport (industry reports, whitepapers)
        - "arxiv_preprint": arXiv preprints (detected by arXiv ID in doi/url/journal)
        - "academic_paper": Normal papers (default, use Crossref/Semantic Scholar)
    """
    entry_type = entry.entry_type.lower() if entry.entry_type else ""
    
    # Check for arXiv preprints first (can be in various entry types)
    arxiv_indicators = [
        entry.doi or "",
        entry.url or "",
        getattr(entry, 'journal', "") or "",
        getattr(entry, 'eprint', "") or "",
    ]
    for indicator in arxiv_indicators:
        if "arxiv" in indicator.lower():
            return "arxiv_preprint"
    
    # Check for web resources (@misc with URL/howpublished)
    if entry_type == "misc":
        if entry.url or getattr(entry, 'howpublished', ''):
            return "web_resource"
    
    # Check for technical reports
    if entry_type == "techreport":
        return "technical_report"
    
    # Default to academic paper
    return "academic_paper"


# =============================================================================
# SUBMISSION PROCESSING - Creates Phase 1 Jobs
# =============================================================================

@celery_app.task(bind=True)
def process_submission(self, task_id: str, bib_content: str, tex_content: str = None):
    """
    Parse BIB/TEX and create Phase 1 jobs for each citation.
    """
    db = get_db_session()
    task_record = db.query(Task).filter(Task.id == task_id).first()
    
    if not task_record:
        logger.error(f"Task {task_id} not found.")
        db.close()
        return

    try:
        task_record.status = "processing"
        task_record.bib_content = bib_content
        task_record.tex_content = tex_content
        db.commit()

        # 1. Parse BIB
        bib_parser = BibParser()
        bib_entries = bib_parser.parse_string(bib_content)
        
        task_record.total_citations = len(bib_entries)
        task_record.phase_1_total = len(bib_entries)
        task_record.phase_2_total = len(bib_entries)
        task_record.phase_3_total = len(bib_entries)
        db.commit()

        # 2. Parse TEX (if provided) to get contexts
        contexts_by_key = {}
        if tex_content:
            latex_parser = LatexParser()
            citations_in_tex = latex_parser.parse_string(tex_content)
            for key, ctx_list in citations_in_tex.items():
                contexts_by_key[key] = [
                    {
                        "sentence": c.sentence,
                        "line_number": c.line_number,
                        "section": c.section
                    }
                    for c in ctx_list
                ]
        
        task_record.contexts_json = contexts_by_key
        db.commit()

        # 3. Create Phase 1 jobs and dispatch
        for entry in bib_entries:
            # Detect special reference types
            ref_type = detect_reference_type(entry)
            
            job = Job(
                task_id=task_id,
                citation_key=entry.cite_key,
                phase=1,
                status="pending",
                entry_type=entry.entry_type,
                reference_type=ref_type,
                paper_title=entry.title,
                paper_author=entry.author,
                paper_year=entry.year,
                original_bib=entry.to_bibtex(),
            )
            db.add(job)
            db.commit()
            
            # Dispatch Phase 1 job with extra info for special types
            verify_paper_job.delay(
                job_id=job.id,
                title=entry.title,
                author=entry.author,
                year=entry.year,
                reference_type=ref_type,
                url=entry.url or getattr(entry, 'howpublished', ''),
                doi=entry.doi
            )
            
    except Exception as e:
        logger.error(f"Error processing submission {task_id}: {e}")
        task_record.status = "failed"
        db.commit()
    finally:
        db.close()


# =============================================================================
# PHASE 1: Paper Verification
# =============================================================================

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def verify_paper_job(self, job_id: int, title: str, author: str, year: str, 
                     reference_type: str = "academic_paper", url: str = "", doi: str = ""):
    """
    Phase 1: Verify paper existence based on reference type.
    - academic_paper: Use Semantic Scholar / Crossref
    - web_resource: Verify URL accessibility
    - technical_report: Mark as valid (not in academic databases)
    - arxiv_preprint: Search arXiv API
    """
    db = get_db_session()
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        db.close()
        return

    # Check task status before processing
    task = db.query(Task).filter(Task.id == job.task_id).first()
    if task:
        if task.status == "stopped":
            job.status = "canceled"
            db.commit()
            db.close()
            logger.info(f"Job {job_id} canceled: task stopped")
            return
        elif task.status == "paused":
            db.close()
            logger.info(f"Job {job_id} skipped: task paused")
            return

    try:
        job.status = "processing"
        db.commit()

        paper_searcher = PaperSearcher()
        ref_type = reference_type or job.reference_type or "academic_paper"
        
        log_job_event(job.id, f"Phase 1: Verifying as {ref_type}...", db)
        
        # Handle different reference types
        if ref_type == "web_resource":
            # Web resource: just verify URL exists
            resource_url = url or ""
            if not resource_url:
                job.is_verified = True  # Accept if no URL to check
                job.result_status = "web_resource"
                job.verification_message = "Web resource (no URL to verify)"
            else:
                log_job_event(job.id, f"Checking URL: {resource_url[:50]}...", db)
                is_valid, msg = paper_searcher.verify_url(resource_url)
                job.is_verified = is_valid
                job.result_status = "web_verified" if is_valid else "url_error"
                job.verification_message = f"Web resource: {msg}"
            log_job_event(job.id, f"{'✅' if job.is_verified else '⚠️'} {job.verification_message}", db)
        
        elif ref_type == "technical_report":
            # Technical report: accept without academic verification
            job.is_verified = True
            job.result_status = "technical_report"
            job.verification_message = "Technical report (not in academic databases, accepted as-is)"
            log_job_event(job.id, f"✅ {job.verification_message}", db)
        
        elif ref_type == "arxiv_preprint":
            # arXiv preprint: search arXiv API
            log_job_event(job.id, f"Searching arXiv for: '{title}'...", db)
            
            # Try to extract arXiv ID from doi or journal field
            arxiv_id = None
            for field in [doi, job.original_bib or ""]:
                import re
                match = re.search(r'arxiv[:\s]*(\d+\.\d+)', field.lower())
                if match:
                    arxiv_id = match.group(1)
                    break
            
            paper_info = paper_searcher.search_arxiv(title=title, arxiv_id=arxiv_id)
            
            if paper_info and paper_info.is_verified:
                job.is_verified = True
                job.result_status = "arxiv_verified"
                job.paper_abstract = paper_info.abstract
                job.verified_info = {
                    "title": paper_info.title,
                    "authors": paper_info.authors,
                    "year": paper_info.year,
                    "venue": "arXiv",
                    "doi": paper_info.doi,
                    "url": paper_info.url,
                    "abstract": paper_info.abstract
                }
                job.verification_message = f"arXiv preprint verified (similarity: {paper_info.similarity_score:.2%})"
                log_job_event(job.id, f"✅ {job.verification_message}", db)
            else:
                # Fallback to regular academic search
                log_job_event(job.id, "arXiv not found, trying academic search...", db)
                is_verified, paper_info, message = paper_searcher.verify_paper(title, author, year)
                job.is_verified = is_verified
                job.result_status = "verified" if is_verified else "not_found"
                job.verification_message = message
                if is_verified and paper_info:
                    job.paper_abstract = paper_info.abstract
                    job.verified_info = {
                        "title": paper_info.title,
                        "authors": paper_info.authors,
                        "year": paper_info.year,
                        "venue": getattr(paper_info, 'venue', None),
                        "doi": getattr(paper_info, 'doi', None),
                        "abstract": job.paper_abstract
                    }
                log_job_event(job.id, f"{'✅' if is_verified else '❌'} {message}", db)
        
        else:
            # Default: academic paper verification
            log_job_event(job.id, f"Searching for: '{title}' by {author}...", db)
            is_verified, paper_info, message = paper_searcher.verify_paper(
                title=title,
                author=author,
                year=year
            )
            
            job.is_verified = is_verified
            job.verification_message = message
            job.result_status = "verified" if is_verified else "not_found"
            
            if is_verified and paper_info:
                job.paper_abstract = paper_info.abstract if hasattr(paper_info, 'abstract') else None
                job.verified_info = {
                    "title": paper_info.title if hasattr(paper_info, 'title') else title,
                    "authors": paper_info.authors if hasattr(paper_info, 'authors') else author,
                    "year": paper_info.year if hasattr(paper_info, 'year') else year,
                    "venue": getattr(paper_info, 'venue', None),
                    "doi": getattr(paper_info, 'doi', None),
                    "abstract": job.paper_abstract
                }
                log_job_event(job.id, f"✅ Paper verified: {message}", db)
            else:
                log_job_event(job.id, f"❌ Paper not found: {message}", db)
        
        job.status = "completed"
        db.commit()
        
        # Update phase progress and check completion
        check_phase_completion(job.task_id, 1, db)

    except Exception as e:
        logger.error(f"Error verifying job {job_id}: {e}")
        job.status = "failed"
        job.error_message = str(e)
        job.retry_count += 1
        log_job_event(job.id, f"❌ Error: {str(e)}", db)
        db.commit()
        raise e
    finally:
        db.close()


# =============================================================================
# PHASE 2: Context Matching
# =============================================================================

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def context_match_job(self, job_id: int, contexts: list):
    """
    Phase 2: Match citation contexts with paper abstract using LLM.
    """
    db = get_db_session()
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        db.close()
        return

    # Check task status
    task = db.query(Task).filter(Task.id == job.task_id).first()
    if task:
        if task.status == "stopped":
            job.status = "canceled"
            db.commit()
            db.close()
            return
        elif task.status == "paused":
            db.close()
            return

    try:
        job.status = "processing"
        db.commit()

        log_job_event(job.id, "Phase 2: Starting context matching...", db)
        
        # Get Phase 1 job to retrieve abstract
        phase1_job = db.query(Job).filter(
            Job.task_id == job.task_id,
            Job.citation_key == job.citation_key,
            Job.phase == 1
        ).first()
        
        if not phase1_job or not phase1_job.is_verified:
            log_job_event(job.id, "⊘ Skipping: Paper not verified in Phase 1", db)
            job.status = "completed"
            job.result_status = "skipped"
            db.commit()
            check_phase_completion(job.task_id, 2, db)
            return
        
        abstract = phase1_job.paper_abstract
        if not abstract:
            log_job_event(job.id, "⊘ Skipping: No abstract available", db)
            job.status = "completed"
            job.result_status = "skipped"
            db.commit()
            check_phase_completion(job.task_id, 2, db)
            return
        
        if not contexts:
            log_job_event(job.id, "⊘ No contexts to match", db)
            job.status = "completed"
            job.result_status = "no_contexts"
            db.commit()
            check_phase_completion(job.task_id, 2, db)
            return
        
        llm_client = LLMClient(api_key=settings.SILICONFLOW_API_KEY)
        job_contexts = []
        all_match = True
        
        for i, ctx in enumerate(contexts):
            log_job_event(job.id, f"Checking context {i+1}/{len(contexts)}...", db)
            
            match_result = llm_client.check_context_match(
                paper_abstract=abstract,
                citation_context=ctx.get('sentence', ''),
                paper_title=phase1_job.paper_title or ""
            )
            
            context_result = {
                "context": ctx.get('sentence', ''),
                "line_number": ctx.get('line_number', 0),
                "section": ctx.get('section', ''),
                "is_match": match_result.is_match,
                "confidence": match_result.confidence,
                "explanation": match_result.explanation,
                "suggestion": match_result.suggestion
            }
            job_contexts.append(context_result)
            
            if not match_result.is_match:
                all_match = False
                log_job_event(job.id, f"⚠️ Context mismatch at line {ctx.get('line_number', '?')}", db)
            else:
                log_job_event(job.id, f"✅ Context matches", db)
        
        job.context_matches = job_contexts
        job.result_status = "context_match" if all_match else "context_mismatch"
        job.status = "completed"
        db.commit()
        
        log_job_event(job.id, f"Phase 2 complete: {'All contexts match' if all_match else 'Some mismatches found'}", db)
        
        check_phase_completion(job.task_id, 2, db)

    except Exception as e:
        logger.error(f"Error in context match job {job_id}: {e}")
        job.status = "failed"
        job.error_message = str(e)
        job.retry_count += 1
        log_job_event(job.id, f"❌ Error: {str(e)}", db)
        db.commit()
        raise e
    finally:
        db.close()


# =============================================================================
# PHASE 3: BIB Correction
# =============================================================================

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def correct_bib_job(self, job_id: int):
    """
    Phase 3: Correct BIB entry format using LLM.
    """
    db = get_db_session()
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        db.close()
        return

    # Check task status
    task = db.query(Task).filter(Task.id == job.task_id).first()
    if task:
        if task.status == "stopped":
            job.status = "canceled"
            db.commit()
            db.close()
            return
        elif task.status == "paused":
            db.close()
            return

    try:
        job.status = "processing"
        db.commit()

        log_job_event(job.id, "Phase 3: Starting BIB correction...", db)
        
        # Get Phase 1 job for verified info and original bib
        phase1_job = db.query(Job).filter(
            Job.task_id == job.task_id,
            Job.citation_key == job.citation_key,
            Job.phase == 1
        ).first()
        
        if not phase1_job:
            log_job_event(job.id, "⊘ No Phase 1 data found", db)
            job.status = "completed"
            job.result_status = "skipped"
            db.commit()
            check_phase_completion(job.task_id, 3, db)
            return
        
        original_bib = phase1_job.original_bib
        verified_info = phase1_job.verified_info or {}
        
        if not original_bib:
            log_job_event(job.id, "⊘ No original BIB to correct", db)
            job.status = "completed"
            job.result_status = "skipped"
            db.commit()
            check_phase_completion(job.task_id, 3, db)
            return
        
        llm_client = LLMClient(api_key=settings.SILICONFLOW_API_KEY)
        
        log_job_event(job.id, "Correcting BIB entry with verified info...", db)
        
        # Determine entry type from original bib
        entry_type = "article"  # default
        if "@inproceedings" in original_bib.lower():
            entry_type = "inproceedings"
        elif "@book" in original_bib.lower():
            entry_type = "book"
        
        correction_result = llm_client.correct_bib_entry(
            original_bib=original_bib,
            verified_info=verified_info,
            entry_type=entry_type
        )
        
        job.original_bib = original_bib
        job.corrected_bib = correction_result.corrected_bib
        job.bib_changes = correction_result.changes
        job.result_status = "corrected"
        job.status = "completed"
        db.commit()
        
        if correction_result.changes:
            log_job_event(job.id, f"✅ BIB corrected: {len(correction_result.changes)} changes", db)
            for change in correction_result.changes[:3]:  # Log first 3 changes
                log_job_event(job.id, f"  • {change}", db)
        else:
            log_job_event(job.id, "✅ BIB already correct, no changes needed", db)
        
        check_phase_completion(job.task_id, 3, db)

    except Exception as e:
        logger.error(f"Error in BIB correction job {job_id}: {e}")
        job.status = "failed"
        job.error_message = str(e)
        job.retry_count += 1
        log_job_event(job.id, f"❌ Error: {str(e)}", db)
        db.commit()
        raise e
    finally:
        db.close()


# =============================================================================
# PHASE MANAGEMENT
# =============================================================================

def check_phase_completion(task_id: str, phase: int, db: Session):
    """
    Check if all jobs in a phase are complete. If so, start the next phase.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return
    
    # Count completed jobs for this phase
    completed = db.query(Job).filter(
        Job.task_id == task_id,
        Job.phase == phase,
        Job.status.in_(["completed", "failed", "canceled", "skipped"])
    ).count()
    
    total = getattr(task, f"phase_{phase}_total", 0)
    setattr(task, f"phase_{phase}_completed", completed)
    
    # Update legacy fields
    task.completed_citations = (
        task.phase_1_completed + task.phase_2_completed + task.phase_3_completed
    ) // 3
    
    db.commit()
    
    # Check if phase is complete
    if completed >= total and total > 0:
        logger.info(f"Task {task_id}: Phase {phase} complete ({completed}/{total})")
        
        if phase == 1:
            # Start Phase 2
            start_phase_2(task_id, db)
        elif phase == 2:
            # Start Phase 3
            start_phase_3(task_id, db)
        elif phase == 3:
            # All done, generate final outputs
            generate_final_outputs(task_id, db)


def start_phase_2(task_id: str, db: Session):
    """
    Start Phase 2 (Context Matching) for all citations.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return
    
    if task.status in ["stopped", "paused"]:
        return
    
    task.current_phase = 2
    db.commit()
    
    logger.info(f"Task {task_id}: Starting Phase 2")
    
    # Get all Phase 1 jobs to create Phase 2 jobs
    phase1_jobs = db.query(Job).filter(
        Job.task_id == task_id,
        Job.phase == 1
    ).all()
    
    contexts_by_key = task.contexts_json or {}
    
    for p1_job in phase1_jobs:
        # Create Phase 2 job
        job = Job(
            task_id=task_id,
            citation_key=p1_job.citation_key,
            phase=2,
            status="pending",
            paper_title=p1_job.paper_title,
        )
        db.add(job)
        db.commit()
        
        contexts = contexts_by_key.get(p1_job.citation_key, [])
        
        # Dispatch Phase 2 job
        context_match_job.delay(
            job_id=job.id,
            contexts=contexts
        )


def start_phase_3(task_id: str, db: Session):
    """
    Start Phase 3 (BIB Correction) for all citations.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return
    
    if task.status in ["stopped", "paused"]:
        return
    
    task.current_phase = 3
    db.commit()
    
    logger.info(f"Task {task_id}: Starting Phase 3")
    
    # Get all Phase 1 jobs to create Phase 3 jobs
    phase1_jobs = db.query(Job).filter(
        Job.task_id == task_id,
        Job.phase == 1
    ).all()
    
    for p1_job in phase1_jobs:
        # Create Phase 3 job
        job = Job(
            task_id=task_id,
            citation_key=p1_job.citation_key,
            phase=3,
            status="pending",
            paper_title=p1_job.paper_title,
        )
        db.add(job)
        db.commit()
        
        # Dispatch Phase 3 job
        correct_bib_job.delay(job_id=job.id)


def generate_final_outputs(task_id: str, db: Session):
    """
    Generate final outputs after all phases complete.
    Includes JSON reports and Markdown formatted reports.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return
    
    logger.info(f"Task {task_id}: Generating final outputs")
    
    # Collect all Phase 3 jobs for corrected BIB
    phase3_jobs = db.query(Job).filter(
        Job.task_id == task_id,
        Job.phase == 3,
        Job.status == "completed"
    ).all()
    
    # Build corrected BIB content
    corrected_bibs = []
    for job in phase3_jobs:
        if job.corrected_bib:
            corrected_bibs.append(job.corrected_bib)
        elif job.original_bib:
            # Fallback to original if no correction
            corrected_bibs.append(job.original_bib)
    
    task.corrected_bib_content = "\n\n".join(corrected_bibs)
    
    # Build verification report
    phase1_jobs = db.query(Job).filter(
        Job.task_id == task_id,
        Job.phase == 1
    ).all()
    
    # Categorize by reference type
    academic_verified = [j for j in phase1_jobs if j.is_verified and j.reference_type == "academic_paper"]
    academic_not_found = [j for j in phase1_jobs if not j.is_verified and j.reference_type == "academic_paper"]
    web_resources = [j for j in phase1_jobs if j.reference_type == "web_resource"]
    tech_reports = [j for j in phase1_jobs if j.reference_type == "technical_report"]
    arxiv_papers = [j for j in phase1_jobs if j.reference_type == "arxiv_preprint"]
    
    verification_report = {
        "summary": {
            "total": len(phase1_jobs),
            "verified": sum(1 for j in phase1_jobs if j.is_verified),
            "not_found": sum(1 for j in phase1_jobs if not j.is_verified),
            "by_type": {
                "academic_papers": {"verified": len(academic_verified), "not_found": len(academic_not_found)},
                "web_resources": len(web_resources),
                "technical_reports": len(tech_reports),
                "arxiv_preprints": len(arxiv_papers)
            }
        },
        "papers": [
            {
                "citation_key": j.citation_key,
                "title": j.paper_title,
                "reference_type": j.reference_type,
                "is_verified": j.is_verified,
                "status": j.result_status,
                "message": j.verification_message
            }
            for j in phase1_jobs
        ]
    }
    task.verification_report = verification_report
    
    # Generate Markdown verification report
    task.verification_report_md = generate_verification_markdown(phase1_jobs, verification_report["summary"])
    
    # Build context report
    phase2_jobs = db.query(Job).filter(
        Job.task_id == task_id,
        Job.phase == 2
    ).all()
    
    context_report = {
        "summary": {
            "total": len(phase2_jobs),
            "all_match": sum(1 for j in phase2_jobs if j.result_status == "context_match"),
            "has_mismatch": sum(1 for j in phase2_jobs if j.result_status == "context_mismatch"),
            "skipped": sum(1 for j in phase2_jobs if j.result_status in ["skipped", "no_contexts"])
        },
        "papers": [
            {
                "citation_key": j.citation_key,
                "title": j.paper_title,
                "status": j.result_status,
                "context_matches": j.context_matches
            }
            for j in phase2_jobs
        ]
    }
    task.context_report = context_report
    
    # Generate Markdown context report
    task.context_report_md = generate_context_markdown(phase2_jobs, context_report["summary"])
    
    task.status = "completed"
    db.commit()
    
    logger.info(f"Task {task_id}: Completed! Verification: {verification_report['summary']}, Context: {context_report['summary']}")


def generate_verification_markdown(phase1_jobs, summary):
    """Generate Markdown formatted verification report."""
    lines = [
        "# Citation Verification Report",
        f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        "## Summary\n",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total Citations | {summary['total']} |",
        f"| ✅ Verified | {summary['verified']} |",
        f"| ❌ Not Found | {summary['not_found']} |",
        "",
    ]
    
    # By type breakdown
    by_type = summary.get('by_type', {})
    if by_type:
        lines.extend([
            "### By Reference Type\n",
            f"- **Academic Papers**: {by_type.get('academic_papers', {}).get('verified', 0)} verified, {by_type.get('academic_papers', {}).get('not_found', 0)} not found",
            f"- **Web Resources**: {by_type.get('web_resources', 0)}",
            f"- **Technical Reports**: {by_type.get('technical_reports', 0)}",
            f"- **arXiv Preprints**: {by_type.get('arxiv_preprints', 0)}",
            ""
        ])
    
    # Verified papers
    verified = [j for j in phase1_jobs if j.is_verified]
    if verified:
        lines.append("\n## ✅ Verified Papers\n")
        for j in verified:
            ref_badge = f"[{j.reference_type}]" if j.reference_type != "academic_paper" else ""
            lines.extend([
                f"### {j.citation_key} {ref_badge}",
                f"**{j.paper_title or 'No title'}**",
                f"- Status: {j.result_status}",
                f"- {j.verification_message or 'Verified'}",
                ""
            ])
    
    # Not found papers
    not_found = [j for j in phase1_jobs if not j.is_verified]
    if not_found:
        lines.append("\n## ❌ Not Found (Needs Review)\n")
        for j in not_found:
            lines.extend([
                f"### {j.citation_key}",
                f"**{j.paper_title or 'No title'}**",
                f"- {j.verification_message or 'Paper not found in academic databases'}",
                ""
            ])
    
    return "\n".join(lines)


def generate_context_markdown(phase2_jobs, summary):
    """Generate Markdown formatted context matching report."""
    lines = [
        "# Context Matching Report",
        f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        "## Summary\n",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total | {summary['total']} |",
        f"| ✅ All Contexts Match | {summary['all_match']} |",
        f"| ⚠️ Has Mismatch | {summary['has_mismatch']} |",
        f"| ⊘ Skipped | {summary['skipped']} |",
        ""
    ]
    
    # Papers with mismatches (show first)
    mismatches = [j for j in phase2_jobs if j.result_status == "context_mismatch"]
    if mismatches:
        lines.append("\n## ⚠️ Context Mismatches\n")
        for j in mismatches:
            lines.extend([
                f"### {j.citation_key}",
                f"**{j.paper_title or 'No title'}**\n"
            ])
            for ctx in (j.context_matches or []):
                if not ctx.get('is_match', True):
                    lines.extend([
                        f"#### Line {ctx.get('line_number', '?')} - Mismatch",
                        f"> \"{ctx.get('context', '')[:200]}...\"",
                        f"",
                        f"**Explanation**: {ctx.get('explanation', 'N/A')}",
                        f"",
                        f"**Suggestion**: {ctx.get('suggestion', 'N/A')}",
                        ""
                    ])
    
    # Papers with all matches
    matches = [j for j in phase2_jobs if j.result_status == "context_match"]
    if matches:
        lines.append("\n## ✅ All Contexts Match\n")
        for j in matches:
            lines.append(f"- **{j.citation_key}**: {j.paper_title or 'No title'}")
    
    # Skipped
    skipped = [j for j in phase2_jobs if j.result_status in ["skipped", "no_contexts"]]
    if skipped:
        lines.append("\n## ⊘ Skipped (No contexts or unverified paper)\n")
        for j in skipped:
            lines.append(f"- {j.citation_key}")
    
    return "\n".join(lines)




# =============================================================================
# UTILITIES
# =============================================================================

def log_job_event(job_id: int, message: str, db: Session):
    """Append a log message to the job's log list."""
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            current_logs = list(job.logs) if job.logs else []
            timestamp = datetime.now().strftime("%H:%M:%S")
            current_logs.append(f"[{timestamp}] {message}")
            job.logs = current_logs
            db.add(job)
            db.commit()
            db.refresh(job)
    except Exception as e:
        logger.error(f"Failed to log event for job {job_id}: {e}")


def update_task_progress(task_id: str, db: Session):
    """Update task completion count and status (legacy)."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return
        
    total = task.total_citations
    completed = db.query(Job).filter(
        Job.task_id == task_id, 
        Job.status.in_(["completed", "failed"])
    ).count()
    
    task.completed_citations = completed
    
    if total > 0 and completed >= total:
        task.status = "completed"
    
    db.commit()
