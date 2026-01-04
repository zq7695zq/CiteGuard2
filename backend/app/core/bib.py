# 中文注释：本文件(backend/app/core/bib.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
# 中文注释：提供 BibTeX 解析、字段补丁合并、必填字段校验与生成能力。
from __future__ import annotations
from typing import Any
import bibtexparser
from app.core.schemas import BibEntry


REQUIRED_FIELDS = {
    "article": ["title", "author", "journal", "volume", "number", "pages", "year"],
    "inproceedings": ["title", "author", "booktitle", "pages", "year"],
}


def parse_bibtex(bib_text: str) -> list[BibEntry]:
    parser = bibtexparser.bparser.BibTexParser(common_strings=True)
    data = bibtexparser.loads(bib_text, parser=parser)
    entries: list[BibEntry] = []
    for entry in data.entries:
        entry_type = entry.get("ENTRYTYPE", "article").lower()
        if entry_type not in {"article", "inproceedings"}:
            entry_type = "article"
        bibkey = entry.get("ID")
        fields = {k: v for k, v in entry.items() if k not in {"ENTRYTYPE", "ID"}}
        raw_bib = bibtexparser.dumps(bibtexparser.bibdatabase.BibDatabase(entries=[entry]))
        entries.append(BibEntry(bibkey=bibkey, entry_type=entry_type, fields=fields, raw_bib=raw_bib))
    return entries


def apply_patch(entry: BibEntry, patch_fields: dict[str, Any], remove_fields: list[str]) -> dict[str, Any]:
    merged = {**entry.fields}
    for key in remove_fields:
        merged.pop(key, None)
    for key, value in patch_fields.items():
        merged[key] = value
    return merged


def generate_bibtex(entries: list[dict[str, Any]], entry_types: dict[str, str]) -> str:
    db = bibtexparser.bibdatabase.BibDatabase()
    db.entries = []
    for bibkey, fields in entries:
        entry = {"ENTRYTYPE": entry_types[bibkey], "ID": bibkey}
        entry.update(fields)
        db.entries.append(entry)
    return bibtexparser.dumps(db)


def ensure_required_fields(fields: dict[str, Any], entry_type: str) -> list[str]:
    missing = []
    for field in REQUIRED_FIELDS.get(entry_type, []):
        if not fields.get(field):
            missing.append(field)
    return missing
