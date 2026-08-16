"""LaTeX layout and equation rules."""

from __future__ import annotations

import math
import re
from typing import Iterable

from .document import ALGO, COMMENT, DISPLAY, INLINE, TEX_SUFFIXES, Document, Span
from .rule import ERROR, WARN, Violation, at_line, make, register
from .wrap import WRAP_TARGET, first_atom

TEX = tuple(sorted(TEX_SUFFIXES))

SHORT_LINE = 50
MIN_GAP_CHARS = 160
MIN_GAP_SENTENCES = 3
MAX_ALIGN_ROWS = 5

ALIGN_FAMILY = frozenset({
    "align", "align*", "alignat", "alignat*", "gather", "gather*",
    "multline", "multline*", "eqnarray", "eqnarray*", "flalign", "flalign*",
    "IEEEeqnarray",
})

TRAILING_PUNCT_RE = re.compile(
    r"([.,;:])(?=[ \t]*(?:\\label\{[^}\r\n]*\}[ \t]*)*"
    r"\r?\n?[ \t]*(?:\\\\|\\\]|\\end\{|\$\$|\Z))"
)
SENTENCE_END_RE = re.compile(r"[.!?][)\]'\"]?(?:\s|\Z)")
STRUCTURAL_RE = re.compile(
    r"\\(?:section|subsection|subsubsection|paragraph|item|end|begin|caption"
    r"|label|proof|qed|newpage|bibliography|appendix)\b"
)
SKIP_LINE_RE = re.compile(
    r"^\s*(?:\\(?:item|begin|end|section|subsection|subsubsection|paragraph"
    r"|label|caption|node|draw|path|fill|coordinate|usepackage|newcommand"
    r"|documentclass|maketitle|title|author|date|bibliography|bibitem"
    r"|thebibliography|input|include)\b"
    r"|&|\||\\\\)"
)
NESTED_ENV_RE = re.compile(r"\\begin\{([A-Za-z@*]+)\}")
ROW_BREAK_RE = re.compile(r"\\\\")
TAB_RE = re.compile(r"(?<!\\)&")
COMMA_RE = re.compile(r",")
RELATION_RE = re.compile(
    r"\\(?:leq|geq|le|ge|neq|ne|equiv|approx|simeq|sim|subseteq|supseteq"
    r"|subset|supset|ll|gg|cong|propto)\b|[=<>]"
)
TEXT_GROUP_RE = re.compile(r"\\(?:text|mbox|textrm|textit|mathrm|operatorname)\s*\{")
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]|\r(?!\n)")
BARE_MATH_COMMAND_RE = re.compile(
    r"(?<![\\A-Za-z])(?P<name>qquad|quad|geq|leq|neq|infty|cdot|ldots|times)"
    r"(?=$|[^a-z])"
)


def _body_spans(document: Document, kind: str) -> list[Span]:
    return [s for s in document.spans_of(kind) if document.in_body(s.start)]


def _visible_text(document: Document, start: int, end: int) -> str:
    """Text in [start, end) with comment spans removed."""
    pieces = []
    for span in document.spans:
        if span.end <= start or span.start >= end or span.kind == COMMENT:
            continue
        pieces.append(document.text[max(span.start, start):min(span.end, end)])
    return "".join(pieces)


def _nested_env_regions(body: str) -> list[tuple[int, int]]:
    """Spans of environments nested inside a display, such as bmatrix or cases.

    Their `&` cells hold relations and stray dots that belong to the matrix,
    not to the surrounding equation.
    """
    from .document import _find_env_end

    regions = []
    for match in NESTED_ENV_RE.finditer(body):
        if match.start() == 0:
            continue
        regions.append((match.start(), _find_env_end(body, match.group(1), match.end())))
    return regions


def _depth_zero_positions(body: str, pattern: re.Pattern) -> list[int]:
    """Offsets of `pattern` matches outside braces, \\text groups, and matrices."""
    blocked: list[tuple[int, int]] = _nested_env_regions(body)
    for match in TEXT_GROUP_RE.finditer(body):
        blocked.append((match.start(), _group_end(body, match.end() - 1)))
    found = []
    for match in pattern.finditer(body):
        start = match.start()
        if any(low <= start < high for low, high in blocked):
            continue
        if _brace_depth(body, start) == 0:
            found.append(start)
    return found


