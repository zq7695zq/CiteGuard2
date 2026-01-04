# 中文注释：本文件(backend/app/core/diff.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
from __future__ import annotations
from app.core.schemas import BibEntry, CanonicalRecord


FIELDS = ["title", "author", "journal", "booktitle", "year", "doi"]


def build_metadata_diff(bib: BibEntry, canonical: CanonicalRecord) -> list[dict[str, str]]:
    diffs = []
    for field in FIELDS:
        bib_value = bib.fields.get(field)
        can_value = None
        if field == "author":
            can_value = ", ".join(canonical.authors)
        elif field == "journal":
            can_value = canonical.venue
        elif field == "booktitle":
            can_value = canonical.venue
        elif field == "year":
            can_value = str(canonical.year) if canonical.year else None
        elif field == "doi":
            can_value = canonical.doi
        else:
            can_value = canonical.title if field == "title" else None
        if bib_value and can_value and str(bib_value) != str(can_value):
            diffs.append({"field": field, "bib": str(bib_value), "canonical": str(can_value)})
    return diffs
