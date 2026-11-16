# Lecture-book checks

The general writing rules live in the [shared guide](../claude.md), generated
from the rule registry. The book profile adds source, cross-reference, and
layout checks for projects with `book.tex`, `lectures/`, `diagrams/`,
`templates/`, and `references.bib`.

```sh
styleck --book ../tcs-courses
styleck --book ../tcs-courses --orphans
styleck --pdf ../tcs-courses/book2.pdf
```

Source checks return 1 on violations. `--orphans` additionally checks for
unused diagrams. Fraction, indexing, and heading rules also run with ordinary
`styleck paper.tex`. The book profile keeps its E-numbered diagnostics and
calls the same shared detectors; its implementation lives in `styleck/book.py`.

Suppress a deliberate exception by appending `% ok: E102` to the offending
line (comma-separate several ids: `% ok: E102, E103`).
Writing checks also honor `.styleck-allow` with the shared rule ids below.

## Checked rules

| ID   | Scope               | Rule |
|------|---------------------|------|
| E102 | lectures            | `eq-trailing-punct` |
| E103 | lectures            | `eq-needs-align`, including inline derivations |
| E105 | lectures            | `heading-case` |
| E106 | book.toc            | Adjacent section starts in the TOC differ by 1 to 5 pages |
| E107 | lectures            | `math-ellipsis` |
| E108 | lectures            | `math-fraction` |
| E201 | lectures, diagrams  | No preamble-only commands (`\usepackage`, `\documentclass`, `\DeclareMathOperator`, `\begin{document}`) in body files |
| E202 | lectures, diagrams  | Every `\input` target file exists |
| E203 | book-wide, opt-in   | Every `diagrams/*.tex` is `\input` somewhere; a commented-out `\input` counts as a keep-alive reference. Run with `--orphans` |
| E204 | book-wide           | Every `\cite` key exists in `references.bib` |
| E205 | references.bib      | No duplicate bibliography keys |
| E301 | book-wide           | No duplicate `\label`; cross-file duplicates only count when both files are reachable from `book.tex`, so a variant chapter (`...2.tex`) beside the live one is fine |
| E302 | book-wide           | Every `\ref`/`\eqref` resolves; references in book-reachable files must resolve within the book. Keys containing `#` (macro parameters) are ignored |

## Rendered box checks

The checker expects TikZ/mdframed named theorem boxes. A box that fits on one
page should stay together; a longer box can split.

After building, run the separate PDF mode (no compilation or source changes):

```sh
python3 -m pip install pdfplumber  # once
styleck --pdf book2.pdf
```

It reads the actual vector borders of the current `namedthmbox`/TikZ/mdframed
style. Messages give the theorem name and **physical PDF pages**, not printed
page numbers or source lines. Multiple PDFs can be passed in one invocation.
Exit codes are 0 for no findings, 1 for findings, and 2 for input/dependency
errors or no recognized boxes. Long, well-balanced splits are allowed.

| ID | Scope | Rule |
|----|-------|------|
| E401 | PDF, opt-in | A theorem box splits despite being short, leaves a tiny fragment, or breaks with substantial unused space below it |
| E402 | PDF, opt-in | An open theorem-box border has no unambiguous continuation on the next PDF page |

E401 is a review heuristic: it flags a split box whose fragments total at most
216 pt, a fragment at most 72 pt tall with fewer than three text rows, or a
split leaving at least 72 pt of blank space below it. Math scripts are grouped
with nearby rows; images and drawings below a box count as occupied space.
The blank-space test assumes the shared preamble's one-inch margins. E402
prevents an unrecognized continuation from silently passing.

Unframed statements/proofs and PDFs using a different frame style are outside
this check's scope. Source `% ok:` markers do not suppress PDF findings. The
geometry logic lives in `styleck/book_pdf.py`.

## Adding a rule

Add general writing rules to the registry as described in
[Developing styleck](development.md). Book-only structural checks belong in
`styleck/book.py`; PDF geometry checks belong in `styleck/book_pdf.py`.
A project's local entry point can supply extra checks for project-specific
conventions.

## Not covered yet

- Build tier: compile each chapter via `./build.sh`, grep the log for
  undefined references and overfull boxes.
- `E106` only runs when `book.toc` is present. The normal build script may
  clean it up after a successful build.