def _brace_depth(body: str, index: int) -> int:
    """Group depth at `index`, counting a literal `\\{` set brace as a group."""
    depth = 0
    position = 0
    while position < index:
        char = body[position]
        if char == "\\":
            escaped = body[position + 1:position + 2]
            depth += (escaped == "{") - (escaped == "}")
            position += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        position += 1
    return depth


def _group_end(body: str, open_brace: int) -> int:
    depth = 0
    position = open_brace
    while position < len(body):
        char = body[position]
        if char == "\\":
            position += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return position + 1
        position += 1
    return len(body)


def _text_group_regions(body: str) -> list[tuple[int, int]]:
    """Ranges of prose-like groups nested inside a math span."""
    return [
        (match.start(), _group_end(body, match.end() - 1))
        for match in TEXT_GROUP_RE.finditer(body)
    ]


def trailing_punct_offsets(document: Document) -> list[tuple[int, str]]:
    """Offsets of stray punctuation ending a display row, with the character.

    Shared by the check and the fixer so the two cannot disagree about which
    characters are punctuation and which are matrix entries.
    """
    found = []
    for span in _body_spans(document, DISPLAY):
        body = document.text[span.start:span.end]
        blocked = _nested_env_regions(body)
        for match in TRAILING_PUNCT_RE.finditer(body):
            start = match.start(1)
            if any(low <= start < high for low, high in blocked):
                continue
            if _previous_visible(body, start) in ("&", "\\\\", ""):
                continue
            found.append((span.start + start, match.group(1)))
    return found


def _previous_visible(body: str, index: int) -> str:
    """The token just before `index`: an alignment tab, a row break, or a char."""
    probe = index - 1
    while probe >= 0 and body[probe] in " \t\r\n":
        probe -= 1
    if probe < 0:
        return ""
    if body[probe] == "&":
        return "&"
    if probe >= 1 and body[probe - 1:probe + 1] == "\\\\":
        return "\\\\"
    return body[probe]


@register(
    id="eq-trailing-punct",
    section="Equations",
    severity=ERROR,
    applies_to=TEX,
    summary="Put no punctuation between display equations or at the end of one.",
    detail="No comma, period, semicolon, or colon before `\\\\`, `\\]`, or `\\end{...}`.",
    bad="\\[\n  \\Phi(G)=\\sum_v d(v)^2 .\n\\]",
    good="\\[\n  \\Phi(G)=\\sum_v d(v)^2\n\\]",
)
def check_eq_trailing_punct(document: Document) -> Iterable[Violation]:
    for offset, char in trailing_punct_offsets(document):
        yield make(
            document,
            "eq-trailing-punct",
            offset,
            f"display equation ends with '{char}'; drop it",
        )


def _split(body: str, start: int, end: int, pattern: re.Pattern,
           width: int) -> list[tuple[int, int]]:
    """`[start, end)` cut at every depth-zero `pattern` match, as offsets in `body`."""
    pieces = []
    cursor = start
    for offset in _depth_zero_positions(body[start:end], pattern):
        pieces.append((cursor, start + offset))
        cursor = start + offset + width
    pieces.append((cursor, end))
    return pieces


def _chains(body: str) -> Iterable[tuple[int, int, bool]]:
    """Per alignment cell holding two or more relations: where, how many, listed.

    A display without a row break is one row, and one without an alignment tab
    is one cell, so every display is measured the same way.
    """
    for row_start, row_end in _split(body, 0, len(body), ROW_BREAK_RE, 2):
        for start, end in _split(body, row_start, row_end, TAB_RE, 1):
            cell = body[start:end]
            positions = _depth_zero_positions(cell, RELATION_RE)
            if len(positions) < 2:
                continue
            middle = cell[positions[0]:positions[-1]]
            listed = bool(_depth_zero_positions(middle, COMMA_RE))
            yield start + positions[1], len(positions), listed


