"""Tell new violations apart from ones that were already in the file.

A paper written before these rules existed can carry hundreds of findings.
Reporting all of them when an agent edits one line is useless, so the hook
compares against a baseline and speaks up only about what the edit added.

Matching is by rule and by the text of the offending line, not by line
number, so inserting a paragraph does not make every later finding look new.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from pathlib import Path

from .document import Document
from .rule import Violation

WHITESPACE_RE = re.compile(r"\s+")
GIT_TIMEOUT = 5


def _git(args: list[str], cwd: Path) -> str | None:
    try:
        done = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=GIT_TIMEOUT
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def git_baseline(path: Path, ref: str = "HEAD") -> Document | None:
    """The committed version of the file, or None if git does not know it."""
    directory = path.parent if path.parent.exists() else Path.cwd()
    root = _git(["rev-parse", "--show-toplevel"], directory)
    if not root:
        return None
    try:
        relative = path.resolve().relative_to(Path(root.strip()))
    except ValueError:
        return None
    text = _git(["show", f"{ref}:{relative.as_posix()}"], directory)
    return None if text is None else Document(str(path), text)


def signature(violation: Violation, document: Document) -> tuple[str, str]:
    """What makes two findings "the same" across edits."""
    index = violation.line - 1
    line = document.lines[index] if 0 <= index < len(document.lines) else ""
    return violation.rule_id, WHITESPACE_RE.sub(" ", line).strip()


def new_violations(
    current: Document,
    current_violations: list[Violation],
    baseline: Document | None,
    baseline_violations: list[Violation],
) -> list[Violation]:
    """The subset of `current_violations` that the baseline did not have.

    With no baseline every finding is new, which is the right answer for a
    file that was just created.
    """
    if baseline is None:
        return list(current_violations)
    budget = Counter(signature(v, baseline) for v in baseline_violations)
    fresh = []
    for violation in current_violations:
        key = signature(violation, current)
        if budget.get(key):
            budget[key] -= 1
            continue
        fresh.append(violation)
    return fresh
