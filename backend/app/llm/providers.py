# 中文注释：本文件(backend/app/llm/providers.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from openai import OpenAI
from app.core.config import get_settings


@dataclass
class LLMResult:
    assistant_text: str
    tool_calls: list[dict[str, Any]]
    raw: dict[str, Any]


class LLMProvider:
    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResult:
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResult:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
        )
        choice = response.choices[0]
        tool_calls = []
        if choice.message.tool_calls:
            for call in choice.message.tool_calls:
                tool_calls.append({
                    "id": call.id,
                    "name": call.function.name,
                    "arguments_json": call.function.arguments,
                })
        return LLMResult(
            assistant_text=choice.message.content or "",
            tool_calls=tool_calls,
            raw=response.model_dump(),
        )


class SiliconFlowProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.client = OpenAI(api_key=settings.siliconflow_api_key, base_url="https://api.siliconflow.cn/v1")
        self.model = settings.siliconflow_model

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResult:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
        )
        choice = response.choices[0]
        tool_calls = []
        if choice.message.tool_calls:
            for call in choice.message.tool_calls:
                tool_calls.append({
                    "id": call.id,
                    "name": call.function.name,
                    "arguments_json": call.function.arguments,
                })
        return LLMResult(
            assistant_text=choice.message.content or "",
            tool_calls=tool_calls,
            raw=response.model_dump(),
        )


class MockProvider(LLMProvider):
    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResult:
        system = messages[0].get("content", "") if messages else ""
        if "Match Agent" in system:
            content = """{
  \"bibkey\": \"demo2024\",
  \"occurrence_id\": \"occ-1\",
  \"match_judgement\": \"partial\",
  \"rationale\": \"Mock match due to missing abstract.\",
  \"suggestion\": \"Provide abstract for stronger match.\",
  \"abstract_used\": \"\",
  \"canonical_source\": \"crossref\",
  \"canonical_id\": \"10.0000/mock\",
  \"confidence\": 0.4
}"""
        else:
            content = """{
  \"bibkey\": \"demo2024\",
  \"selected_canonical\": null,
  \"all_candidates\": [],
  \"bib_patch\": {\"bibkey\": \"demo2024\", \"patch_fields\": {}, \"remove_fields\": []},
  \"notes\": \"mock\"
}"""
        return LLMResult(assistant_text=content, tool_calls=[], raw={"mock": True})


def get_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "openai":
        return OpenAIProvider()
    if settings.llm_provider == "siliconflow":
        return SiliconFlowProvider()
    return MockProvider()
