# 中文注释：本文件(backend/app/worker/tasks.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
# 中文注释：这里集中处理任务拉取、执行、事件落库、产物写入、失败重试与心跳/看门狗机制，是任务编排的执行核心。
from __future__ import annotations
import json
from datetime import datetime, timedelta
from pydantic import ValidationError
from sqlalchemy import select, update, func
from app.core.schemas import BibEntry, Evidence, ContextMatchResult, BibPatch
from app.core.scoring import score_bib
from app.core.diff import build_metadata_diff
from app.core.bib_writer import build_fixed_bib
from app.db.models import Task, Job, Artifact
from app.db.session import SessionLocal
from app.llm.agents import run_main_agent, run_match_agent
from app.storage.fs import Storage
from app.sse.events import emit_event
from app.worker.celery_app import celery_app
from app.tools import zotero, crossref


RETRYABLE_CODES = {"RATE_LIMITED", "TRANSIENT_UPSTREAM"}


def enqueue_task(job_id: str) -> None:
    """中文注释：向 Celery 投递一个 job 处理任务，用于触发任务扫描。"""
    celery_app.send_task("app.worker.tasks.process_job", args=[job_id])


@celery_app.task(name="app.worker.tasks.process_job")
def process_job(job_id: str) -> None:
    """中文注释：循环拉取可执行任务，直到全部完成或暂停/取消。"""
    while True:
        task = _next_runnable_task(job_id)
        if not task:
            _maybe_finalize_job(job_id)
            break
        process_task(task.id)


@celery_app.task(name="app.worker.tasks.process_task")
def process_task(task_id: str) -> None:
    """中文注释：执行单个任务并根据结果更新状态与事件。"""
    storage = Storage()
    with SessionLocal() as session:
        task = session.get(Task, task_id)
        if not task or task.status in {"SUCCEEDED", "BLOCKED", "CANCELLED"}:
            return
        task.status = "RUNNING"
        task.heartbeat_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        session.commit()
        emit_event(task.job_id, "task_started", "info", {"task_id": task.id, "type": task.type})

    try:
        should_mark = True
        if task.type == "BIB_VERIFY":
            # 中文注释：文献真实性核验任务
            _run_bib_verify(task, storage)
        elif task.type == "OCC_MATCH":
            # 中文注释：上下文匹配任务
            _run_occ_match(task, storage)
        elif task.type == "BUILD_BIB":
            # 中文注释：汇总并生成修正后的 bib
            should_mark = _run_build_bib(task, storage)
        elif task.type == "SUMMARIZE_ARTIFACTS":
            # 中文注释：汇总报告产物并落库
            should_mark = _run_summarize(task, storage)
        else:
            raise ValueError(f"Unknown task type {task.type}")
        if should_mark:
            _mark_task_succeeded(task_id, None)
        else:
            _reset_pending(task_id)
    except Exception as exc:  # noqa: BLE001
        _mark_task_failed(task_id, exc)


def _next_runnable_task(job_id: str) -> Task | None:
    """中文注释：从数据库中获取下一个可执行任务，考虑暂停状态和重试时间。"""
    now = datetime.utcnow()
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if not job or job.status != "RUNNING":
            return None
        return (
            session.execute(
                select(Task)
                .where(
                    Task.job_id == job_id,
                    Task.status.in_(["PENDING", "RETRY_PENDING"]),
                    func.coalesce(Task.retry_after_at, now) <= now,
                )
                .order_by(Task.created_at)
            )
            .scalars()
            .first()
        )


