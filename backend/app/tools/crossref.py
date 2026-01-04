# 中文注释：本文件(backend/app/tools/crossref.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
from __future__ import annotations
import requests
from app.core.schemas import CanonicalRecord
from app.tools.errors import ToolError


def crossref_lookup(title: str | None = None, authors: list[str] | None = None, year: int | None = None) -> dict:
    if not title:
        raise ToolError("VALIDATION", "title is required", retryable=False)
    query = title
    params = {"query.title": query, "rows": 5}
    if authors:
        params["query.author"] = " ".join(authors)
    if year:
        params["filter"] = f"from-pub-date:{year}-01-01,until-pub-date:{year}-12-31"
    response = requests.get("https://api.crossref.org/works", params=params, timeout=10)
    if response.status_code != 200:
        raise ToolError("TRANSIENT_UPSTREAM", "Crossref error", retryable=True)
    items = response.json().get("message", {}).get("items", [])
    return {"ok": True, "items": items}


def to_canonical(item: dict) -> CanonicalRecord:
    title = item.get("title", [""])[0]
    authors = []
    for author in item.get("author", []):
        name = " ".join(part for part in [author.get("given"), author.get("family")] if part)
        if name:
            authors.append(name)
    year = None
    if item.get("issued", {}).get("date-parts"):
        year = item["issued"]["date-parts"][0][0]
    return CanonicalRecord(
        source="crossref",
        id=item.get("DOI", ""),
        title=title,
        authors=authors,
        year=year,
        venue=item.get("container-title", [""])[0],
        publication_type="article",
        volume=item.get("volume"),
        number=item.get("issue"),
        pages=item.get("page"),
        publisher=item.get("publisher"),
        organization=None,
        doi=item.get("DOI"),
        url=item.get("URL"),
        abstract=None,
        identifiers={"crossref_doi": item.get("DOI", "")},
    )
