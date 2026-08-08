#!/usr/bin/env python3
"""PostToolUse hook that enforces the writing rules.

Wire it to Edit, Write, and MultiEdit. After the agent touches a paper the
hook repairs what is mechanical, then reports whatever is left so the agent
has to deal with it before moving on.

Reads the hook payload as JSON on stdin. Exit code 2 sends stderr back to the
agent, which is what makes the feedback loop work.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from styleck import check_document  # noqa: E402
from styleck.document import Document  # noqa: E402
from styleck.fixers import apply_fixes  # noqa: E402
from styleck.rule import MANUAL  # noqa: E402

CHECKED = {".tex", ".sty", ".cls", ".tikz"}
BLOCK_EXIT = 2


def _payload() -> dict:
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}


def _target(payload: dict) -> Path | None:
    raw = (payload.get("tool_input") or {}).get("file_path")
    return Path(raw) if raw else None


def _autofix(path: Path, text: str) -> tuple[str, list[str]]:
    if os.environ.get("STYLECK_AUTOFIX", "1") == "0":
        return text, []
    fixed = apply_fixes(str(path), text)
    if fixed == text:
        return text, []
    before = {v.rule_id for v in check_document(Document(str(path), text))}
    after = {v.rule_id for v in check_document(Document(str(path), fixed))}
    path.write_text(fixed, encoding="utf-8")
    return fixed, sorted(before - after)


def check(payload: dict) -> int:
    path = _target(payload)
    if path is None or path.suffix not in CHECKED or not path.is_file():
        return 0
    text, repaired = _autofix(path, path.read_text(encoding="utf-8", errors="replace"))
    violations = [
        v for v in check_document(Document(str(path), text)) if v.severity != MANUAL
    ]
    if not violations and not repaired:
        return 0

    lines = []
    if repaired:
        lines.append(
            f"styleck repaired {path.name} for you ({', '.join(repaired)}). "
            "Re-read the file before editing it again."
        )
    if violations:
        lines.append(f"styleck found {len(violations)} issue(s) in {path.name}:")
        lines.extend("  " + v.format() for v in violations)
        lines.append(
            "Fix these now. `python -m styleck --docs` prints the rule text; "
            "`python -m styleck --rules <id> <file>` rechecks one rule."
        )
    sys.stderr.write("\n".join(lines) + "\n")
    return BLOCK_EXIT


if __name__ == "__main__":
    sys.exit(check(_payload()))
