"""Rules for writing like a human."""

from __future__ import annotations

import re
from typing import Iterable

from .document import COMMENT, TEX_SUFFIXES, Document
from .rule import ERROR, WARN, Violation, make, register
from .terms import TERM_RE, background_terms, normalize_term

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
    r"\bthe\s+(?:(?!(?:and|as|at|by|for|from|in|of|on|or|to|with)\b)"
    r"[A-Za-z][A-Za-z-]*\s+){0,3}"
    r"(?:theorem|lemma|proposition|corollary)\b",
    re.I,
)
VAGUE_REFERENT_RE = re.compile(
    r"\b(?:the|this|that)\s+"
    r"(?:(?!(?:and|as|at|by|for|from|in|of|on|or|to|with)\b)"
    r"[A-Za-z][A-Za-z-]*\s+){0,2}"
    r"(?:argument|bound|calculation|claim|comparison|conclusion|construction|"
    r"dichotomy|estimate|expression|fact|functional|method|object|order|"
    r"preprocessing|proof|quantity|reduction|remainder|result|side|statement|"
    r"step|term)\b",
    re.I,
)
DIRECT_QUALIFIER_RE = re.compile(
    r"^\s*(?:"
    r"\$"                                     # the expression, written out
    r"|(?:[A-Za-z]+[\s~]+){0,3}\\(?:eqref|ref)\{"  # a citation, a few words along
    r")"
)
INLINE_QUALIFIER_RE = re.compile(r"\$[^$]+\$|\\(?:eqref|ref)\{")
UNSPECIFIED_CONVENTION_RE = re.compile(
    r"\b(?:a|an|the|some)\s+(?:fixed|usual|standard|chosen)\s+convention\b", re.I
)
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
BACKGROUND_FORMULA_TAIL_RE = re.compile(
    r"\s+(?:is|are)\s*(?:\n[ \t]*)?"
    r"\$[^$\n=]{0,80}\([^$\n=]{0,120}\)\s*=[^$\n]{0,240}\$",
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
    prose = document.prose_mask()
    for match in VAGUE_REFERENCE_RE.finditer(prose):
        if _referent_follows(document, match.end()):
            continue
        yield make(
            document,
            "precise-reference",
            match.start(),
            f"vague reference '{match.group(0)}'; cite or name the exact result",
        )


@register(
    id="vague-referent",
    section="Write like a human",
    severity=WARN,
    applies_to=TEX_ONLY,
    summary="Replace abstract `the ...` phrases with an exact referent.",
    detail=(
        "A definite article promises that the reader can identify its noun. "
        "Phrases such as `the bound`, `the same expression`, and `the "
        "functional` often force the reader to search backward. Cite the "
        "equation or result, write the expression, or name the specific "
        "mathematical object. This is a deliberately high-recall warning; "
        "keep a phrase when its referent is genuinely immediate."
    ),
    bad="The same estimate proves the claim.",
    good="Applying \\eqref{eq:local-TV} proves Lemma~\\ref{lem:tail}.",
)
def check_vague_referent(document: Document) -> Iterable[Violation]:
    prose = document.prose_mask()
    background = background_terms(document.path)
    for match in VAGUE_REFERENT_RE.finditer(prose):
        if _referent_follows(document, match.end()):
            continue
        if _referent_inside(document, match.start(), match.end()):
            continue
        noun = match.group(0).split(maxsplit=1)[1]
        if normalize_term(noun) in background:
            continue
        yield make(
            document,
            "vague-referent",
            match.start(),
            f"'{match.group(0)}' has no exact referent; cite it, name it, or write it out",
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


def _term_variants(term: str) -> set[str]:
    """Return a term and its ordinary singular or plural counterpart."""
    words = term.split()
    if not words or not re.fullmatch(r"[A-Za-z]+", words[-1]):
        return {term}
    last = words[-1]
    variants = {term}
    if last.casefold().endswith("ies"):
        counterpart = last[:-3] + "y"
    elif re.search(r"(?:ses|xes|zes|ches|shes)$", last, re.I):
        counterpart = last[:-2]
    elif last.casefold().endswith("s") and not last.casefold().endswith("ss"):
        counterpart = last[:-1]
    elif re.search(r"[^aeiou]y$", last, re.I):
        counterpart = last[:-1] + "ies"
    elif re.search(r"(?:s|x|z|ch|sh)$", last, re.I):
        counterpart = last + "es"
    else:
        counterpart = last + "s"
    variants.add(" ".join((*words[:-1], counterpart)))
    return variants


def _referent_follows(document: Document, offset: int) -> bool:
    """Whether the source at ``offset`` supplies the referent it was promised.

    Reads the source rather than the prose mask, so an expression written out
    in inline math counts alongside a numbered citation.
    """
    return bool(DIRECT_QUALIFIER_RE.match(document.text[offset:offset + 100]))


def _referent_inside(document: Document, start: int, end: int) -> bool:
    r"""Whether the phrase carries its own qualifier, as in ``the $p\log p$ term``.

    The prose mask blanks inline math, so a qualifier standing before the noun
    is invisible to the pattern that found the phrase.
    """
    return bool(INLINE_QUALIFIER_RE.search(document.text[start:end]))


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
    id="term-background",
    section="Write like a human",
    severity=WARN,
    applies_to=TEX_ONLY,
    summary="Do not present project background vocabulary as newly introduced terminology.",
    detail=(
        "List assumed field vocabulary in `.styleck-terms` for a project or "
        "in a source-specific `paper-name.styleck-terms` file. One phrase goes "
        "on each line. An `@relative/path.tex` line imports that source's "
        "`\\term` entries. Background terms may appear without boldface or a "
        "local definition."
    ),
    bad="The \\term{relative entropy} is $D(P\\Vert Q)$.",
    good="Write $D(P\\Vert Q)$ for relative entropy.",
)
def check_term_background(document: Document) -> Iterable[Violation]:
    background = background_terms(document.path)
    if not background:
        return
    for marked in TERM_RE.finditer(document.text):
        if normalize_term(marked.group(1)) not in background:
            continue
        yield make(
            document,
            "term-background",
            marked.start(),
            f"'{marked.group(1)}' is project background; remove the term marking",
        )


@register(
    id="background-redefinition",
    section="Write like a human",
    severity=WARN,
    applies_to=TEX_ONLY,
    summary="Do not rederive project background vocabulary from a formula.",
    detail=(
        "A term listed in `.styleck-terms` is assumed knowledge. Introduce a "
        "notation convention if needed, but omit a textbook-style local "
        "definition. This deliberately narrow check looks for `the term is "
        "$f(x)=...$`; substantive identities still require judgment."
    ),
    bad="The binary entropy function is $h_2(p)=-p\\log p-(1-p)\\log(1-p)$.",
    good="For binary entropy $h_2$, independence gives the required rate.",
)
def check_background_redefinition(document: Document) -> Iterable[Violation]:
    background = background_terms(document.path)
    if not background:
        return
    prose = document.prose_mask()
    for term in sorted(background, key=len, reverse=True):
        for match in _term_pattern(term).finditer(prose):
            prefix = prose[max(0, match.start() - 5):match.start()]
            if not re.search(r"\bthe\s*$", prefix, re.I):
                continue
            tail = document.text[match.end():match.end() + 500]
            if not BACKGROUND_FORMULA_TAIL_RE.match(tail):
                continue
            yield make(
                document,
                "background-redefinition",
                match.start(),
                f"'{match.group(0)}' is background vocabulary; omit its formula definition",
            )


@register(
    id="term-single-use",
    section="Write like a human",
    severity=WARN,
    applies_to=TEX_ONLY,
    summary="Name a technical term only when the paper reuses the name.",
    detail=(
        "A one-off phrase usually needs a direct definition of its symbol, not "
        "a bold name. The checker covers literal multiword terms and ordinary "
        "singular/plural forms; irregular inflections, one-word terms, and "
        "conceptual reuse still require judgment."
    ),
    bad="Define the \\term{window family} $\\mathcal W_m$ to be all intervals.",
    good="Let $\\mathcal W_m$ be the set of all length-$m$ intervals.",
)
def check_term_single_use(document: Document) -> Iterable[Violation]:
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
        mention_offsets = {
            match.start()
            for variant in _term_variants(term)
            for match in _term_pattern(variant).finditer(prose)
            if not _inside(match.start(), title_regions)
        }
        if len(mention_offsets) > 1:
            continue
        yield make(
            document,
            "term-single-use",
            marked.start(),
            f"'{term}' is introduced but never reused by name; define the symbol directly",
        )


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
