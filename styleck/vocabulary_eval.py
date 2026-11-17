"""Evaluate terminology findings on documents and paired definition controls."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from .document import Document
from .linguistics import analyze, phrase_key, prose_text, tokens
from .vocabulary import Evidence, declared, definitions, findings
from .vocabulary_build import expanded, source_text
from .math_dictionary import modifier_heads, senses, usage
from .word_senses import best_sense


# Each pair changes the supplied definition, not the mathematical use.
CONTROLS = (
    ("heavy vertex", "Every heavy vertex of $G$ meets another vertex of the graph.",
     "A vertex is heavy if its degree exceeds $k$."),
    ("fragile component", "Each fragile component of $G$ contains a vertex of the graph.",
     "A component is fragile if deleting one vertex disconnects it."),
    ("active clause", "Each active clause of $F$ contains a variable of the formula.",
     "A clause is active if it contains an unassigned variable."),
    ("good partition", "Each good partition of $V$ separates two vertices of the graph.",
     "A partition is good if every part contains at least $k$ vertices."),
    ("bud", "Each bud of $G$ contains two vertices of the graph.",
     "A bud is a connected subgraph with exactly one boundary vertex."),
    ("socket", "Each socket of $G$ contains two vertices of the graph.",
     "A socket is an ordered pair of distinct vertices of the graph."),
    ("shadow matching", "Each shadow matching of $G$ selects edges of the graph.",
     "A shadow matching is a matching whose endpoints all lie in $U$."),
    ("charged occurrence", "Each charged occurrence of $x$ belongs to a clause of the formula.",
     "An occurrence is charged if its variable has already been assigned."),
)

ORDINARY = (
    "The proof makes heavy use of exhaustive search. We construct a nonnegative integer $k$.",
    "The budget $k$ limits the number of chosen sets. The input length determines the running time.",
    "Construct $A$ from $B$. The function $h$ is nondecreasing in $n$.",
    "We select distinct sets from the empty universe. The output parameter is a nonnegative integer.",
    "A weight-$k$ truth assignment sets exactly $k$ variables to true. We count these assignments.",
    "The reduction returns a yes- or no-instance. The source and target are decision problems.",
)


def check(text: str, path: str):
    document = Document(path, text)
    return [{"line": document.text.count("\n", 0, offset) + 1,
             "phrase": quoted, "uses": count, "reason": reason}
            for offset, quoted, count, reason in findings(document)]


def controls():
    cases = []
    for term, sentence, definition in CONTROLS:
        body = (sentence + " ") * 4
        variants = {"undefined": body, "prose definition": definition + " " + body,
                    "marked definition": f"A \\deftext{{{term}}} has the stated property. " + body}
        for variant, text in variants.items():
            text = "\\begin{document}\n" + text + "\n\\end{document}"
            found = check(text, "/private/tmp/styleck-evaluation/control.tex")
            expected = {phrase_key(term)} if variant == "undefined" else set()
            observed = {phrase_key(item["phrase"]) for item in found}
            cases.append({"case": term + ": " + variant, "pass": observed == expected,
                          "expected": sorted(expected), "observed": sorted(observed)})
    for index, sentence in enumerate(ORDINARY):
        found = check("\\begin{document}\n" + (sentence + " ") * 4 + "\n\\end{document}",
                      "/private/tmp/styleck-evaluation/ordinary.tex")
        cases.append({"case": f"ordinary {index + 1}", "pass": not found,
                      "expected": [], "observed": [item["phrase"] for item in found]})
    return cases


def document_report(path: Path, include_inputs: bool):
    path = path.resolve()
    text = expanded(path, path.parent, set()) if include_inputs else source_text(path)
    with_list = check(text, str(path))
    with patch("styleck.vocabulary.background_terms", return_value=frozenset()):
        without_list = check(text, str(path))
    return {"path": str(path), "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "includes_expanded": include_inputs,
            "with_background": with_list, "without_background": without_list}


def control_metrics(cases):
    metrics = {"exact_hits": 0, "missed_terms": 0, "false_alarms": 0, "boundary_errors": 0}
    for case in cases:
        expected, observed = set(case["expected"]), set(case["observed"])
        exact = expected & observed
        metrics["exact_hits"] += len(exact)
        missing, extra = expected - exact, observed - exact
        for wanted in sorted(missing):
            fragments = [actual for actual in extra if (" " + actual + " ") in (" " + wanted + " ")
                         or (" " + wanted + " ") in (" " + actual + " ")]
            if fragments:
                extra.remove(max(fragments, key=len))
                metrics["boundary_errors"] += 1
            else:
                metrics["missed_terms"] += 1
        metrics["false_alarms"] += len(extra)
    return metrics


def inspect_text(sentence):
    document = Document("/private/tmp/styleck-evaluation/control.tex",
                        "\\begin{document}\n" + (sentence + " ") * 4 + "\n\\end{document}")
    prose, candidates = analyze(document)
    evidence = Evidence(document, candidates)
    tagged = tokens(prose, document.spans_of("inline", "display"))
    print([(item.text, item.tag, item.pos, item.dependency) for item in tagged if item.sentence == 0])
    for key in sorted({item.key for item in candidates}):
        uses = [item for item in candidates if item.key == key]
        context = set().union(*(item.context for item in uses))
        print(key, "count=", len(uses), "declared=", declared(key, definitions(document)),
              "standard=", evidence.standard(key), "uses=", usage(key), "sense=", best_sense(key, context),
              "reason=", evidence.reason(uses))
        if " " in key:
            print("  modifier sense:", best_sense(key.split()[0], context | {uses[0].head}))


def sense_summary():
    for term, sentence, _ in CONTROLS:
        _, candidates = analyze(Document("control.tex", sentence))
        uses = [item for item in candidates if item.key == term]
        if not uses:
            continue
        context = set().union(*(item.context for item in uses))
        word = term.split()[0]
        if " " in term:
            context.add(uses[0].head)
        general = best_sense(word, context)[0]
        mathematical = best_sense(word, context, mathematical=True)[0]
        print(f"{term}: ordinary={general:.3f}, mathematical={mathematical:.3f}, heads={len(modifier_heads(word))}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--controls", action="store_true")
    parser.add_argument("--inputs", action="store_true", help="include the document's input files")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--inspect-control", choices=[case[0] for case in CONTROLS])
    parser.add_argument("--inspect-text")
    parser.add_argument("--sense-summary", action="store_true")
    args = parser.parse_args()
    if args.sense_summary:
        sense_summary()
        return
    if args.inspect_control:
        inspect_text(next(case[1] for case in CONTROLS if case[0] == args.inspect_control))
        return
    if args.inspect_text:
        inspect_text(args.inspect_text)
        return
    report = {"documents": [document_report(path, args.inputs) for path in args.paths]}
    if args.controls:
        report["controls"] = controls()
        report["metrics"] = control_metrics(report["controls"])
    if args.json:
        print(json.dumps(report, indent=2))
        return
    for item in report["documents"]:
        print(f"{item['path']}: {len(item['with_background'])} with background; "
              f"{len(item['without_background'])} without")
        for finding in item["without_background"]:
            print(f"  {finding['line']}: {finding['phrase']}")
    cases = report.get("controls", [])
    if cases:
        print(f"Controls: {sum(case['pass'] for case in cases)}/{len(cases)} passed")
        print("  " + "; ".join(f"{name}: {count}" for name, count in report["metrics"].items()))
        for case in cases:
            if not case["pass"]:
                print(f"  {case['case']}: expected {case['expected']}; observed {case['observed']}")


if __name__ == "__main__":
    main()
