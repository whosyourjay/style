"""Write the generated style guide into the repos that need it.

The point is that no repo keeps its own copy of the rules. Each `claude.md`
is regenerated, so one edit to the rules reaches every repo and no copy can drift.
"""

from __future__ import annotations

from pathlib import Path

from .docgen import BANNER, render

TARGET_NAME = "claude.md"


def is_generated(path: Path) -> bool:
    if not path.is_file():
        return False
    return BANNER in path.read_text(encoding="utf-8", errors="replace")


def sync(targets: list[Path], force: bool = False) -> list[tuple[Path, str]]:
    """Write the guide into each target directory.

    Returns one (path, outcome) pair per target. A hand-written file is left
    alone unless `force` is set, so nobody loses notes they meant to keep.
    """
    body = render()
    results = []
    for directory in targets:
        path = directory / TARGET_NAME
        if path.exists() and not is_generated(path) and not force:
            results.append((path, "skipped (hand-written; pass --force to replace)"))
            continue
        if path.exists() and path.read_text(encoding="utf-8", errors="replace") == body:
            results.append((path, "unchanged"))
            continue
        outcome = "updated" if path.exists() else "created"
        path.write_text(body, encoding="utf-8")
        results.append((path, outcome))
    return results


def find_targets(root: Path) -> list[Path]:
    """Directories under `root` that already carry a claude.md."""
    found = {path.parent for path in root.glob(f"*/{TARGET_NAME}")}
    if (root / TARGET_NAME).exists():
        found.add(root)
    return sorted(found)
