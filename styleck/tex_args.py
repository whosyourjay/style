"""TeX arguments and source masks shared by writing rules."""

from __future__ import annotations

import re

from .document import VERBATIM, Document, _find_braced_end

COMMAND_RE = re.compile(r"\\(?:[A-Za-z@]+|.)", re.S)
HEADING_RE = re.compile(
    r"\\(?:part|chapter|section|subsection|subsubsection|paragraph|subparagraph|title)"
    r"(?![A-Za-z@])\*?"
)


def visible_source(document: Document) -> str:
    """Blank comments and verbatim regions without changing source offsets."""
    text = document.text
    masked = list(text)
    regions = [(span.start, span.end) for span in document.spans_of(VERBATIM)]
    pos = 0
    while pos < len(text):
        if text[pos] == "\\":
            pos += 2
        elif text[pos] == "%":
            end = text.find("\n", pos)
            end = len(text) if end < 0 else end
            regions.append((pos, end))
            pos = end
        else:
            pos += 1
    for start, end in regions:
        for pos in range(start, end):
            if text[pos] != "\n":
                masked[pos] = " "
    return "".join(masked)


def braced_arg_at(text: str, pos: int) -> tuple[str | None, int]:
    while pos < len(text) and text[pos].isspace():
        pos += 1
    end = _find_braced_end(text, pos)
    if end is None:
        return None, pos
    return text[pos + 1:end - 1], end


def optional_arg_at(text: str, pos: int) -> tuple[str | None, int]:
    """Read an optional argument, allowing nested braces and brackets."""
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos >= len(text) or text[pos] != "[":
        return None, pos
    start = pos + 1
    pos += 1
    braces = brackets = 0
    while pos < len(text):
        char = text[pos]
        if char == "\\":
            pos += 2
            continue
        if char == "{":
            braces += 1
        elif char == "}":
            braces = max(braces - 1, 0)
        elif char == "[":
            brackets += 1
        elif char == "]":
            if braces == brackets == 0:
                return text[start:pos], pos + 1
            brackets = max(brackets - 1, 0)
        pos += 1
    return None, pos


def heading_regions(text: str) -> list[tuple[int, int]]:
    """Locate titles, including short titles and nested formatting commands."""
    regions = []
    for match in HEADING_RE.finditer(text):
        _, pos = optional_arg_at(text, match.end())
        title, end = braced_arg_at(text, pos)
        if title is not None:
            regions.append((match.start(), end))
    return regions