@register(
    id="eq-needs-align",
    section="Equations",
    severity=WARN,
    applies_to=TEX,
    summary="Give each relation a row of its own.",
    detail=(
        "One relation per display, or per row of an align, however short the "
        "far side is. Record a deliberate exception in a `.styleck-allow` "
        "file next to the source."
    ),
    bad="\\begin{align}\n  f(x) &= g(x) = h(x)\n\\end{align}",
    good="\\begin{align}\n  f(x) &= g(x) \\\\\n       &= h(x)\n\\end{align}",
)
def check_eq_needs_align(document: Document) -> Iterable[Violation]:
    for span in _body_spans(document, DISPLAY):
        body = document.text[span.start:span.end]
        rowed = span.env in ALIGN_FAMILY
        for offset, count, listed in _chains(body):
            yield make(
                document,
                "eq-needs-align",
                span.start + offset,
                _align_message(count, listed, rowed),
            )


def _align_message(count: int, listed: bool, rowed: bool) -> str:
    subject = "row" if rowed else "display"
    if listed:
        return f"{subject} holds {count} separate equations; align them on the relation"
    remedy = "give each its own row" if rowed else "split it into an align"
    return f"{subject} chains {count} relations; {remedy}"


@register(
    id="eq-block-size",
    section="Equations",
    severity=WARN,
    applies_to=TEX,
    summary=f"Keep a derivation block to {MAX_ALIGN_ROWS} rows or fewer.",
    detail="Break a longer chain with a sentence of explanation and a new block.",
)
def check_eq_block_size(document: Document) -> Iterable[Violation]:
    for span in _body_spans(document, DISPLAY):
        if span.env not in ALIGN_FAMILY:
            continue
        body = document.text[span.start:span.end]
        rows = len(_split(body, 0, len(body), ROW_BREAK_RE, 2))
        if rows > MAX_ALIGN_ROWS:
            yield make(
                document,
                "eq-block-size",
                span.start,
                f"block has {rows} rows; keep it to {MAX_ALIGN_ROWS} and explain between",
            )


@register(
    id="tex-malformed-control",
    section="LaTeX layout",
    severity=ERROR,
    applies_to=TEX,
    summary="Reject control characters and TeX commands that lost their backslash.",
    detail=(
        "A pasted carriage return can corrupt a command, and `qquadE` is not "
        "a substitute for `\\qquad \\E`. The math-word check is deliberately "
        "limited to common TeX commands with very low prose ambiguity."
    ),
    bad="$m \\geq 1, qquadE \\log M=\\nu$",
    good="$m \\geq 1, \\qquad \\E \\log M=\\nu$",
)
def check_tex_malformed_control(document: Document) -> Iterable[Violation]:
    for match in CONTROL_CHAR_RE.finditer(document.text):
        char = match.group(0)
        name = "standalone carriage return" if char == "\r" else f"U+{ord(char):04X}"
        yield make(
            document,
            "tex-malformed-control",
            match.start(),
            f"source contains {name}; remove it and restore any damaged TeX command",
        )

    for span in document.spans_of(INLINE, DISPLAY):
        body = document.text[span.start:span.end]
        blocked = _text_group_regions(body)
        for match in BARE_MATH_COMMAND_RE.finditer(body):
            if any(low <= match.start() < high for low, high in blocked):
                continue
            yield make(
                document,
                "tex-malformed-control",
                span.start + match.start("name"),
                f"'{match.group('name')}' in math looks like a TeX command missing '\\'",
            )


@register(
    id="tex-text-gap",
    section="LaTeX layout",
    severity=WARN,
    applies_to=TEX,
    summary="Give at least three lines of explanation between two displays.",
    detail=(
        "Several sentences, not a stub clause. Either say more, or fold the "
        "stub into the align as inline text, or merge the two displays."
    ),
    bad="\\[ A \\]\nHence the bound.\n\\[ B \\]",
    good=(
        "\\[ A \\]\nThe left side counts each pair twice, so halving it gives the\n"
        "number of edges. The same argument applies to every vertex of the\n"
        "graph, which yields the second bound.\n\\[ B \\]"
    ),
)
def check_tex_text_gap(document: Document) -> Iterable[Violation]:
    displays = _body_spans(document, DISPLAY)
    for first, second in zip(displays, displays[1:]):
        gap = _visible_text(document, first.end, second.start)
        if not gap.strip() or STRUCTURAL_RE.search(gap):
            continue
        chars = len(" ".join(gap.split()))
        sentences = len(SENTENCE_END_RE.findall(gap))
        if chars >= MIN_GAP_CHARS or sentences >= MIN_GAP_SENTENCES:
            continue
        estimate = max(1, math.ceil(chars / WRAP_TARGET))
        yield at_line(
            document,
            "tex-text-gap",
            document.line_of(second.start),
            f"only ~{estimate} line(s) of text between displays; write at least 3",
        )


