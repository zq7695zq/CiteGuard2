# 中文注释：本文件(backend/app/demo/run_demo.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./demo.db"
os.environ["STORAGE_ROOT"] = "./demo_storage"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["ZOTERO_SNAPSHOT_PATH"] = "./fixtures/zotero_snapshot.json"

from app.db.models import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.orchestrator.jobs import create_job  # noqa: E402
from app.worker.tasks import process_job  # noqa: E402


def main() -> None:
    Base.metadata.create_all(bind=engine)
    root = Path(__file__).resolve().parents[2] / ".." / "fixtures"
    paper_text = (root / "sample_paper.txt").read_text(encoding="utf-8")
    bib_text = (root / "sample_refs.bib").read_text(encoding="utf-8")
    job_id = create_job(paper_text, bib_text, {})
    process_job(job_id)
    print(f"Demo job completed: {job_id}")


if __name__ == "__main__":
    main()
