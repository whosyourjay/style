"""Ordinary English and generic paper vocabulary.

``term-undeclared`` treats every other repeated word as project vocabulary
which the paper must either mark with ``\\term{...}`` or list in a
``.styleck-terms`` file.  Domain nouns stay out of this list on purpose: a
graph paper should declare ``vertex`` and ``clique`` once rather than have the
checker guess which fields they belong to.
"""

from __future__ import annotations

_WORDS = """
a able about above across add added after again against all almost along
already also although always among an and another any anything appear appears
apply are around as ask asked assume assumed at back bad be because become
becomes been before begin beginning behind being below best better between
beyond big both bring but by call called can cannot care carry carries case
cases certain change check choice choose chosen clear come common complete
completely condition consider consists contain contains continue correct cost
could count course cover create current cut deal define defined definition
depend depends describe detail did differ difference different direct
discussion do does doing done down draw drawn due during each early easy
either else empty end enough enter entire equal especially even ever every
everything exact exactly example except exist exists expect explain fact fall
false far few field figure fill final find finish first five fix fixed follow
follows for form four free from full further general get give given go good
great group had half half happen has have having he help hence her here high
his hold holds how however idea if important in include including increase
indeed index inside instead into introduce is it its itself join just keep
kept key kind know known large last late later leave led left length less let
level like likely limit line list little local long look low made main major
make makes many may mean means meet method might minor more moreover most move
much must my name natural near necessary need never new next no nor not note
nothing now number obtain obtained of off often old on once one only onto open
or order original other others otherwise our out output over own paper part
particular pass past per perhaps place play point poor position possible
prefer present previous primary problem proper property prove proved provide
provides public put question quite rather reach read real reason recall recent
receive reduce refer remain remains remove replace require required rest
result return right round rule run running said same satisfy say second see
seen send sequence serve set seven several shall she short should show shown
side simple since single six size small so solution solve some something
sometimes soon space special specific stand start state statement stay step
still stop strong such suffice sufficient suppose sure symbol table take taken
tell ten term test than that the their them themselves then there therefore
these they thing think third this those though three through thus time to
today together too total toward towards true try turn two under understand
unique until up upon us use used useful using usual usually value various very
via wait walk want was way we well were what when where whether which while
who whole whom whose why will with within without work would write written
wrong yet you your zero
piece pair copy row column member item record family collection sum unit
amount rate part place thing way point end top bottom middle left right
accept actual answer assign auxiliary contribute cover criterion delete depth
direction force handle inspection join label lie neither word
accept actual assign contribute cover delete direction force handle join lie
opposite pattern reject select separate supply unless valid
absolute arbitrary constant corresponding decidable decide distinct disjoint
element empty enumerate enumeration exactly external finite greatest hence
independent infinite integer internal intersection least linear machine matrix
maximum member minimum namely negative nonempty odd ordering pairwise
polynomial positive precisely prescribed relative respective search subset
superset triple union whenever workspace
algorithm analysis appendix argument assumption bound bounded claim
complexity computation conclusion construction corollary definition equation
example exercise figure formula function idea induction input instance lemma
notation observation output paragraph proof proposition question reference
remark result section sentence statement step subsection table theorem theory
"""

COMMON_WORDS = frozenset(_WORDS.split())

# Latin and Greek plurals which the ordinary -s rule cannot fold.
IRREGULAR_PLURALS = {
    "analyses": "analysis", "apices": "apex", "bases": "basis",
    "criteria": "criterion", "foci": "focus", "formulae": "formula",
    "hypotheses": "hypothesis", "indices": "index", "lemmata": "lemma",
    "loci": "locus", "matrices": "matrix", "maxima": "maximum",
    "minima": "minimum", "phenomena": "phenomenon", "radii": "radius",
    "simplices": "simplex", "theses": "thesis", "vertices": "vertex",
}
