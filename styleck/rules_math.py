"""Mathematical notation rules."""

from __future__ import annotations

import re

from .document import DISPLAY, INLINE, TEX_SUFFIXES, Document, _find_env_end
from .rule import ERROR, make, register
from .tex_args import COMMAND_RE, braced_arg_at, optional_arg_at, visible_source

TEX = tuple(sorted(TEX_SUFFIXES))
ELLIPSES = {r"\dots", r"\ldots", r"\cdots"}
GRID_BEGIN_RE = re.compile(r"\\begin\{([A-Za-z]*matrix\*?|array|subarray)\}")
TEXT_ARGS = {
    **dict.fromkeys((
        "text", "textrm", "textnormal", "textsf", "texttt", "textbf",
        "textit", "textsl", "textsc", "textup", "mbox", "hbox",
        "intertext", "shortintertext", "operatorname", "label", "tag",
        "ref", "eqref", "cref", "Cref", "cite", "url",
    ), 1),
    "href": 2,
}
SCRIPT_ARGS = {
    **TEXT_ARGS,
    **dict.fromkeys(("frac", "dfrac", "tfrac", "binom", "dbinom", "tbinom"), 2),
    **dict.fromkeys(("sqrt", "mathrm", "mathbf", "mathit", "mathsf",
                    "mathbb", "mathcal"), 1),
}
SLASH_RE = re.compile(r"(?<!\\)/|\\slash\b")


@register(
    id="math-ellipsis",
    section="Equations",
    severity=ERROR,
    applies_to=TEX,
    summary="Give sequences an explicit index set instead of mathematical ellipses.",
    detail=(
        r"Replace \dots, \ldots, and \cdots with indexed sets, tuples, sums, "
        "or products in inline and display math. Matrix and array layouts are "
        "exempt. Record deliberate exceptions in .styleck-allow."
    ),
    bad=r"$x_1,\ldots,x_n$",
    good=r"$(x_i)_{i\in[n]}$",
)
def check_math_ellipsis(document: Document):
    source = visible_source(document)
    grids = []
    for token in COMMAND_RE.finditer(source):
        if token.group() == r"\begin":
            grid = GRID_BEGIN_RE.match(source, token.start())
            if grid:
                end = _find_env_end(source, grid.group(1), grid.end())
                grids.append((grid.start(), end))
        if token.group() not in ELLIPSES or not document.in_body(token.start()):
            continue
        if any(start <= token.start() < end for start, end in grids):
            continue
        yield make(document, "math-ellipsis", token.start(),
                   f"sequence written with {token.group()!r}; index it explicitly")


def _argument_end(text: str, pos: int) -> int:
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos >= len(text):
        return len(text)
    if text[pos] == "{":
        argument, end = braced_arg_at(text, pos)
        return len(text) if argument is None else end
    command = COMMAND_RE.match(text, pos)
    if not command:
        return pos + 1
    name = command.group()[1:]
    pos = command.end()
    if name == "sqrt":
        _, pos = optional_arg_at(text, pos)
    for _ in range(SCRIPT_ARGS.get(name, 0)):
        pos = _argument_end(text, pos)
    return pos


def _fraction_stream(body: str) -> str:
    """Mask prose arguments, preserving mathematical scripts and positions."""
    masked = list(body)
    pos = 0
    while pos < len(body):
        start = pos
        if body[pos] == "\\":
            command = COMMAND_RE.match(body, pos)
            if not command:
                pos += 1
                continue
            name = command.group()[1:]
            pos = command.end()
            if name not in TEXT_ARGS:
                continue
            if body[pos:pos + 1] == "*":
                pos += 1
            while True:
                option, pos = optional_arg_at(body, pos)
                if option is None:
                    break
            for _ in range(TEXT_ARGS[name]):
                pos = _argument_end(body, pos)
        else:
            pos += 1
            continue
        for index in range(start, pos):
            if body[index] != "\n":
                masked[index] = " "
    return "".join(masked)


@register(
    id="math-fraction",
    section="Equations",
    severity=ERROR,
    applies_to=TEX,
    summary="Use typeset fractions instead of bare slashes in math.",
    detail=(
        "This includes simple ratios, inline math, superscripts, and subscripts. "
        r"Use \frac in displays and \frac or \sfrac in inline math and scripts. "
        "Preserve prose and whether an equation is inline or displayed. "
        "Labels, URLs, and other prose arguments are not mathematical fractions. "
        "Quotient notation needs an explicit exception. This rule has no "
        "automatic fixer."
    ),
    bad=r"$n^{1/k}$",
    good=r"$n^{\frac{1}{k}}$",
)
def check_math_fractions(document: Document):
    source = visible_source(document)
    for span in document.spans_of(INLINE, DISPLAY):
        if not document.in_body(span.start):
            continue
        body = _fraction_stream(source[span.start:span.end])
        for match in SLASH_RE.finditer(body):
            yield make(document, "math-fraction", span.start + match.start(),
                       r"bare slash in math; use a typeset fraction")
