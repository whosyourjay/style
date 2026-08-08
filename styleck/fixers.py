"""Deterministic repairs.

A fixer rewrites the source so the matching rule stops firing. Only rules with
one obviously correct repair belong here; everything else needs a human or an
agent to decide.
"""

from __future__ import annotations

import re
from typing import Callable

from .document import Document
from .rules_tex import (_is_wrappable_prose, _report_short_run,
                        algo_period_offsets, trailing_punct_offsets)
from .wrap import wrap

MAX_PASSES = 5


def fix_eq_trailing_punct(document: Document) -> str:
    """Drop the punctuation and the horizontal space it was hanging on."""
    offsets = []
    for offset, _ in trailing_punct_offsets(document):
        offsets.append(offset)
        probe = offset - 1
        while probe >= 0 and document.text[probe] in " \t":
            offsets.append(probe)
            probe -= 1
    return _delete_offsets(document.text, offsets)


def fix_algo_period(document: Document) -> str:
    return _delete_offsets(document.text, [o for o, _ in algo_period_offsets(document)])


def fix_tex_short_lines(document: Document) -> str:
    """Rewrap each flagged paragraph to the target width."""
    flagged = {v.line for v in _short_line_violations(document)}
    if not flagged:
        return document.text
    lines = list(document.lines)
    for start, stop in reversed(_paragraphs(document)):
        if not any(start + 1 <= line <= stop + 1 for line in flagged):
            continue
        indent = re.match(r"[ \t]*", lines[start]).group(0)
        joined = " ".join(" ".join(lines[index].split()) for index in range(start, stop + 1))
        lines[start:stop + 1] = wrap(joined, indent)
    return "\n".join(lines)


def _short_line_violations(document: Document) -> list:
    kinds = document.line_kinds()
    found, run = [], []
    for index in range(len(document.lines)):
        if _is_wrappable_prose(document, kinds, index):
            run.append(index)
            continue
        found.extend(_report_short_run(document, run))
        run = []
    found.extend(_report_short_run(document, run))
    return found


def _paragraphs(document: Document) -> list[tuple[int, int]]:
    """Maximal runs of wrappable prose lines, as 0-based inclusive ranges."""
    kinds = document.line_kinds()
    blocks, run = [], []
    for index in range(len(document.lines)):
        if _is_wrappable_prose(document, kinds, index):
            run.append(index)
            continue
        if len(run) > 1:
            blocks.append((run[0], run[-1]))
        run = []
    if len(run) > 1:
        blocks.append((run[0], run[-1]))
    return blocks


def _delete_offsets(text: str, offsets: list[int]) -> str:
    buffer = list(text)
    for offset in sorted(set(offsets), reverse=True):
        del buffer[offset]
    return "".join(buffer)


FIXERS: dict[str, Callable[[Document], str]] = {
    "eq-trailing-punct": fix_eq_trailing_punct,
    "algo-period": fix_algo_period,
    "tex-short-lines": fix_tex_short_lines,
}


def apply_fixes(path: str, text: str, only: frozenset[str] | None = None) -> str:
    """Run every applicable fixer until the text stops changing."""
    current = text
    for _ in range(MAX_PASSES):
        start = current
        for rule_id, fixer in FIXERS.items():
            if only is not None and rule_id not in only:
                continue
            current = fixer(Document(path, current))
        if current == start:
            break
    return current
