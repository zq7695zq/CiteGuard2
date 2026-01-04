# 中文注释：本文件(backend/app/llm/agents.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
# 中文注释：封装 Main Agent 与 Match Agent 的调用逻辑，负责提示词、工具调用与结果校验。
from __future__ import annotations
import json
from pydantic import ValidationError
from app.core.schemas import BibEntry, MainAgentOutput, ContextMatchResult
from app.llm.prompts import MAIN_SYSTEM_PROMPT, MATCH_SYSTEM_PROMPT
from app.llm.providers import get_provider
from app.llm.tool_loop import run_tool_loop
from app.sse.events import emit_event


def run_main_agent(job_id: str, bib_entry: BibEntry, citation_snippets: list[str]) -> tuple[MainAgentOutput, list[dict]]:
    provider = get_provider()
    messages = [
        {"role": "system", "content": MAIN_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "bib_entry": bib_entry.model_dump(),
                    "citation_snippets": citation_snippets,
                }
            ),
        },
    ]
    emit_event(job_id, "llm_called", "info", {"provider": type(provider).__name__})
    result, tool_events = run_tool_loop(provider, messages)
    try:
        output = MainAgentOutput.model_validate_json(result.assistant_text)
        return output, tool_events
    except ValidationError as exc:
        emit_event(job_id, "llm_validation_failed", "error", {"errors": exc.errors()})
        raise


def run_match_agent(job_id: str, payload: dict) -> ContextMatchResult:
    provider = get_provider()
    messages = [
        {"role": "system", "content": MATCH_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload)},
    ]
    emit_event(job_id, "llm_called", "info", {"provider": type(provider).__name__, "agent": "match"})
    result = provider.chat(messages)
    try:
        return ContextMatchResult.model_validate_json(result.assistant_text)
    except ValidationError as exc:
        emit_event(job_id, "llm_validation_failed", "error", {"errors": exc.errors()})
        raise
