"""Writing rules no checker can enforce.

These live in the registry so that one command still generates the whole
style guide. Their wording matters more than the others': an agent has
nothing but the text to go on.
"""

from __future__ import annotations

from .rule import manual

manual(
    id="diagram-visual",
    section="Diagrams",
    summary="Draw the object, do not describe it in boxes.",
    detail=(
        "Boxes holding equations or lemma names with arrows between them are a "
        "weak diagram. A small caption is fine."
    ),
)

manual(
    id="diagram-labels",
    section="Diagrams",
    summary="Do not re-explain a label the surrounding text already defines.",
)

manual(
    id="diagram-variables",
    section="Diagrams",
    summary="Define diagram labels as variables in the main .tex.",
    detail="Editing the label then happens in one place, next to the prose.",
)

manual(
    id="diagram-as-code",
    section="Diagrams",
    summary="Treat a diagram as code: loops, functions, derived coordinates.",
    detail=(
        "Some coordinates have to be magic numbers, but derive the rest from a "
        "few anchors. Attach labels to objects instead of to coordinates, and "
        "hardcode a nudge only when a label overlaps."
    ),
)

manual(
    id="jargon-the-x",
    section="Write like a human",
    summary='Do not write "the X" for jargon X the paper has not defined.',
    detail=(
        "Define technical vocabulary at its first substantive use. Make the "
        "referent and quantifier explicit: if `the probabilities` means all "
        "action probabilities, say so."
    ),
)

manual(
    id="one-noun-one-concept",
    section="Write like a human",
    summary="Give each technical concept one noun, and each noun one role.",
    detail=(
        "Do not alternate among near-synonyms such as `outcome`, `action`, and "
        "`label`. If they denote different objects, define the distinction; if "
        "not, choose one. Do not rename an ordinary probability a `hazard`, or "
        "an inserted word a `payload`, unless the new term does mathematical "
        "work."
    ),
)

manual(
    id="active-voice",
    section="Write like a human",
    summary="Put the named actor before the verb.",
    detail=(
        "Give an implicit actor a name: \"we\", \"the reduction\", \"the "
        "schedule\". Let the object act — a partition covers, a schedule "
        "meets a deadline. Expand a passive participial modifier into a clause."
    ),
    bad="The deadline is met by the schedule constructed above.",
    good="The schedule above meets every deadline.",
)

manual(
    id="prose-between-blocks",
    section="LaTeX layout",
    summary="Alternate blocks of text and blocks of equations.",
    detail=(
        "When a stub of text falls between two displays, either say more, fold "
        "the stub into the align as inline text, or merge the two displays. If "
        "the prose states a reusable claim, promote it to a lemma or "
        "proposition; if the cluster introduces notation, use a definition."
    ),
)

manual(
    id="formalize-reusable-claims",
    section="LaTeX layout",
    summary="Put reusable mathematical claims in named environments.",
    detail=(
        "A claim that carries part of the proof, is cited later, or introduces "
        "several related quantities belongs in a lemma, proposition, or "
        "definition with a label. Do not leave it as an unnumbered assertion "
        "between displays."
    ),
)
