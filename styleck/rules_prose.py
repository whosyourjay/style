"""Rules for writing like a human."""

from __future__ import annotations

import re
from typing import Iterable

from .document import COMMENT, TEX_SUFFIXES, Document
from .rule import ERROR, WARN, Violation, make, register

PROSE_SUFFIXES = (".md", ".tex", ".txt")
TEX_ONLY = tuple(sorted(TEX_SUFFIXES))

# Words ending in -ly that are not the trailing adverbs the rule targets.
ADVERB_EXCEPTIONS = frozenset({
    "apply", "ally", "anomaly", "assembly", "comply", "costly", "early",
    "family", "friendly", "holy", "imply", "italy", "jelly", "july", "likely",
    "lonely", "monopoly", "multiply", "only", "orderly", "panoply", "poly",
    "rely", "reply", "respectively", "supply", "ugly", "unlikely",
})

ADVERB_TAIL_RE = re.compile(r"\b([A-Za-z]+ly)\s*\.(?=\s|\Z)")
DISPLAY_WORD_RE = re.compile(r"\bthe\s+(?:above\s+|following\s+)?display(?:ed)?\b", re.I)
VAGUE_REFERENCE_RE = re.compile(
    r"\bthe\s+(?:theorem|lemma|proposition|corollary)\b", re.I
)
UNSPECIFIED_CONVENTION_RE = re.compile(
    r"\b(?:a|an|the|some)\s+(?:fixed|usual|standard|chosen)\s+convention\b", re.I
)
TERM_RE = re.compile(r"\\term\s*\{([^{}]+)\}")
DEFINITION_TITLE_RE = re.compile(r"\\begin\{definition\}\s*\[[^\]]*\]")
NAMING_RE = re.compile(
    r"\b(?:is|are|was|were)\s+(?:called|denoted|known\s+as|said\s+to\s+be)\b", re.I
)
HEDGE_RE = re.compile(
    r"\bit\s+(?:can\s+be\s+(?:shown|seen)|is\s+(?:easy\s+to\s+see|clear|"
    r"well[\s-]known|worth\s+noting)|should\s+be\s+noted|turns\s+out)\b",
    re.I,
)
EMPTY_ADVERB_RE = re.compile(
    r"\b(?:clearly|obviously|trivially|evidently|essentially|crucially|"
    r"importantly|notably|fundamentally|seamlessly|elegantly|nicely|"
    r"straightforwardly)\b",
    re.I,
)
EMPTY_ADJECTIVE_RE = re.compile(
    r"\b(?:novel|powerful|seamless|comprehensive|cutting[\s-]edge|"
    r"state[\s-]of[\s-]the[\s-]art|robust|versatile|holistic|myriad|"
    r"plethora|invaluable)\b",
    re.I,
)
META_RE = re.compile(
    r"\b(?:as\s+requested|per\s+your|as\s+you\s+asked|changed\s+from|"
    r"was\s+previously|previously\s+(?:this|we|it)|used\s+to\s+be|"
    r"instead\s+of\s+the\s+old|note\s*:\s*i\b|i\s+(?:removed|added|changed)|"
    r"we\s+(?:removed|changed)\s+this|updated\s+to\s+|no\s+longer\s+needed)",
    re.I,
)


def _scan_prose(document: Document, rule_id: str, pattern: re.Pattern,
                template: str) -> Iterable[Violation]:
    """Report every match of `pattern` in the document's prose."""
    for match in pattern.finditer(document.prose_mask()):
        yield make(document, rule_id, match.start(), template.format(match.group(0)))


@register(
    id="the-display",
    section="Write like a human",
    severity=ERROR,
    applies_to=PROSE_SUFFIXES,
    summary="Never write `the display` to refer to a display equation.",
    detail="Number the equation and reference it, or just say `this`.",
    bad="Combining the display with Lemma 2 gives the bound.",
    good="Combining \\eqref{eq:phi} with Lemma 2 gives the bound.",
)
def check_the_display(document: Document) -> Iterable[Violation]:
    return _scan_prose(
        document, "the-display", DISPLAY_WORD_RE,
        'nobody says "{}"; number the equation or say "this"',
    )


@register(
    id="precise-reference",
    section="Write like a human",
    severity=WARN,
    applies_to=TEX_ONLY,
    summary="Replace vague theorem references with a numbered reference.",
    detail=(
        "Write `Theorem~\\ref{...}` or name the exact result. A nearby result "
        "may feel obvious while writing but becomes ambiguous after revision."
    ),
    bad="The theorem also permits zero probabilities.",
    good="Theorem~\\ref{thm:main} also permits zero probabilities.",
)
def check_precise_reference(document: Document) -> Iterable[Violation]:
    return _scan_prose(
        document,
        "precise-reference",
        VAGUE_REFERENCE_RE,
        "vague reference '{}'; cite or name the exact result",
    )


@register(
    id="state-conventions",
    section="Write like a human",
    severity=WARN,
    applies_to=TEX_ONLY,
    summary="State boundary and degeneracy conventions in concrete terms.",
    detail=(
        "Do not hide behavior behind a `fixed`, `usual`, or `standard` "
        "convention. Say what happens and, when relevant, why another choice "
        "would not change the result."
    ),
    bad="A fixed convention handles actions at the right boundary.",
    good="If an action extends past $x_n$, emit the remaining suffix unchanged.",
)
def check_state_conventions(document: Document) -> Iterable[Violation]:
    return _scan_prose(
        document,
        "state-conventions",
        UNSPECIFIED_CONVENTION_RE,
        "'{}' hides the actual rule; state what happens",
    )


def _term_pattern(term: str) -> re.Pattern:
    parts = term.split()
    body = r"\s+".join(re.escape(part) for part in parts)
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", re.I)


