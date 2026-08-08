"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import check_document
from .document import Document
from .docgen import render, render_summary
from .fixers import apply_fixes
from .rule import ERROR, MANUAL, REGISTRY
from .sync import find_targets, sync

CHECKED_SUFFIXES = (".tex", ".sty", ".cls", ".tikz", ".md", ".txt")


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="styleck", description=__doc__)
    parser.add_argument("paths", nargs="*", help="files or directories to check")
    parser.add_argument("--fix", action="store_true", help="repair what is mechanical")
    parser.add_argument("--json", action="store_true", help="machine readable output")
    parser.add_argument("--rules", help="comma separated rule ids to run")
    parser.add_argument("--docs", action="store_true", help="print the style guide")
    parser.add_argument("--summary", action="store_true", help="print one line per rule")
    parser.add_argument(
        "--warn-exit", action="store_true", help="exit nonzero on warnings too"
    )
    parser.add_argument(
        "--sync", metavar="ROOT",
        help="write writing-style.md into every directory under ROOT with a claude.md",
    )
    parser.add_argument(
        "--add-import", action="store_true",
        help="with --sync, append the @writing-style.md import to each claude.md",
    )
    return parser.parse_args(argv)


def _collect(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.suffix in CHECKED_SUFFIXES:
                    found.append(child)
        elif path.is_file():
            found.append(path)
    return found


def _selected_rules(spec: str | None) -> frozenset[str] | None:
    if not spec:
        return None
    wanted = frozenset(part.strip() for part in spec.split(",") if part.strip())
    unknown = wanted - set(REGISTRY)
    if unknown:
        raise SystemExit(f"unknown rule ids: {', '.join(sorted(unknown))}")
    return wanted


def run(argv: list[str]) -> int:
    args = _parse(argv)
    if args.docs:
        sys.stdout.write(render())
        return 0
    if args.summary:
        sys.stdout.write(render_summary())
        return 0
    if args.sync:
        root = Path(args.sync)
        for path, outcome in sync(find_targets(root), args.add_import):
            sys.stdout.write(f"{path}: {outcome}\n")
        return 0
    only = _selected_rules(args.rules)
    files = _collect(args.paths)
    if not files:
        sys.stderr.write("styleck: no files to check\n")
        return 2

    violations = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        if args.fix:
            repaired = apply_fixes(str(path), text, only)
            if repaired != text:
                path.write_text(repaired, encoding="utf-8")
                text = repaired
        violations.extend(check_document(Document(str(path), text), only))
    return _report(violations, args)


def _report(violations: list, args: argparse.Namespace) -> int:
    real = [v for v in violations if v.severity != MANUAL]
    if args.json:
        payload = [vars(v) for v in real]
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    else:
        for violation in real:
            sys.stdout.write(violation.format() + "\n")
    errors = sum(1 for v in real if v.severity == ERROR)
    if errors:
        return 1
    return 1 if (args.warn_exit and real) else 0


def main() -> None:
    raise SystemExit(run(sys.argv[1:]))
