# 中文注释：本文件(backend/app/tools/scholar.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
from __future__ import annotations
from app.tools.errors import ToolError


def scholar_search_paper(title: str, authors: list[str] | None = None, year: int | None = None, topk: int = 3) -> dict:
    raise ToolError("NOT_FOUND", "Scholar provider not configured", retryable=False)


def scholar_get_paper(paper_id: str) -> dict:
    raise ToolError("NOT_FOUND", "Scholar provider not configured", retryable=False)