def _inside(offset: int, regions: list[tuple[int, int]]) -> bool:
    return any(start <= offset < end for start, end in regions)


@register(
    id="term-first-use",
    section="Write like a human",
    severity=WARN,
    applies_to=TEX_ONLY,
    summary="Mark a technical term where it first appears, not later.",
    detail=(
        "Use one definition macro such as `\\term{...}` at the first "
        "substantive occurrence. In an abstract, either define proof-internal "
        "vocabulary in plain language or paraphrase it. The checker covers "
        "literal multiword terms; variants and one-word terms still require "
        "judgment."
    ),
    bad=(
        "The alignment path records the script.\n"
        "Later, the \\term{alignment path} is defined formally."
    ),
    good="The \\term{alignment path} records the script in lattice coordinates.",
)
def check_term_first_use(document: Document) -> Iterable[Violation]:
    prose = document.prose_mask()
    title_regions = [
        (match.start(), match.end())
        for match in DEFINITION_TITLE_RE.finditer(document.text)
    ]
    seen: set[str] = set()
    for marked in TERM_RE.finditer(document.text):
        if not document.in_body(marked.start()):
            continue
        term = " ".join(marked.group(1).split())
        words = re.findall(r"[A-Za-z][A-Za-z0-9-]*", term)
        if len(words) < 2 or len("".join(words)) != len(term.replace(" ", "")):
            continue
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        for earlier in _term_pattern(term).finditer(prose, 0, marked.start()):
            if _inside(earlier.start(), title_regions):
                continue
            yield make(
                document,
                "term-first-use",
                earlier.start(),
                f"'{earlier.group(0)}' appears before its first \\term{{...}} marking",
            )
            break


@register(
    id="adverb-tail",
    section="Write like a human",
    severity=WARN,
    applies_to=PROSE_SUFFIXES,
    summary="Test a sentence that ends in an -ly adverb: delete it and reread.",
    detail=(
        "This is a smell, not a ban. If the sentence still says what you mean "
        "without the adverb, the adverb was padding. If deleting it loses "
        "something, keep it. \"Applied unevenly\" survives the test; \"arrange "
        "the deck cleanly\" does not."
    ),
    bad="We arrange the deck cleanly.",
    good="We sort the deck.",
)
def check_adverb_tail(document: Document) -> Iterable[Violation]:
    for match in ADVERB_TAIL_RE.finditer(document.prose_mask()):
        word = match.group(1)
        if word.lower() in ADVERB_EXCEPTIONS:
            continue
        yield make(
            document, "adverb-tail", match.start(1),
            f"sentence ends with '{word}'; delete it and reread — if nothing is "
            "lost, leave it out",
        )


@register(
    id="voice-naming",
    section="Write like a human",
    severity=WARN,
    applies_to=PROSE_SUFFIXES,
    summary="Name things with an active sentence, not a passive one.",
    detail="Put the named actor before the verb.",
    bad="A vertex of in-degree at least 11 is called heavy.",
    good="We call a vertex heavy when its in-degree reaches 11.",
)
def check_voice_naming(document: Document) -> Iterable[Violation]:
    return _scan_prose(
        document, "voice-naming", NAMING_RE,
        "passive naming '{}'; put the actor before the verb",
    )


@register(
    id="voice-hedge",
    section="Write like a human",
    severity=WARN,
    applies_to=PROSE_SUFFIXES,
    summary="Drop hedges like `it can be shown that`.",
    detail="State the claim, or point at the argument that proves it.",
    bad="It can be shown that $\\Phi$ decreases.",
    good="Lemma 3 shows that $\\Phi$ decreases.",
)
def check_voice_hedge(document: Document) -> Iterable[Violation]:
    return _scan_prose(
        document, "voice-hedge", HEDGE_RE,
        "hedge '{}'; state the claim or cite the argument",
    )


@register(
    id="empty-adverb",
    section="Write like a human",
    severity=WARN,
    applies_to=PROSE_SUFFIXES,
    summary="Cut adverbs that add no information.",
    detail="If the step really is clear, the reader does not need to be told.",
    bad="Clearly the potential drops.",
    good="The potential drops because each square shrinks.",
)
def check_empty_adverb(document: Document) -> Iterable[Violation]:
    return _scan_prose(
        document, "empty-adverb", EMPTY_ADVERB_RE,
        "'{}' adds nothing; cut it or give the reason",
    )


@register(
    id="empty-adjective",
    section="Write like a human",
    severity=WARN,
    applies_to=PROSE_SUFFIXES,
    summary="Cut jargony adjectives that do not change the meaning.",
    bad="This novel, powerful technique is comprehensive.",
    good="This technique handles every case in one pass.",
)
def check_empty_adjective(document: Document) -> Iterable[Violation]:
    return _scan_prose(
        document, "empty-adjective", EMPTY_ADJECTIVE_RE,
        "'{}' is marketing language; say what the thing does",
    )


@register(
    id="meta-commentary",
    section="Write like a human",
    severity=ERROR,
    applies_to=TEX_ONLY,
    summary="Never record edit history or your reasoning in the paper.",
    detail="Explain a change in chat. The file holds the current state only.",
    bad="% changed from a linear bound as requested",
    good="",
)
def check_meta_commentary(document: Document) -> Iterable[Violation]:
    for start, text in _comments(document):
        for match in META_RE.finditer(text):
            yield make(
                document, "meta-commentary", start + match.start(),
                f"comment records edit history ('{match.group(0).strip()}'); "
                "say it in chat instead",
            )


def _comments(document: Document) -> list[tuple[int, str]]:
    """LaTeX comment regions as (offset, text) pairs."""
    spans = [s for s in document.spans if s.kind == COMMENT]
    return [(s.start, document.text[s.start:s.end]) for s in spans]
