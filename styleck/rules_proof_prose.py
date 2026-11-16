"""Proof steps should name the action and state the quantitative bound."""

from __future__ import annotations

import re

from .document import Document
from .rule import WARN, make, manual, register
from .rules_punctuation import _clause_mask

PROSE_SUFFIXES = (".md", ".tex", ".txt")
NAMED_BOUND_RE = re.compile(
    r"\b(?:Chernoff|Hoeffding|Markov(?:['’]s)?|Chebyshev(?:['’]s)?|"
    r"Jensen(?:['’]s)?|Cauchy[-–]Schwarz|Azuma(?:[-–]Hoeffding)?|"
    r"Bernstein|union)\s+(?:bound|inequality)\b", re.I,
)
INDEFINITE_RE = re.compile(
    r"\b(?:a|an)\s+(?:(?:multiplicative|additive|one-sided|two-sided)\s+)?$", re.I,
)
BOUND_VERB_RE = re.compile(
    r"\s+(?:gives?|yields?|provides?|implies|establishes|bounds|limits|ensures)\b", re.I,
)
APPLY_RE = re.compile(
    r"\b(?:apply(?:ing)?|us(?:e|ing)|prov(?:e|ing)|deriv(?:e|ing))\s+the\s+$", re.I,
)
NOMINALIZED_RE = re.compile(
    r"\b(?:(?:is|are|was|were)\s+(?:an?|the)\s+"
    r"(?:application|computation|construction|verification|simulation|selection)\s+of"
    r"|reach(?:es|ed)?\s+(?:its|their|the)\s+completion"
    r"|(?:its|their)\s+existence\s+(?:proves|shows)"
    r"|(?:completeness|soundness)\s+guarantee\s+(?:then\s+)?"
    r"(?:supplies|provides|gives|ensures)"
    r"|counting\s+(?:supplies|provides)\s+decision)\b", re.I,
)
OVERHEAD_RE = re.compile(r"\b(?:fixed\s+)?polynomial\s+overhead\b", re.I)
EXPLICIT_OVERHEAD_RE = re.compile(
    r"\s*[,:(]?\s*(?:(?:of|is|bounded by|at most)\s+)?"
    r"(?:\$|\\\(|\\(?:eqref|ref)\{)"
)
GERUND_RE = re.compile(r"\b[A-Z][a-z]+ing\b")
GERUND_NONACTIONS = frozenset({
    "assuming", "supposing", "considering", "according",
    "remaining", "existing", "corresponding", "leading", "surrounding",
    "interesting", "string", "spring", "thing", "something", "anything",
    "nothing", "everything", "morning", "evening",
})
FINITE_VERB_RE = re.compile(
    r"\b(?:is|was|has|had|does|did|can|could|may|might|must|will|would|"
    r"gives|gave|leaves|left|makes|made|takes|took|lets|"
    r"(?:identif|simplif|suppl|impl)(?:ies|ied)|"
    r"(?:add|allow|avoid|change|cost|create|define|delete|ensure|establish|"
    r"exclude|expose|fail|find|force|guarantee|increase|introduce|"
    r"keep|limit|need|preserve|prevent|produce|prove|provide|recover|reduce|"
    r"remain|remove|require|return|save|show|solve|suffice|"
    r"use|yield)(?:s|d|ed))\b", re.I,
)


@register(
    id="apply-named-bound",
    section="Write like a human",
    severity=WARN,
    applies_to=PROSE_SUFFIXES,
    summary="Apply the named inequality instead of saying that a bound gives the result.",
    detail=(
        "Write `Apply the Chernoff bound to obtain ...`. Use `the` for an "
        "established inequality, including the union bound. Avoid `a Chernoff "
        "bound gives ...` and `the Chernoff bound gives ...`. The proof step "
        "is our application of the result. New variants can use a "
        "local exception."
    ),
    bad="A Chernoff bound gives the required probability.",
    good="Apply the Chernoff bound to obtain the required probability.",
)
def check_apply_named_bound(document: Document):
    mask = document.prose_mask()
    for match in NAMED_BOUND_RE.finditer(mask):
        prefix = mask[max(0, match.start() - 100):match.start()]
        indefinite = INDEFINITE_RE.search(prefix)
        subject = BOUND_VERB_RE.match(mask, match.end()) and not APPLY_RE.search(prefix)
        if indefinite or subject:
            yield make(
                document, "apply-named-bound", match.start(),
                f"write 'Apply the {match.group()} to obtain ...' or 'By the {match.group()}, ...'",
            )