@register(
    id="tex-short-lines",
    section="LaTeX layout",
    severity=WARN,
    applies_to=TEX,
    summary="Do not break prose into short lines; wrap near 80 characters.",
    detail=(
        "A paragraph may sit on one long line. What reads badly is a run of "
        "stubby lines, which happens when text is edited without rewrapping."
    ),
    bad="The bound follows\nfrom convexity of\nthe square function.",
    good="The bound follows from convexity of the square function.",
)
def check_tex_short_lines(document: Document) -> Iterable[Violation]:
    kinds = document.line_kinds()
    run: list[int] = []
    for index in range(len(document.lines)):
        if _is_wrappable_prose(document, kinds, index):
            run.append(index)
            continue
        yield from _report_short_run(document, run)
        run = []
    yield from _report_short_run(document, run)


def _is_wrappable_prose(document: Document, kinds: list[set[str]], index: int) -> bool:
    line = document.lines[index]
    if not line.strip() or kinds[index] != {"prose"}:
        return False
    start, _ = document.line_span(index + 1)
    return document.in_body(start) and not SKIP_LINE_RE.match(line)


def _report_short_run(document: Document, run: list[int]) -> Iterable[Violation]:
    """Flag two or more consecutive short lines inside one prose paragraph."""
    if len(run) < 3:
        return
    short: list[int] = []
    for index in run[:-1]:
        if _is_needlessly_short(document, index):
            short.append(index)
            continue
        if len(short) >= 2:
            yield _short_run_violation(document, short)
        short = []
    if len(short) >= 2:
        yield _short_run_violation(document, short)


def _is_needlessly_short(document: Document, index: int) -> bool:
    """True when the line is short and the next word would have fitted.

    A line ending before a long inline-math atom cannot be lengthened, so
    flagging it would report something no fixer can repair.
    """
    line = document.lines[index].rstrip()
    if len(line) >= SHORT_LINE:
        return False
    nxt = first_atom(document.lines[index + 1])
    return bool(nxt) and len(line) + 1 + len(nxt) <= WRAP_TARGET


def _short_run_violation(document: Document, short: list[int]) -> Violation:
    return at_line(
        document,
        "tex-short-lines",
        short[0] + 1,
        f"{len(short)} consecutive prose lines under {SHORT_LINE} chars; rewrap near 80",
    )


def algo_period_offsets(document: Document) -> list[tuple[int, int]]:
    """Offsets of stray step-ending periods, paired with their line number."""
    found = []
    for span in _body_spans(document, ALGO):
        first = document.line_of(span.start)
        last = document.line_of(max(span.start, span.end - 1))
        for lineno in range(first, last + 1):
            line = document.lines[lineno - 1].rstrip()
            if not line.endswith(".") or SKIP_LINE_RE.match(line):
                continue
            if len(SENTENCE_END_RE.findall(line)) > 1:
                continue
            start, _ = document.line_span(lineno)
            found.append((start + len(line) - 1, lineno))
    return found


@register(
    id="algo-period",
    section="Equations",
    severity=WARN,
    applies_to=TEX,
    summary="End a single-sentence algorithm step without a period.",
    bad="\\State Swap $a$ and $b$.",
    good="\\State Swap $a$ and $b$",
)
def check_algo_period(document: Document) -> Iterable[Violation]:
    for _, lineno in algo_period_offsets(document):
        yield at_line(
            document,
            "algo-period",
            lineno,
            "single-sentence algorithm step ends with a period; drop it",
        )
