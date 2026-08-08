"""Segment a source file into prose, math, and verbatim regions.

Every rule works off a Document. The scanner is char-based so that offsets map
back to exact line/column positions for the reported violations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PROSE = "prose"
COMMENT = "comment"
INLINE = "inline"
DISPLAY = "display"
VERBATIM = "verbatim"
ALGO = "algo"

DISPLAY_ENVS = frozenset({
    "equation", "equation*", "align", "align*", "alignat", "alignat*",
    "gather", "gather*", "multline", "multline*", "eqnarray", "eqnarray*",
    "displaymath", "flalign", "flalign*", "split", "IEEEeqnarray",
})
# Environments whose contents no prose or layout rule should touch: either
# they are not prose at all, or their short lines are structural.
VERBATIM_ENVS = frozenset({
    "verbatim", "Verbatim", "lstlisting", "minted", "tikzpicture", "comment",
    "filecontents", "filecontents*", "picture", "pgfpicture",
    "thebibliography", "tabular", "tabularx", "longtable", "array",
})
ALGO_ENVS = frozenset({
    "algorithm", "algorithm*", "algorithmic", "algorithmic*", "algorithm2e",
    "algorithmvv", "pseudocode",
})

BEGIN_RE = re.compile(r"\\begin\{([A-Za-z@*]+)\}")
COMMAND_RE = re.compile(r"\\(?:[A-Za-z@]+\*?|.)", re.S)
TEX_SUFFIXES = frozenset({".tex", ".sty", ".cls", ".tikz"})


@dataclass(frozen=True)
class Span:
    """A contiguous region of the source with a single kind."""

    kind: str
    start: int
    end: int
    env: str | None = None


def _kind_for_env(env: str) -> str:
    if env in VERBATIM_ENVS:
        return VERBATIM
    if env in ALGO_ENVS:
        return ALGO
    return DISPLAY


def _find_unescaped(text: str, needle: str, start: int) -> int:
    """Index just past the next unescaped `needle`, or len(text)."""
    pos = start
    while True:
        found = text.find(needle, pos)
        if found < 0:
            return len(text)
        backslashes = 0
        probe = found - 1
        while probe >= 0 and text[probe] == "\\":
            backslashes += 1
            probe -= 1
        if backslashes % 2 == 0:
            return found + len(needle)
        pos = found + 1


def _find_env_end(text: str, env: str, start: int) -> int:
    """Index just past the matching `\\end{env}`, honouring nesting."""
    opener = "\\begin{" + env + "}"
    closer = "\\end{" + env + "}"
    depth = 1
    pos = start
    while depth > 0:
        next_open = text.find(opener, pos)
        next_close = text.find(closer, pos)
        if next_close < 0:
            return len(text)
        if 0 <= next_open < next_close:
            depth += 1
            pos = next_open + len(opener)
            continue
        depth -= 1
        pos = next_close + len(closer)
    return pos


def scan(text: str) -> list[Span]:
    """Split `text` into non-overlapping spans covering the whole string."""
    marked: list[Span] = []
    pos, size = 0, len(text)
    while pos < size:
        char = text[pos]
        if char == "%":
            stop = text.find("\n", pos)
            stop = size if stop < 0 else stop
            marked.append(Span(COMMENT, pos, stop))
            pos = stop
        elif char == "$":
            double = text.startswith("$$", pos)
            token = "$$" if double else "$"
            stop = _find_unescaped(text, token, pos + len(token))
            marked.append(Span(DISPLAY if double else INLINE, pos, stop))
            pos = stop
        elif char == "\\":
            pos = _scan_backslash(text, pos, marked)
        else:
            pos += 1
    return _fill_gaps(marked, size)


def _scan_backslash(text: str, pos: int, marked: list[Span]) -> int:
    """Consume the construct starting at a backslash; append any span found."""
    begin = BEGIN_RE.match(text, pos)
    if begin:
        env = begin.group(1)
        if env in DISPLAY_ENVS or env in VERBATIM_ENVS or env in ALGO_ENVS:
            stop = _find_env_end(text, env, begin.end())
            marked.append(Span(_kind_for_env(env), pos, stop, env))
            return stop
        return begin.end()
    if text.startswith("\\[", pos):
        stop = _find_unescaped(text, "\\]", pos + 2)
        marked.append(Span(DISPLAY, pos, stop))
        return stop
    if text.startswith("\\(", pos):
        stop = _find_unescaped(text, "\\)", pos + 2)
        marked.append(Span(INLINE, pos, stop))
        return stop
    command = COMMAND_RE.match(text, pos)
    return command.end() if command else pos + 1


FENCE_RE = re.compile(r"^[ \t]*(?:```|~~~).*$", re.M)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def scan_markdown(text: str) -> list[Span]:
    """Mark fenced blocks and inline code so prose rules skip the samples."""
    marked: list[Span] = []
    fences = [m for m in FENCE_RE.finditer(text)]
    covered = 0
    for opener, closer in zip(fences[0::2], fences[1::2]):
        marked.append(Span(VERBATIM, opener.start(), closer.end()))
        covered = closer.end()
    if len(fences) % 2:
        marked.append(Span(VERBATIM, fences[-1].start(), len(text)))
        covered = len(text)
    for match in INLINE_CODE_RE.finditer(text):
        if match.start() >= covered or not any(
            s.start <= match.start() < s.end for s in marked
        ):
            marked.append(Span(VERBATIM, match.start(), match.end()))
    marked.sort(key=lambda s: s.start)
    trimmed: list[Span] = []
    for span in marked:
        if trimmed and span.start < trimmed[-1].end:
            continue
        trimmed.append(span)
    return _fill_gaps(trimmed, len(text))


def _fill_gaps(marked: list[Span], size: int) -> list[Span]:
    spans: list[Span] = []
    cursor = 0
    for span in marked:
        if span.start > cursor:
            spans.append(Span(PROSE, cursor, span.start))
        spans.append(span)
        cursor = span.end
    if cursor < size:
        spans.append(Span(PROSE, cursor, size))
    return spans


class Document:
    """A source file plus its span decomposition and line index."""

    def __init__(self, path: str, text: str) -> None:
        self.path = path
        self.text = text
        self.lines = text.split("\n")
        self.suffix = "." + path.rsplit(".", 1)[-1] if "." in path else ""
        self.is_tex = self.suffix in TEX_SUFFIXES
        self.spans = self._scan(text)
        self._line_starts = self._compute_line_starts()
        self.body_start = self._compute_body_start()
        self._line_kinds: list[set[str]] | None = None
        self._mask: str | None = None

    def _scan(self, text: str) -> list[Span]:
        if self.is_tex:
            return scan(text)
        if self.suffix == ".md":
            return scan_markdown(text)
        return [Span(PROSE, 0, len(text))]

    def _compute_line_starts(self) -> list[int]:
        starts, total = [0], 0
        for line in self.lines[:-1]:
            total += len(line) + 1
            starts.append(total)
        return starts

    def _compute_body_start(self) -> int:
        marker = self.text.find("\\begin{document}")
        return 0 if marker < 0 else marker

    def line_of(self, offset: int) -> int:
        """1-based line number containing `offset`."""
        low, high = 0, len(self._line_starts) - 1
        while low < high:
            mid = (low + high + 1) // 2
            if self._line_starts[mid] <= offset:
                low = mid
            else:
                high = mid - 1
        return low + 1

    def column_of(self, offset: int) -> int:
        return offset - self._line_starts[self.line_of(offset) - 1] + 1

    def line_span(self, lineno: int) -> tuple[int, int]:
        start = self._line_starts[lineno - 1]
        return start, start + len(self.lines[lineno - 1])

    def in_body(self, offset: int) -> bool:
        return offset >= self.body_start

    def line_kinds(self) -> list[set[str]]:
        """Per line (0-based index), the set of span kinds touching it."""
        if self._line_kinds is not None:
            return self._line_kinds
        kinds: list[set[str]] = [set() for _ in self.lines]
        for span in self.spans:
            first = self.line_of(span.start) - 1
            last = self.line_of(max(span.start, span.end - 1)) - 1
            for index in range(first, min(last + 1, len(kinds))):
                if span.kind == PROSE and not self.text[span.start:span.end].strip():
                    continue
                kinds[index].add(span.kind)
        self._line_kinds = kinds
        return kinds

    def prose_mask(self) -> str:
        """The text with every non-prose character blanked to a space.

        Offsets are preserved, so a match in the mask reports the right
        position in the original file.
        """
        if self._mask is not None:
            return self._mask
        buffer = [" "] * len(self.text)
        for index, char in enumerate(self.text):
            if char == "\n":
                buffer[index] = "\n"
        for span in self.spans:
            if span.kind != PROSE or span.end <= self.body_start:
                continue
            start = max(span.start, self.body_start)
            for index in range(start, span.end):
                buffer[index] = self.text[index]
        self._mask = "".join(buffer)
        return self._mask

    def spans_of(self, *kinds: str) -> list[Span]:
        wanted = frozenset(kinds)
        return [s for s in self.spans if s.kind in wanted]


def load(path: str) -> Document:
    with open(path, encoding="utf-8", errors="replace") as handle:
        return Document(path, handle.read())
