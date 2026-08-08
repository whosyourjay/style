#!/usr/bin/env python3
"""Check the staged versions of papers before Git creates a commit."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

STYLE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STYLE_ROOT))

from styleck import check_document  # noqa: E402
from styleck.baseline import new_violations  # noqa: E402
from styleck.document import Document  # noqa: E402
from styleck.rule import ERROR, MANUAL  # noqa: E402

CHECKED = {".tex", ".sty", ".cls", ".tikz"}
GIT_TIMEOUT = 10


def _git(args: list[str], cwd: Path) -> bytes | None:
    try:
        done = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, timeout=GIT_TIMEOUT
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def _root(cwd: Path) -> Path | None:
    raw = _git(["rev-parse", "--show-toplevel"], cwd)
    if raw is None:
        return None
    return Path(os.fsdecode(raw).strip())


def _staged_paths(root: Path) -> list[Path]:
    raw = _git(
        ["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"], root
    )
    if raw is None:
        return []
    return [
        Path(os.fsdecode(name))
        for name in raw.split(b"\0")
        if name and Path(os.fsdecode(name)).suffix in CHECKED
    ]


def _blob(root: Path, spec: str) -> str | None:
    raw = _git(["show", spec], root)
    return None if raw is None else raw.decode("utf-8", errors="replace")


def staged_findings(root: Path) -> list:
    """Return only findings introduced by the versions in Git's index."""
    violations = []
    for path in _staged_paths(root):
        staged_text = _blob(root, f":0:{path.as_posix()}")
        if staged_text is None:
            continue
        current = Document(path.as_posix(), staged_text)
        found = [v for v in check_document(current) if v.severity != MANUAL]
        baseline_text = _blob(root, f"HEAD:{path.as_posix()}")
        baseline = (
            None
            if baseline_text is None
            else Document(path.as_posix(), baseline_text)
        )
        prior = (
            []
            if baseline is None
            else [v for v in check_document(baseline) if v.severity != MANUAL]
        )
        violations.extend(new_violations(current, found, baseline, prior))
    return violations


def run(cwd: Path | None = None) -> int:
    root = _root(cwd or Path.cwd())
    if root is None:
        return 0
    violations = staged_findings(root)
    if not violations:
        return 0

    errors = [v for v in violations if v.severity == ERROR]
    warnings = [v for v in violations if v.severity != ERROR]
    if errors:
        sys.stderr.write(
            f"styleck: staged changes introduced {len(errors)} style error(s); "
            "commit stopped.\n"
        )
    elif warnings:
        sys.stderr.write(
            f"styleck: staged changes introduced {len(warnings)} style warning(s); "
            "commit continues.\n"
        )
    for violation in violations:
        sys.stderr.write("  " + violation.format() + "\n")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(run())
