#!/usr/bin/env python3
"""Source and optional post-build PDF lint for lecture books.

The rule catalog and rationale live in docs/books.md. Suppress a violation
by appending '% ok: E102' (comma-separate several ids) to the line.

Usage: styleck --book PATH             lint a lecture book
       styleck --book PATH --orphans   include the diagram-orphan audit
       python3 -m styleck.book --list  show the book-rule aliases
       styleck --pdf BOOK.pdf         check rendered theorem-box splits
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from .document import Document
from .rule import REGISTRY, check_document

ROOT = Path.cwd()

# Rule scopes, relative to the repo root.  lemmas/ is generated and
# files starting with '_' are scratch, so both stay out.
STYLE_GLOBS = ["lectures/*.tex"]
HYGIENE_GLOBS = ["lectures/*.tex", "diagrams/*.tex"]
XREF_GLOBS = ["book.tex", "lectures/*.tex", "diagrams/*.tex", "templates/*.tex"]
BIB_FILE = "references.bib"

STYLE_RULE_IDS = {
    "E102": "eq-trailing-punct",
    "E103": "eq-needs-align",
    "E105": "heading-case",
    "E107": "math-ellipsis",
    "E108": "math-fraction",
}

RULES = {
    **{legacy: REGISTRY[rule].summary for legacy, rule in STYLE_RULE_IDS.items()},
    "E106": "section spans should be 1 to 5 pages in the table of contents",
    "E201": "preamble-only command in a body file",
    "E202": "\\input target does not exist",
    "E203": "diagram file is never \\input",
    "E204": "unknown \\cite key",
    "E205": "duplicate bib key",
    "E301": "duplicate \\label",
    "E302": "unresolved \\ref",
    "E401": "suspicious theorem-box page split in a compiled PDF",
    "E402": "open theorem-box border has no unambiguous continuation",
}


# ---------------------------------------------------------------- text utils

def strip_comment(line: str) -> str:
    """Text before the first unescaped %.  Escaped pairs like \\% survive."""
    out = []
    i = 0
    while i < len(line):
        c = line[i]
        if c == "\\" and i + 1 < len(line):
            out.append(line[i : i + 2])
            i += 2
            continue
        if c == "%":
            break
        out.append(c)
        i += 1
    return "".join(out)


SUPPRESS_RE = re.compile(r"ok:\s*(E\d+(?:\s*,\s*E\d+)*)")


def suppressed_rules(line: str) -> set[str]:
    """Rule ids named by an 'ok: E123' marker in the comment part of a line."""
    comment = line[len(strip_comment(line)):]
    m = SUPPRESS_RE.search(comment)
    if not m:
        return set()
    return {r.strip() for r in m.group(1).split(",")}


def apply_suppressions(text: str, violations: list) -> list:
    """Drop (line, rule, msg) violations whose line carries an ok-marker."""
    lines = text.split("\n")
    out = []
    for lineno, rule, msg in violations:
        if 1 <= lineno <= len(lines) and rule in suppressed_rules(lines[lineno - 1]):
            continue
        out.append((lineno, rule, msg))
    return out


# ------------------------------------------------------- shared writing rules

def _writing_violations(text: str, legacy_id: str) -> list:
    rule = REGISTRY[STYLE_RULE_IDS[legacy_id]]
    return [(v.line, legacy_id, v.message)
            for v in rule.check(Document("chapter.tex", text))]


def check_display_punctuation(text: str) -> list:
    return _writing_violations(text, "E102")


def check_multi_relation_display(text: str) -> list:
    return _writing_violations(text, "E103")


def check_title_case(text: str) -> list:
    return _writing_violations(text, "E105")


def check_ellipsis(text: str) -> list:
    return _writing_violations(text, "E107")


def check_display_fractions(text: str) -> list:
    return _writing_violations(text, "E108")


TOC_RE = re.compile(
    r"\\contentsline\s*\{section\}.*?\{(\d+)\}(?:\{[^}]*\})?\s*%?\s*$",
)


def check_toc_section_pages(toc_text: str) -> list:
    """E106: adjacent TOC sections should start 1 to 5 pages apart."""
    pages = [(lineno, int(m.group(1)))
             for lineno, line in enumerate(toc_text.split("\n"), start=1)
             for m in [TOC_RE.search(line)] if m]
    out = []
    for (lineno, page), (_, next_page) in zip(pages, pages[1:]):
        gap = next_page - page
        if gap < 1:
            out.append((lineno, "E106",
                        f"next section starts on same page {page}"))
        elif gap > 5:
            out.append((lineno, "E106",
                        f"section spans {gap} pages before next section"))
    return out


PREAMBLE_ONLY_RE = re.compile(
    r"\\(?:documentclass|usepackage|DeclareMathOperator\*?)\b"
    r"|\\(?:begin|end)\{document\}"
)


def check_preamble_commands(text: str) -> list:
    """E201: preamble-only commands break the book build when \\input mid-document."""
    out = []
    for lineno, raw in enumerate(text.split("\n"), start=1):
        m = PREAMBLE_ONLY_RE.search(strip_comment(raw))
        if m:
            out.append((lineno, "E201",
                        f"preamble-only command {m.group(0)} in a body file"))
    return out


# All syntaxes that pull in another tex file.  Group 1 is the target path:
# \input, \include, \lectureinput, \sideinput[lines]{r}{0.34}{path}, and
# \begin{sidepar}[c]{r}{0.34}{path}.
INPUT_RES = [
    re.compile(r"\\(?:input|include|lectureinput)\s*\{([^}]*)\}"),
    re.compile(r"\\sideinput(?:\[[^\]]*\])?\{[^}]*\}\{[^}]*\}\{([^}]*)\}"),
    re.compile(r"\\begin\{sidepar\}(?:\[[^\]]*\])?\{[^}]*\}\{[^}]*\}\{([^}]*)\}"),
]


def input_targets(line: str) -> list:
    """Targets of every file-inclusion command on the line."""
    return [m.group(1) for rx in INPUT_RES for m in rx.finditer(line)]


def _tex_name(target: str) -> str:
    target = target.strip()
    return target if target.endswith(".tex") else target + ".tex"


def check_input_targets(text: str, exists) -> list:
    """E202: every \\input target resolves.  `exists` maps path string to bool."""
    out = []
    for lineno, raw in enumerate(text.split("\n"), start=1):
        for target in input_targets(strip_comment(raw)):
            if not exists(_tex_name(target)):
                out.append((lineno, "E202",
                            f"\\input target '{target.strip()}' not found"))
    return out


# ------------------------------------------------------------- project rules
# These take {relative path: text} so tests can pass explicit dicts.

def check_orphan_diagrams(files: dict) -> list:
    """E203: diagrams nothing references.  Commented \\input lines count as
    references, so a deliberately parked diagram stays alive."""
    referenced = set()
    for text in files.values():
        for target in input_targets(text):
            referenced.add(_tex_name(target))
    out = []
    for path in files:
        if path.startswith("diagrams/") and path not in referenced:
            out.append((path, 1, "E203", "diagram is not \\input anywhere"))
    return out


BIB_KEY_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s{}]+)\s*,")
CITE_RE = re.compile(r"\\(?:no)?cite[tp]?\*?(?:\[[^\]]*\])?\{([^}]*)\}")


def bib_keys(bib_text: str) -> list:
    return [key for kind, key in BIB_KEY_RE.findall(bib_text)
            if kind.lower() not in ("string", "comment", "preamble")]


def check_citations(files: dict, bib_text: str) -> list:
    """E204: every \\cite key appears in the bibliography."""
    keys = set(bib_keys(bib_text))
    out = []
    for path, text in files.items():
        for lineno, raw in enumerate(text.split("\n"), start=1):
            for m in CITE_RE.finditer(strip_comment(raw)):
                for key in (k.strip() for k in m.group(1).split(",")):
                    if key and key not in keys:
                        out.append((path, lineno, "E204",
                                    f"unknown citation key '{key}'"))
    return out


def check_bib_duplicates(bib_text: str) -> list:
    """E205: duplicate keys in references.bib."""
    seen = set()
    out = []
    for lineno, raw in enumerate(bib_text.split("\n"), start=1):
        for kind, key in BIB_KEY_RE.findall(raw):
            if kind.lower() in ("string", "comment", "preamble"):
                continue
            if key in seen:
                out.append((BIB_FILE, lineno, "E205", f"duplicate bib key '{key}'"))
            seen.add(key)
    return out


LABEL_RE = re.compile(r"\\label\{([^}]*)\}")
REF_RE = re.compile(r"\\(?:ref|eqref|autoref|pageref|[cC]ref)\*?\{([^}]*)\}")


def included_files(files: dict, start: str = "book.tex") -> set:
    """Files reachable from book.tex via uncommented \\input."""
    reach: set[str] = set()
    frontier = [start]
    while frontier:
        path = frontier.pop()
        if path in reach or path not in files:
            continue
        reach.add(path)
        for raw in files[path].split("\n"):
            for target in input_targets(strip_comment(raw)):
                frontier.append(_tex_name(target))
    return reach


def collect_labels(files: dict) -> dict:
    labels: dict[str, list] = {}
    for path, text in files.items():
        for lineno, raw in enumerate(text.split("\n"), start=1):
            for m in LABEL_RE.finditer(strip_comment(raw)):
                if "#" not in m.group(1):  # skip macro definitions
                    labels.setdefault(m.group(1), []).append((path, lineno))
    return labels


def check_duplicate_labels(files: dict, included: set = None) -> list:
    """E301: a duplicate label breaks every \\ref to it.  Cross-file
    duplicates only count when both files are part of the book; a
    variant chapter kept next to the live one is fine."""
    if included is None:
        included = set(files)
    out = []
    for name, sites in collect_labels(files).items():
        for i, (path, lineno) in enumerate(sites[1:], start=1):
            prior = sites[:i]
            same_file = any(p == path for p, _ in prior)
            both_in = path in included and any(p in included for p, _ in prior)
            if same_file or both_in:
                out.append((path, lineno, "E301", f"duplicate label '{name}'"))
    return out


def check_unresolved_refs(files: dict, included: set = None) -> list:
    """E302: every reference resolves.  References in book files must
    resolve within the book; variant files may reference any label."""
    all_labels = set(collect_labels(files))
    if included is None:
        included, book_labels = set(files), all_labels
    else:
        book_labels = set(collect_labels(
            {p: t for p, t in files.items() if p in included}))
    out = []
    for path, text in files.items():
        pool = book_labels if path in included else all_labels
        for lineno, raw in enumerate(text.split("\n"), start=1):
            for m in REF_RE.finditer(strip_comment(raw)):
                for key in (k.strip() for k in m.group(1).split(",")):
                    if key and "#" not in key and key not in pool:
                        out.append((path, lineno, "E302",
                                    f"unresolved reference '{key}'"))
    return out


# --------------------------------------------------------------------- runner

def gather(root: Path, globs: list) -> dict:
    files = {}
    for pattern in globs:
        for p in sorted(root.glob(pattern)):
            if p.name.startswith("_"):
                continue
            files[str(p.relative_to(root))] = p.read_text(
                encoding="utf-8", errors="replace")
    return files


def lint_repo(root: Path, include_orphans: bool = False, extra_checks: tuple = ()) -> list:
    """All violations as (path, line, rule, message), suppressions applied."""
    xref = gather(root, XREF_GLOBS)
    bib_path = root / BIB_FILE
    bib = bib_path.read_text(encoding="utf-8", errors="replace") \
        if bib_path.exists() else ""

    def exists(name: str) -> bool:
        return (root / name).exists()

    raw = []
    legacy_ids = {rule: legacy for legacy, rule in STYLE_RULE_IDS.items()}
    for path, text in gather(root, STYLE_GLOBS).items():
        document = Document(str(root / path), text)
        checks = [(v.line, legacy_ids[v.rule_id], v.message)
                  for v in check_document(document, frozenset(legacy_ids))]
        for check in extra_checks:
            checks.extend(check(text))
        raw += [(path, *v) for v in checks]
    for path, text in gather(root, HYGIENE_GLOBS).items():
        checks = check_preamble_commands(text) + check_input_targets(text, exists)
        raw += [(path, *v) for v in checks]
    included = included_files(xref)
    if include_orphans:
        raw += check_orphan_diagrams(xref)
    raw += check_citations(xref, bib)
    raw += check_bib_duplicates(bib)
    raw += check_duplicate_labels(xref, included)
    raw += check_unresolved_refs(xref, included)
    toc_path = root / "book.toc"
    toc = ""
    if toc_path.exists():
        toc = toc_path.read_text(encoding="utf-8", errors="replace")
        raw += [("book.toc", *v) for v in check_toc_section_pages(toc)]

    texts = {**xref, BIB_FILE: bib}
    if toc:
        texts["book.toc"] = toc
    out = []
    for path, lineno, rule, msg in raw:
        kept = apply_suppressions(texts.get(path, ""), [(lineno, rule, msg)])
        out += [(path, *v) for v in kept]
    return sorted(out)


def main(argv: list, root: Path | None = None, *,
         extra_checks: tuple = (), extra_rules: dict | None = None) -> int:
    if argv and argv[0] == "--pdf":
        from .book_pdf import main as pdf_main
        return pdf_main(argv[1:])
    if "--list" in argv:
        for rule, desc in sorted({**RULES, **(extra_rules or {})}.items()):
            print(f"{rule}  {desc}")
        return 0
    include_orphans = "--orphans" in argv
    unknown = [arg for arg in argv if arg not in {"--orphans"}]
    if unknown:
        print(f"unknown option: {unknown[0]}", file=sys.stderr)
        return 2
    root = root if root is not None else ROOT
    if not (root / "book.tex").is_file():
        print(f"{root}: book.tex not found", file=sys.stderr)
        return 2
    violations = lint_repo(root, include_orphans=include_orphans,
                           extra_checks=extra_checks)
    counts: dict[str, int] = {}
    for path, lineno, rule, msg in violations:
        counts[rule] = counts.get(rule, 0) + 1
        print(f"{path}:{lineno}: {rule} {msg}")
    if violations:
        summary = "  ".join(f"{r}:{n}" for r, n in sorted(counts.items()))
        print(f"\n{len(violations)} violations   {summary}")
        return 1
    print("clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
