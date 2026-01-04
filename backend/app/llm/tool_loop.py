# 中文注释：本文件(backend/app/llm/tool_loop.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
# 中文注释：实现模型的工具调用循环，统一分发到 Zotero / Crossref / Scholar 等结构化工具。
from __future__ import annotations
import json
from typing import Any
from app.llm.providers import LLMProvider, LLMResult
from app.tools import zotero, crossref, scholar
from app.tools.errors import ToolError


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "zotero.search_items",
            "description": "Search items in local Zotero snapshot",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "filters": {"type": "object"},
                    "limit": {"type": "integer"},
                    "offset": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "zotero.get_item",
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "zotero.get_items_batch",
            "parameters": {
                "type": "object",
                "properties": {"ids": {"type": "array", "items": {"type": "string"}}},
                "required": ["ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "zotero.export",
            "parameters": {
                "type": "object",
                "properties": {
                    "ids": {"type": "array", "items": {"type": "string"}},
                    "format": {"type": "string"},
                },
                "required": ["ids", "format"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scholar.search_paper",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "authors": {"type": "array", "items": {"type": "string"}},
                    "year": {"type": "integer"},
                    "topk": {"type": "integer"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crossref.lookup",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "authors": {"type": "array", "items": {"type": "string"}},
                    "year": {"type": "integer"},
                },
                "required": ["title"],
            },
        },
    },
]


TOOL_DISPATCH = {
    "zotero.search_items": zotero.zotero_search_items,
    "zotero.get_item": zotero.zotero_get_item,
    "zotero.get_items_batch": zotero.zotero_get_items_batch,
    "zotero.export": zotero.zotero_export,
    "scholar.search_paper": scholar.scholar_search_paper,
    "crossref.lookup": crossref.crossref_lookup,
}


def run_tool_loop(provider: LLMProvider, messages: list[dict[str, Any]], max_loops: int = 4) -> tuple[LLMResult, list[dict[str, Any]]]:
    tool_events: list[dict[str, Any]] = []
    for _ in range(max_loops):
        result = provider.chat(messages, tools=TOOLS)
        if not result.tool_calls:
            return result, tool_events
        for call in result.tool_calls:
            name = call["name"]
            args = json.loads(call["arguments_json"] or "{}")
            try:
                data = TOOL_DISPATCH[name](**args)
            except ToolError as err:
                data = err.to_dict()
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(data)})
            tool_events.append({"name": name, "arguments": args, "result": data})
    return result, tool_events
