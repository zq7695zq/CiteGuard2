# 中文注释：本文件(backend/app/core/schemas.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field


class Location(BaseModel):
    char_start: int
    char_end: int
    paragraph_index: int
    sentence_index: int


class CitationOccurrence(BaseModel):
    occurrence_id: str
    bibkeys: list[str]
    location: Location
    context_snippet: str


class BibEntry(BaseModel):
    bibkey: str
    entry_type: Literal["article", "inproceedings"]
    fields: dict[str, Any]
    raw_bib: str


class CanonicalRecord(BaseModel):
    source: Literal["zotero", "semanticscholar", "crossref", "openalex"]
    id: str
    title: str
    authors: list[str]
    year: int | None = None
    venue: str | None = None
    publication_type: Literal["article", "inproceedings", "book", "other"]
    volume: str | None = None
    number: str | None = None
    pages: str | None = None
    publisher: str | None = None
    organization: str | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    identifiers: dict[str, str] = Field(default_factory=dict)


class EvidenceRecord(BaseModel):
    source: str
    id: str | None = None
    doi: str | None = None
    url: str | None = None


class Evidence(BaseModel):
    bibkey: str
    status: Literal["real", "suspicious", "likely_fake"]
    confidence: float
    evidence_records: list[EvidenceRecord]
    canonical_record: dict[str, str] | None
    metadata_diff: list[dict[str, str]]
    failure_reason: str | None = None


class ContextMatchResult(BaseModel):
    bibkey: str
    occurrence_id: str
    match_judgement: Literal["match", "partial", "mismatch"]
    rationale: str
    suggestion: str
    abstract_used: str
    canonical_source: str
    canonical_id: str
    confidence: float


class BibPatch(BaseModel):
    bibkey: str
    patch_fields: dict[str, Any]
    remove_fields: list[str]


class MainAgentOutput(BaseModel):
    bibkey: str
    selected_canonical: CanonicalRecord | None
    all_candidates: list[CanonicalRecord]
    bib_patch: BibPatch
    notes: str
