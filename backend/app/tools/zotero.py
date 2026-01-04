# 中文注释：本文件(backend/app/tools/zotero.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
from __future__ import annotations
import json
from pathlib import Path
from app.core.config import get_settings
from app.core.schemas import CanonicalRecord
from app.tools.errors import ToolError


def _load_snapshot() -> list[dict]:
    settings = get_settings()
    path = Path(settings.zotero_snapshot_path)
    if not path.exists():
        raise ToolError("NOT_FOUND", f"Zotero snapshot not found at {path}", retryable=False)
    return json.loads(path.read_text(encoding="utf-8"))


def zotero_healthcheck() -> dict:
    _load_snapshot()
    return {"ok": True}


def zotero_search_items(query: str, filters: dict | None = None, limit: int = 5, offset: int = 0) -> dict:
    items = _load_snapshot()
    query_lower = query.lower()
    matched = [item for item in items if query_lower in item.get("title", "").lower()]
    sliced = matched[offset : offset + limit]
    return {"ok": True, "items": sliced, "total": len(matched)}


def zotero_get_item(item_id: str) -> dict:
    items = _load_snapshot()
    for item in items:
        if item.get("id") == item_id:
            return {"ok": True, "item": item}
    raise ToolError("NOT_FOUND", f"Item {item_id} not found", retryable=False)


def zotero_get_items_batch(ids: list[str]) -> dict:
    items = _load_snapshot()
    matched = [item for item in items if item.get("id") in ids]
    return {"ok": True, "items": matched}


def zotero_export(ids: list[str], format: str) -> dict:
    items = zotero_get_items_batch(ids)
    return {"ok": True, "items": items.get("items", []), "format": format}


def to_canonical(item: dict) -> CanonicalRecord:
    return CanonicalRecord(
        source="zotero",
        id=item.get("id", ""),
        title=item.get("title", ""),
        authors=item.get("authors", []),
        year=item.get("year"),
        venue=item.get("venue"),
        publication_type=item.get("publication_type", "article"),
        volume=item.get("volume"),
        number=item.get("number"),
        pages=item.get("pages"),
        publisher=item.get("publisher"),
        organization=item.get("organization"),
        doi=item.get("doi"),
        url=item.get("url"),
        abstract=item.get("abstract"),
        identifiers=item.get("identifiers", {}),
    )