@register(
    id="proof-step-action",
    section="Write like a human",
    severity=WARN,
    applies_to=PROSE_SUFFIXES,
    summary="Use the action verb in a proof step.",
    detail=(
        "Prefer `apply`, `compute`, `construct`, `verify`, `simulate`, or "
        "`halt` to `is an application of`, `is a computation of`, or `reaches "
        "its completion`. State what the chosen witness proves instead of "
        "making `its existence` the actor. This rule concerns descriptions "
        "of proof steps. Also avoid abstract actors such as `the "
        "completeness guarantee supplies ...`; invoke the precise condition "
        "and state what follows. Mathematical definitions and predicates "
        "do not need action verbs."
    ),
    bad="Simulation reaches its completion.",
    good=r"$D_k$ halts.",
)
def check_proof_step_action(document: Document):
    for match in NOMINALIZED_RE.finditer(document.prose_mask()):
        yield make(document, "proof-step-action", match.start(),
                   f"'{match.group()}' hides the action; name the actor and use the verb")


@register(
    id="gerund-subject",
    section="Write like a human",
    severity=WARN,
    applies_to=PROSE_SUFFIXES,
    summary="Review an '-ing ... verb' sentence: state the action or its result directly.",
    detail=(
        "A gerund phrase used as the subject often makes a proof step harder "
        "to read: 'Deleting X exposes Y', 'Applying the lemma gives ...', "
        "or 'Encoding the cases lets us ...'. Prefer an instruction followed "
        "by its consequence, an explicit actor, or the resulting mathematical "
        "statement. This is a warning sign, not a ban. Keep a gerund when the "
        "activity itself is the subject and that wording is clearest. "
        "Headings and introductory phrases such as 'Using X, we ...' are "
        "different constructions. The detector covers common finite verbs."
    ),
    bad=r"Deleting $L_T$ exposes the crossing heads.",
    good=r"Delete $L_T$. The crossing heads become sources.",
)
def check_gerund_subject(document: Document):
    prose = _clause_mask(document)
    for match in GERUND_RE.finditer(prose):
        if match.group().casefold() in GERUND_NONACTIONS:
            continue
        prefix = prose[:match.start()].rstrip()
        if prefix and prefix[-1] not in ".!?:;{":
            continue
        tail = prose[match.end():match.end() + 300]
        clause = re.split(r"[,.!?;:]|\n[ \t]*\n", tail, maxsplit=1)[0]
        verb = FINITE_VERB_RE.search(clause)
        if verb is None:
            continue
        if re.search(r"\b(?:we|you|they|he|she|it|who|which|that|when|while|if)\b",
                     clause[:verb.start()], re.I):
            continue
        yield make(
            document, "gerund-subject", match.start(),
            f"'{match.group()} ... {verb.group()}' uses an action as the subject; "
            "consider a direct instruction, actor, or mathematical conclusion",
        )


@register(
    id="polynomial-overhead",
    section="Write like a human",
    severity=WARN,
    applies_to=PROSE_SUFFIXES,
    summary="Give a bound for simulation overhead and state its dependencies.",
    detail=(
        "A `fixed polynomial overhead of its running time` leaves the "
        "polynomial's arguments and degree unspecified. Write a bound or "
        "reference one, and say which parameters its constants may depend "
        "on. This matters when the proof varies parameters to obtain a "
        "subexponential running time."
    ),
    bad="Simulation takes a fixed polynomial overhead of its running time.",
    good=r"The simulation takes at most $(rT)^c$ steps for an absolute constant $c$.",
)
def check_polynomial_overhead(document: Document):
    for match in OVERHEAD_RE.finditer(document.prose_mask()):
        if EXPLICIT_OVERHEAD_RE.match(document.text, match.end()):
            continue
        yield make(document, "polynomial-overhead", match.start(),
                   "state the overhead as a bound and specify what its constants depend on")


