"""High-recall lexical audits over source prose."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .document import Document


@dataclass(frozen=True)
class ConcordanceEntry:
    path: str
    line: int
    column: int
    text: str

    def format(self) -> str:
        return f"{self.path}:{self.line}:{self.column}: {self.text}"


def concordance(document: Document, word: str) -> list[ConcordanceEntry]:
    """Return every whole-word occurrence in prose, preserving source offsets."""
    if not word or not re.fullmatch(r"[^\W_]+(?:[-'][^\W_]+)*", word):
        raise ValueError("concordance query must be one word")
    pattern = re.compile(rf"(?<!\w){re.escape(word)}(?!\w)", re.I)
    entries = []
    for match in pattern.finditer(document.prose_mask()):
        line = document.line_of(match.start())
        source_line = " ".join(document.lines[line - 1].strip().split())
        entries.append(ConcordanceEntry(
            path=document.path,
            line=line,
            column=document.column_of(match.start()),
            text=source_line,
        ))
    return entries