def _run_bib_verify(task: Task, storage: Storage) -> None:
    """中文注释：执行单条 Bib 核验，调用主 Agent，计算分数并写入中间结果。"""
    _touch_heartbeat(task.id)
    bib = BibEntry.model_validate(task.payload_json["bib"])
    citations = task.payload_json.get("citations", [])
    output, tool_events = run_main_agent(task.job_id, bib, citations)
    emit_event(task.job_id, "tool_called", "info", {"count": len(tool_events)})
    if tool_events:
        emit_event(
            task.job_id,
            "tool_result",
            "info",
            {"tools": [{"name": ev["name"], "ok": ev["result"].get("ok")} for ev in tool_events]},
        )

    # 中文注释：优先使用模型选择的候选，如果为空则降级到工具检索
    candidates = []
    if output.selected_canonical:
        candidates.append(output.selected_canonical)
    candidates.extend(output.all_candidates)
    if not candidates:
        title = bib.fields.get("title")
        if title:
            try:
                zotero_result = zotero.zotero_search_items(title, limit=3)
                for item in zotero_result.get("items", []):
                    candidates.append(zotero.to_canonical(item))
                emit_event(task.job_id, "tool_result", "info", {"tools": [{"name": "zotero.search_items", "ok": True}]})
            except Exception:
                pass
            try:
                crossref_result = crossref.crossref_lookup(title=title)
                for item in crossref_result.get("items", []):
                    candidates.append(crossref.to_canonical(item))
                emit_event(task.job_id, "tool_result", "info", {"tools": [{"name": "crossref.lookup", "ok": True}]})
            except Exception:
                pass
    selected = output.selected_canonical or (candidates[0] if candidates else None)

    evidence_records = []
    sources = set()
    for candidate in candidates:
        sources.add(candidate.source)
        evidence_records.append(
            {
                "source": candidate.source,
                "id": candidate.id,
                "doi": candidate.doi,
                "url": candidate.url,
            }
        )

    if selected:
        score = score_bib(bib, selected)
        status = "real" if score.score >= 0.85 and (selected.doi or len(sources) >= 2) else "suspicious"
        if score.score < 0.65:
            status = "likely_fake"
        evidence = Evidence(
            bibkey=bib.bibkey,
            status=status,
            confidence=score.score,
            evidence_records=evidence_records,
            canonical_record={"source": selected.source, "id": selected.id},
            metadata_diff=build_metadata_diff(bib, selected),
            failure_reason=None,
        )
        canonical_json = selected.model_dump()
    else:
        evidence = Evidence(
            bibkey=bib.bibkey,
            status="likely_fake",
            confidence=0.0,
            evidence_records=evidence_records,
            canonical_record=None,
            metadata_diff=[],
            failure_reason="No canonical record found",
        )
        canonical_json = None

    payload = {
        "evidence": evidence.model_dump(),
        "canonical": canonical_json,
        "bib_patch": output.bib_patch.model_dump(),
    }
    uri = f"jobs/{task.job_id}/intermediate/bib/{bib.bibkey}.json"
    storage.write_json(uri, json.dumps(payload, ensure_ascii=False, indent=2))


