# 中文注释：本文件(backend/app/core/scoring.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
from __future__ import annotations
from dataclasses import dataclass
from rapidfuzz import fuzz
from app.core.schemas import BibEntry, CanonicalRecord


def _norm(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.lower().split())


def _split_authors(authors: str | list[str]) -> list[str]:
    if isinstance(authors, list):
        return [a.strip().lower() for a in authors if a.strip()]
    return [a.strip().lower() for a in authors.replace("and", ",").split(",") if a.strip()]


@dataclass
class ScoreResult:
    score: float
    title_sim: float
    author_overlap: float
    venue_sim: float
    year_score: float
    doi_bonus: float


def score_bib(bib: BibEntry, canonical: CanonicalRecord) -> ScoreResult:
    title_sim = fuzz.token_set_ratio(_norm(bib.fields.get("title")), _norm(canonical.title)) / 100
    bib_authors = _split_authors(bib.fields.get("author", ""))
    can_authors = _split_authors(canonical.authors)
    author_overlap = 0.0
    if bib_authors:
        author_overlap = len(set(bib_authors) & set(can_authors)) / max(len(bib_authors), 1)
    venue_sim = fuzz.token_set_ratio(
        _norm(bib.fields.get("journal") or bib.fields.get("booktitle")),
        _norm(canonical.venue),
    ) / 100
    year_score = 0.0
    bib_year = bib.fields.get("year")
    if bib_year and canonical.year:
        diff = abs(int(bib_year) - int(canonical.year))
        year_score = 1.0 if diff == 0 else 0.7 if diff == 1 else 0.0
    doi_bonus = 0.08 if canonical.doi and bib.fields.get("doi") == canonical.doi else 0.0
    score = 0.55 * title_sim + 0.25 * author_overlap + 0.15 * venue_sim + 0.05 * year_score + doi_bonus
    return ScoreResult(
        score=score,
        title_sim=title_sim,
        author_overlap=author_overlap,
        venue_sim=venue_sim,
        year_score=year_score,
        doi_bonus=doi_bonus,
    )
