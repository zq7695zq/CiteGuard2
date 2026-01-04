# 中文注释：本文件(backend/app/core/citation_locator.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
# 中文注释：用于从正文中定位 \\cite{...} 引文位置并生成结构化 occurrence。
from __future__ import annotations
import re
from app.core.schemas import CitationOccurrence, Location

CITE_PATTERN = re.compile(r"\\cite\{([^}]+)\}")


def locate_citations(text: str) -> list[CitationOccurrence]:
    occurrences: list[CitationOccurrence] = []
    sentences = text.split(".")
    offset = 0
    for sentence_index, sentence in enumerate(sentences):
        for match in CITE_PATTERN.finditer(sentence):
            keys = [k.strip() for k in match.group(1).split(",") if k.strip()]
            start = offset + match.start()
            end = offset + match.end()
            occurrence_id = f"occ-{len(occurrences)+1}"
            occurrences.append(
                CitationOccurrence(
                    occurrence_id=occurrence_id,
                    bibkeys=keys,
                    location=Location(
                        char_start=start,
                        char_end=end,
                        paragraph_index=text[:start].count("\n\n"),
                        sentence_index=sentence_index,
                    ),
                    context_snippet=sentence.strip(),
                )
            )
        offset += len(sentence) + 1
    return occurrences