def _run_occ_match(task: Task, storage: Storage) -> None:
    """中文注释：执行引用上下文匹配任务，调用 Match Agent 输出严格 JSON。"""
    _touch_heartbeat(task.id)
    occurrence = task.payload_json["occurrence"]
    bibkey = task.payload_json["bibkey"]
    bib_path = f"jobs/{task.job_id}/intermediate/bib/{bibkey}.json"
    canonical = {}
    abstract = ""
    try:
        data = json.loads(storage.read_text(bib_path))
        canonical = data.get("canonical") or {}
        abstract = canonical.get("abstract") or ""
    except FileNotFoundError:
        abstract = ""

    payload = {
        "bibkey": bibkey,
        "occurrence_id": occurrence["occurrence_id"],
        "context_snippet": occurrence["context_snippet"],
        "abstract": abstract,
        "canonical": {
            "source": canonical.get("source", ""),
            "id": canonical.get("id", ""),
            "title": canonical.get("title", ""),
        },
    }
    result: ContextMatchResult = run_match_agent(task.job_id, payload)
    uri = f"jobs/{task.job_id}/intermediate/occ/{occurrence['occurrence_id']}__{bibkey}.json"
    storage.write_json(uri, json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


def _run_build_bib(task: Task, storage: Storage) -> bool:
    """中文注释：等待所有 BIB_VERIFY 完成后生成 fixed.bib。"""
    _touch_heartbeat(task.id)
    with SessionLocal() as session:
        remaining = session.execute(
            select(Task)
            .where(Task.job_id == task.job_id, Task.type.in_(["BIB_VERIFY"]))
            .where(Task.status != "SUCCEEDED")
        ).scalars().first()
        if remaining:
            return False

    input_uri = _get_job_input(task.job_id, "input_bib_uri")
    bib_text = storage.read_uri(input_uri)
    entries = parse_bib_entries(bib_text)
    patches: dict[str, BibPatch] = {}
    evidences: dict[str, Evidence] = {}
    for entry in entries:
        path = f"jobs/{task.job_id}/intermediate/bib/{entry.bibkey}.json"
        try:
            data = json.loads(storage.read_text(path))
        except FileNotFoundError:
            continue
        patches[entry.bibkey] = BibPatch.model_validate(data.get("bib_patch"))
        evidences[entry.bibkey] = Evidence.model_validate(data.get("evidence"))
    fixed_bib = build_fixed_bib(entries, patches, evidences)
    out_path = f"jobs/{task.job_id}/artifacts/fixed.bib"
    storage.write_text(out_path, fixed_bib)
    return True


def _run_summarize(task: Task, storage: Storage) -> bool:
    """中文注释：等待所有任务完成后汇总 JSON 报告与 artifact 元数据。"""
    _touch_heartbeat(task.id)
    with SessionLocal() as session:
        remaining = session.execute(
            select(Task)
            .where(Task.job_id == task.job_id, Task.type.in_(["BIB_VERIFY", "OCC_MATCH", "BUILD_BIB"]))
            .where(Task.status != "SUCCEEDED")
        ).scalars().first()
        if remaining:
            return False

    existence = []
    context = []
    with SessionLocal() as session:
        bib_tasks = session.execute(
            select(Task).where(Task.job_id == task.job_id, Task.type == "BIB_VERIFY")
        ).scalars().all()
    for bib_task in bib_tasks:
        path = f"jobs/{task.job_id}/intermediate/bib/{bib_task.key.split(':')[1]}.json"
        try:
            data = json.loads(storage.read_text(path))
            existence.append(data.get("evidence"))
        except FileNotFoundError:
            continue

    with SessionLocal() as session:
        occ_tasks = session.execute(
            select(Task).where(Task.job_id == task.job_id, Task.type == "OCC_MATCH")
        ).scalars().all()
    for occ_task in occ_tasks:
        parts = occ_task.key.split(":")
        occ_id = parts[1]
        bibkey = parts[2]
        path = f"jobs/{task.job_id}/intermediate/occ/{occ_id}__{bibkey}.json"
        try:
            data = json.loads(storage.read_text(path))
            context.append(data)
        except FileNotFoundError:
            continue

    existence_path = f"jobs/{task.job_id}/artifacts/existence_report.json"
    context_path = f"jobs/{task.job_id}/artifacts/context_report.json"
    storage.write_json(existence_path, json.dumps(existence, ensure_ascii=False, indent=2))
    storage.write_json(context_path, json.dumps(context, ensure_ascii=False, indent=2))

    _record_artifact(task.job_id, "existence_report.json", existence_path, storage)
    _record_artifact(task.job_id, "context_report.json", context_path, storage)
    _record_artifact(task.job_id, "fixed.bib", f"jobs/{task.job_id}/artifacts/fixed.bib", storage)

    emit_event(task.job_id, "artifact_written", "info", {"names": ["existence_report.json", "context_report.json", "fixed.bib"]})
    return True


def _mark_task_succeeded(task_id: str, result_uri: str | None) -> None:
    """中文注释：将任务标记为成功并更新 job 进度。"""
    with SessionLocal() as session:
        task = session.get(Task, task_id)
        if not task:
            return
        task.status = "SUCCEEDED"
        task.result_uri = result_uri
        task.updated_at = datetime.utcnow()
        session.commit()
        total = session.execute(
            select(func.count(Task.id)).where(Task.job_id == task.job_id)
        ).scalar()
        done = session.execute(
            select(func.count(Task.id)).where(Task.job_id == task.job_id, Task.status == "SUCCEEDED")
        ).scalar()
        job = session.get(Job, task.job_id)
        if job:
            job.progress_json = {"done": done, "total": total}
            job.updated_at = datetime.utcnow()
            session.commit()
        emit_event(task.job_id, "task_succeeded", "info", {"task_id": task.id, "type": task.type})


def _mark_task_failed(task_id: str, exc: Exception) -> None:
    """中文注释：记录失败原因并根据错误类型决定是否重试。"""
    code = "BUG"
    message = str(exc)
    retryable = False
    if isinstance(exc, ValidationError):
        code = "VALIDATION"
        retryable = True
    with SessionLocal() as session:
        task = session.get(Task, task_id)
        if not task:
            return
        task.attempt += 1
        if code in RETRYABLE_CODES and task.attempt <= task.max_attempts:
            retryable = True
        if retryable:
            task.status = "RETRY_PENDING"
            task.retry_after_at = datetime.utcnow() + timedelta(seconds=2 ** task.attempt)
        else:
            task.status = "FAILED"
        task.error_json = {"code": code, "message": message}
        task.updated_at = datetime.utcnow()
        job = session.get(Job, task.job_id)
        if job:
            job.last_error_code = code
            job.last_error_message = message
            job.updated_at = datetime.utcnow()
        session.commit()
        emit_event(task.job_id, "task_failed", "error", {"task_id": task.id, "code": code, "message": message})


def _reset_pending(task_id: str) -> None:
    with SessionLocal() as session:
        task = session.get(Task, task_id)
        if not task:
            return
        task.status = "PENDING"
        task.updated_at = datetime.utcnow()
        session.commit()


def _record_artifact(job_id: str, name: str, path: str, storage: Storage) -> None:
    """中文注释：将产物写入 artifacts 表，方便下载。"""
    sha = storage.compute_sha256(path)
    with SessionLocal() as session:
        artifact = Artifact(job_id=job_id, name=name, uri=storage.to_uri(path), sha256=sha)
        session.add(artifact)
        session.commit()


def _maybe_finalize_job(job_id: str) -> None:
    """中文注释：所有任务完成后更新 job 状态为 COMPLETED。"""
    with SessionLocal() as session:
        remaining = session.execute(
            select(Task)
            .where(Task.job_id == job_id)
            .where(Task.status.in_(["PENDING", "RETRY_PENDING", "RUNNING"]))
        ).scalars().first()
        if remaining:
            return
        job = session.get(Job, job_id)
        if job:
            job.status = "SUCCEEDED"
            job.stage = "COMPLETED"
            job.finished_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            session.commit()
            emit_event(job_id, "stage_changed", "info", {"stage": "COMPLETED"})


def _get_job_input(job_id: str, field: str) -> str:
    """中文注释：从 jobs 表读取输入文件 URI。"""
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if not job:
            return ""
        return getattr(job, field)


def parse_bib_entries(bib_text: str) -> list[BibEntry]:
    """中文注释：解析 BibTeX 文本为结构化 BibEntry 列表。"""
    from app.core.bib import parse_bibtex

    return parse_bibtex(bib_text)


def _touch_heartbeat(task_id: str) -> None:
    """中文注释：更新任务心跳，防止被 watchdog 判定超时。"""
    with SessionLocal() as session:
        session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(heartbeat_at=datetime.utcnow(), updated_at=datetime.utcnow())
        )
        session.commit()


@celery_app.task(name="app.worker.tasks.watchdog_tick")
def watchdog_tick() -> None:
    """中文注释：看门狗任务，发现超时任务则转为重试。"""
    timeout = datetime.utcnow() - timedelta(seconds=30)
    with SessionLocal() as session:
        stale = session.execute(
            select(Task).where(Task.status == "RUNNING", Task.heartbeat_at < timeout)
        ).scalars().all()
        for task in stale:
            task.status = "RETRY_PENDING"
            task.attempt += 1
            task.retry_after_at = datetime.utcnow() + timedelta(seconds=2 ** task.attempt)
            task.updated_at = datetime.utcnow()
        session.commit()