manual(
    id="named-object-reference",
    section="Write like a human",
    summary="Use an object's name when the argument depends on which object it is.",
    detail=(
        "If the proof names algorithms D and D_k, use those names where "
        "`this procedure`, `the implemented algorithm`, or `the algorithm "
        "and its running-time bound` makes the reader reconstruct the "
        "referent. Name the functions and parameters on which a constant "
        "depends. Identify the cases meant by `early-return branches`. "
        "Replace ambiguous possessives such as `its recursion` with the "
        "algorithm's name. Use an existing symbol instead of a repeated "
        "verbal description of a circuit or function. An immediate, "
        "unambiguous pronoun is fine."
    ),
    bad="Eventually this procedure participates and is admissible.",
    good=r"For sufficiently large $s$, $D_k$ is among the simulated procedures and is admissible.",
)

@register(
    id="named-reference",
    section="Write like a human",
    severity=WARN,
    applies_to=PROSE_SUFFIXES,
    summary="Replace `named` with the symbol or cross-reference that identifies the object.",
    detail=(
        "`The named subcircuits` and `the named lemma` make the reader search "
        "for a name. Write the symbols or link to the result. Keep `named` "
        "only when the act of naming or a technical naming convention matters."
    ),
    bad="The circuit retains the named subcircuits.",
    good=r"The circuit retains $P_0,S_0,H$.",
)
def check_named_reference(document: Document):
    for match in re.finditer(r"\bnamed\b", document.prose_mask(), re.I):
        yield make(document, "named-reference", match.start(),
                   "replace 'named' with the symbol or cross-reference, unless naming itself matters")


@register(
    id="wordy-math-condition",
    section="Write like a human",
    severity=WARN,
    applies_to=PROSE_SUFFIXES,
    summary="State a condition on an expression directly, rather than describing its value in words.",
    bad=r"A zero value of $H(x)$ leaves a direct edge.",
    good=r"When $H(x)=0$, keep a direct edge.",
)
def check_wordy_math_condition(document: Document):
    pattern = r"\b(?:a|an|the)\s+(?:zero|nonzero|positive|negative|unit)\s+value\s+of\b"
    for match in re.finditer(pattern, document.prose_mask(), re.I):
        yield make(document, "wordy-math-condition", match.start(),
                   "write the condition on the expression, for example 'When $H(x)=0$'")


manual(
    id="introduce-constructed-objects",
    section="Write like a human",
    summary="Introduce constructed objects explicitly and distinguish them from supplied inputs.",
    detail=(
        "Use `Let` or `Define` when first introducing a graph, a vertex, a "
        "function, or a parameter. State which graph contains a vertex and "
        "give a function's domain and codomain when needed. Reserve `given` "
        "and `supplied` for actual inputs or hypotheses. For example, write "
        "`Define P and S by ...`, not `The supplied pointer circuits have "
        "the following form ...` when constructing them for the first time."
    ),
)

manual(
    id="concrete-technical-qualifiers",
    section="Write like a human",
    summary="State the mathematical distinction instead of adding a vague qualifier.",
    detail=(
        "A `numerical exponential-time hypothesis` needs an actual time "
        "bound and quantifiers. State them if needed, or omit the aside. "
        "Use a citation to identify a published hypothesis instead of "
        "calling it `printed`. Words such as `fixed` and `specified` must "
        "identify a relevant dependence or choice. Do not treat these "
        "words as a blacklist; their mathematical role requires review."
    ),
)
