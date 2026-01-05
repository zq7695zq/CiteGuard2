from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")  # pending, processing, completed, failed, paused, stopped
    
    # Phase tracking
    current_phase = Column(Integer, default=1)  # 1, 2, or 3
    phase_1_total = Column(Integer, default=0)
    phase_1_completed = Column(Integer, default=0)
    phase_2_total = Column(Integer, default=0)
    phase_2_completed = Column(Integer, default=0)
    phase_3_total = Column(Integer, default=0)
    phase_3_completed = Column(Integer, default=0)
    
    # Legacy (keep for compatibility)
    total_citations = Column(Integer, default=0)
    completed_citations = Column(Integer, default=0)
    
    # Store original content for phase transitions
    bib_content = Column(Text, nullable=True)
    tex_content = Column(Text, nullable=True)
    contexts_json = Column(JSON, nullable=True)  # Parsed contexts for each citation_key
    
    # Final outputs
    corrected_bib_content = Column(Text, nullable=True)
    verification_report = Column(JSON, nullable=True)
    context_report = Column(JSON, nullable=True)
    
    # Markdown reports
    verification_report_md = Column(Text, nullable=True)
    context_report_md = Column(Text, nullable=True)
    
    # Store aggregated report data (legacy)
    report_json = Column(JSON, nullable=True)
    
    jobs = relationship("Job", back_populates="task", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    citation_key = Column(String, index=True)
    phase = Column(Integer, default=1)  # 1, 2, or 3
    entry_type = Column(String, nullable=True)  # article, inproceedings, misc, techreport, etc.
    reference_type = Column(String, default="academic_paper")  # academic_paper, web_resource, technical_report, arxiv_preprint
    
    status = Column(String, default="pending")  # pending, processing, completed, failed, canceled, skipped
    result_status = Column(String, nullable=True)  # verified, fake, context_match, context_mismatch, corrected, web_verified, technical_report, arxiv_verified
    
    # Phase 1 results (Paper Verification)
    paper_title = Column(String, nullable=True)
    paper_author = Column(String, nullable=True)
    paper_year = Column(String, nullable=True)
    paper_abstract = Column(Text, nullable=True)  # Saved for Phase 2
    is_verified = Column(Boolean, default=False)
    verification_message = Column(String, nullable=True)
    verified_info = Column(JSON, nullable=True)  # Full paper info from API
    
    # Phase 2 results (Context Matching)
    context_matches = Column(JSON, default=list)
    
    # Phase 3 results (BIB Correction)
    original_bib = Column(Text, nullable=True)
    corrected_bib = Column(Text, nullable=True)
    bib_changes = Column(JSON, default=list)  # List of changes made
    
    # Logging
    logs = Column(JSON, default=list)
    retry_count = Column(Integer, default=0)
    error_message = Column(String, nullable=True)
    
    task = relationship("Task", back_populates="jobs")
