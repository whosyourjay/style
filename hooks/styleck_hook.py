#!/usr/bin/env python3
"""PostToolUse hook that enforces the writing rules.

Wire it to Edit, Write, and MultiEdit. After the agent touches a paper the
hook checks it and reports what the edit introduced.

Only what the edit added is reported. A paper written before these rules
existed keeps its old findings; the hook compares against the committed
version and stays quiet about anything that was already there.

Errors block: exit code 2 sends stderr back to the agent, which has to fix
them before moving on. Warnings only inform: they ride back as context the
agent can weigh, and never interrupt the run.

Nothing here runs during a LaTeX build and nothing here fails a build.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from styleck import check_document  # noqa: E402
from styleck.baseline import git_baseline, new_violations  # noqa: E402
from styleck.document import Document  # noqa: E402
from styleck.fixers import apply_fixes  # noqa: E402
from styleck.rule import ERROR, MANUAL  # noqa: E402

CHECKED = {".tex", ".sty", ".cls", ".tikz"}
BLOCK_EXIT = 2
LAUNCHER = Path(__file__).resolve().parent.parent / "bin" / "styleck"


def _payload() -> dict:
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}


def _target(payload: dict) -> Path | None:
    raw = (payload.get("tool_input") or {}).get("file_path")
    return Path(raw) if raw else None


def _findings(path: Path, text: str) -> list:
    document = Document(str(path), text)
    current = [v for v in check_document(document) if v.severity != MANUAL]
    if not current:
        return []
    baseline = git_baseline(path)
    prior = [] if baseline is None else [
        v for v in check_document(baseline) if v.severity != MANUAL
    ]
    return new_violations(document, current, baseline, prior)


def _autofix(path: Path, text: str) -> tuple[str, list[str]]:
    """Repair mechanical issues. Off unless the repo opts in.

    A legacy paper can hold hundreds of findings, and rewriting all of them
    because the agent touched one line would bury the real change.
    """
    if os.environ.get("STYLECK_AUTOFIX", "0") != "1":
        return text, []
    fixed = apply_fixes(str(path), text)
    if fixed == text:
        return text, []
    before = {v.rule_id for v in _findings(path, text)}
    after = {v.rule_id for v in _findings(path, fixed)}
    path.write_text(fixed, encoding="utf-8")
    return fixed, sorted(before - after)


def check(payload: dict) -> int:
    path = _target(payload)
    if path is None or path.suffix not in CHECKED or not path.is_file():
        return 0
    text, repaired = _autofix(path, path.read_text(encoding="utf-8", errors="replace"))
    violations = _findings(path, text)
    errors = [v for v in violations if v.severity == ERROR]
    warnings = [v for v in violations if v.severity != ERROR]
    if not violations and not repaired:
        return 0

    preamble = []
    if repaired:
        preamble.append(
            f"styleck repaired {path.name} for you ({', '.join(repaired)}). "
            "Re-read the file before editing it again."
        )
    if errors:
        sys.stderr.write("\n".join(preamble + _block_text(path, errors, warnings)) + "\n")
        return BLOCK_EXIT
    _emit_context("\n".join(preamble + _advice_text(path, warnings)))
    return 0


def _block_text(path: Path, errors: list, warnings: list) -> list[str]:
    lines = [
        f"styleck: your edit to {path.name} introduced {len(errors)} style "
        "error(s). Fix them now."
    ]
    lines.extend("  " + v.format() for v in errors)
    if warnings:
        lines.append(f"Also {len(warnings)} warning(s), which are advice, not blockers:")
        lines.extend("  " + v.format() for v in warnings)
    lines.append(f"`{LAUNCHER} --docs` prints the rule text for any id above.")
    return lines


def _advice_text(path: Path, warnings: list) -> list[str]:
    if not warnings:
        return []
    lines = [
        f"styleck notes {len(warnings)} style warning(s) from your edit to "
        f"{path.name}. These do not block you. Apply the ones that improve the "
        "writing and say so briefly if you leave one alone:"
    ]
    lines.extend("  " + v.format() for v in warnings)
    return lines


def _emit_context(message: str) -> None:
    """Hand information to the agent without interrupting the run."""
    if not message.strip():
        return
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": message,
        }
    }
    sys.stdout.write(json.dumps(payload) + "\n")


if __name__ == "__main__":
    sys.exit(check(_payload()))
