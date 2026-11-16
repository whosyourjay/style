"""Punctuation joining prose clauses, outside mathematical and literal syntax."""

from __future__ import annotations

import re

from .document import DISPLAY, INLINE, Document
from .rule import WARN, make, register
from .tex_args import COMMAND_RE, braced_arg_at, optional_arg_at

PROSE_SUFFIXES = (".md", ".tex", ".txt")
SEPARATOR_RE = re.compile(r"(?<!\\)[:;](?=\s)")
SENTENCE_BREAK_RE = re.compile(r"[.!?;:]|\n[ \t]*\n")
WORD_RE = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")
CLAUSE_START_RE = re.compile(
    r"\b(?:we|it|this|that|is|are|let|put|assume|suppose|apply|choose|fix|"
    r"return|take|write|use|since|then|thus|hence)\b", re.I,
)
BLOCK_START_RE = re.compile(
    r"\s*(?:\\begin\{[A-Za-z*]+\}|\\npprob\b|"
    r"\n[ \t]*(?:[-*+]|\d+[.)])[ \t]+)"
)
HIDDEN_ARGUMENTS = frozenset({
    "label", "ref", "eqref", "autoref", "cref", "Cref", "cite", "citep",
    "citet", "url", "path", "href", "begin", "end", "title", "part",
    "chapter", "section", "subsection", "subsubsection", "paragraph",
    "subparagraph", "input", "include", "includegraphics", "hspace", "vspace",
})
PROSE_START_COMMANDS = frozenset({"caption", "footnote", "footnotetext"})


def _clause_mask(document: Document) -> str:
    masked = list(document.prose_mask())
    for span in document.spans_of(INLINE, DISPLAY):
        if document.in_body(span.start):
            masked[span.start] = "@" if span.kind == INLINE else "."
    source = "".join(masked)
    for command in COMMAND_RE.finditer(source):
        name = command.group()[1:]
        end = command.end()
        if name in HIDDEN_ARGUMENTS or name in PROSE_START_COMMANDS:
            if source[end:end + 1] == "*":
                end += 1
            for _ in range(2):
                _, end = optional_arg_at(source, end)
            if name in HIDDEN_ARGUMENTS:
                _, end = braced_arg_at(source, end)
        for index in range(command.start(), end):
            if masked[index] != "\n":
                masked[index] = " "
        if name in PROSE_START_COMMANDS:
            masked[command.start()] = "."
    for heading in re.finditer(r"(?m)^#{1,6}[ \t]+.*$", source):
        masked[heading.start():heading.end()] = " " * len(heading.group())
    return "".join(masked)


@register(
    id="prose-clause-separator",
    section="Write like a human",
    severity=WARN,
    applies_to=PROSE_SUFFIXES,
    summary="Almost never join prose sentences with a colon or semicolon.",
    detail=(
        "Use separate sentences or a direct conjunction. Capitalizing the "
        "clause after a colon does not resolve this rule. The detector skips "
        "mathematics, literal syntax, headings, short labels, and colons "
        "introducing lists or displays. Record a deliberate exception in "
        ".styleck-allow. Rewriting clauses requires judgment, so there is no "
        "automatic fixer."
    ),
    bad="The algorithm need not find this witness: its existence suffices.",
    good="The algorithm need not find this witness. Its existence suffices.",
)
def check_prose_clause_separator(document: Document):
    mask = _clause_mask(document)
    for match in SEPARATOR_RE.finditer(mask):
        if match.group() == ":" and BLOCK_START_RE.match(document.text, match.end()):
            continue
        left = SENTENCE_BREAK_RE.split(mask[max(0, match.start() - 512):match.start()])[-1]
        right = SENTENCE_BREAK_RE.split(mask[match.end():match.end() + 512])[0]
        words = WORD_RE.findall(left)
        if not words or not WORD_RE.search(right):
            continue
        if len(words) < 3 and "@" not in left and not CLAUSE_START_RE.search(left):
            continue
        yield make(
            document, "prose-clause-separator", match.start(),
            f"'{match.group()}' joins prose clauses; use separate sentences or a conjunction",
        )
