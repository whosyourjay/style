"""Project vocabulary files and explicitly introduced terms."""

from __future__ import annotations

import re
from pathlib import Path


TERM_RE = re.compile(r"\\term\s*\{([^{}]+)\}")


def normalize_term(term: str) -> str:
    """Normalize a literal prose term for exact dictionary comparison."""
    return " ".join(term.split()).casefold()


def introduced_terms(text: str) -> list[str]:
    r"""Return terms marked with ``\term{...}``, preserving source order."""
    return [" ".join(match.group(1).split()) for match in TERM_RE.finditer(text)]


def background_terms(source_path: str) -> frozenset[str]:
    r"""Load the background vocabulary that applies to ``source_path``.

    A source-specific ``name.styleck-terms`` extends the nearest project-level
    ``.styleck-terms``.  Lines beginning with ``@`` include another term list;
    a TeX include contributes the terms it explicitly marks with ``\term``.
    """
    source = Path(source_path).resolve()
    configs: list[Path] = []
    project = _nearest_project_config(source.parent)
    if project is not None:
        configs.append(project)
    specific = source.with_suffix(".styleck-terms")
    if specific.is_file() and specific not in configs:
        configs.append(specific)

    found: set[str] = set()
    seen: set[Path] = set()
    for config in configs:
        found.update(_read_term_list(config, seen))
    return frozenset(found)


def _nearest_project_config(start: Path) -> Path | None:
    for directory in (start, *start.parents):
        candidate = directory / ".styleck-terms"
        if candidate.is_file():
            return candidate
        if (directory / ".git").exists():
            break
    return None


def _read_term_list(path: Path, seen: set[Path]) -> set[str]:
    path = path.resolve()
    if path in seen or not path.is_file():
        return set()
    seen.add(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix in {".tex", ".sty", ".cls", ".tikz"}:
        return {normalize_term(term) for term in introduced_terms(text)}

    found: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            found.update(_read_term_list(path.parent / line[1:].strip(), seen))
            continue
        found.add(normalize_term(line))
    return found
