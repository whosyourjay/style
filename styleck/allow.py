"""Written-down exceptions to a rule.

No rule carries a built-in escape hatch. A paper that needs one records it in
a ``.styleck-allow`` file, which loads like ``.styleck-terms``: a
source-specific ``name.styleck-allow`` extends the nearest project list.

A line beginning with ``#`` is a comment. Every other line names a rule and,
optionally, text from the line it covers::

    eq-needs-align: I(X^n;Y)+1

A rule id on its own exempts the whole file. The anchored form stops applying
once the line it names is rewritten.
"""

from __future__ import annotations

from pathlib import Path

from .config import config_chain

SUFFIX = ".styleck-allow"


def allowances(source_path: str) -> frozenset[tuple[str, str]]:
    """The (rule id, anchor) pairs excused for ``source_path``.

    An empty anchor exempts every finding of that rule in the file.
    """
    found: set[tuple[str, str]] = set()
    for config in config_chain(source_path, SUFFIX):
        found.update(_read_list(config))
    return frozenset(found)


def filter_allowed(document, violations: list) -> list:
    """Drop the findings an exception list excuses."""
    rules = allowances(document.path)
    if not rules:
        return list(violations)
    return [v for v in violations if not _excused(v, document, rules)]


def _excused(violation, document, rules: frozenset[tuple[str, str]]) -> bool:
    index = violation.line - 1
    line = document.lines[index] if 0 <= index < len(document.lines) else ""
    text = " ".join(line.split())
    return any(
        rule_id == violation.rule_id and (not anchor or anchor in text)
        for rule_id, anchor in rules
    )


def _read_list(path: Path) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        rule_id, _, anchor = line.partition(":")
        found.add((rule_id.strip(), " ".join(anchor.split())))
    return found
