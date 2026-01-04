# 中文注释：本文件(backend/app/core/bib_writer.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
from __future__ import annotations
from typing import Any
from app.core.bib import apply_patch, ensure_required_fields, generate_bibtex
from app.core.schemas import BibEntry, Evidence, BibPatch


def build_fixed_bib(entries: list[BibEntry], patches: dict[str, BibPatch], evidences: dict[str, Evidence]) -> str:
    patched_entries: list[tuple[str, dict[str, Any]]] = []
    entry_types: dict[str, str] = {}
    for entry in entries:
        patch = patches.get(entry.bibkey)
        fields = entry.fields
        if patch:
            fields = apply_patch(entry, patch.patch_fields, patch.remove_fields)
        evidence = evidences.get(entry.bibkey)
        if evidence and evidence.status in {"suspicious", "likely_fake"}:
            note = f"CiteGuard: {evidence.status}. {evidence.failure_reason or ''}".strip()
            fields = {**fields, "note": note}
        missing = ensure_required_fields(fields, entry.entry_type)
        if missing:
            fields["note"] = (fields.get("note", "") + f" Missing fields: {', '.join(missing)}").strip()
        patched_entries.append((entry.bibkey, fields))
        entry_types[entry.bibkey] = entry.entry_type
    return generate_bibtex(patched_entries, entry_types)
