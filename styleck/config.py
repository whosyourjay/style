"""Locate the sidecar config files that apply to one source file."""

from __future__ import annotations

from pathlib import Path


def config_chain(source_path: str, suffix: str) -> list[Path]:
    """Config files for ``source_path``, project level first.

    A source-specific ``name<suffix>`` extends the nearest ``<suffix>`` at or
    above the file's directory, searching no further than the repository root.
    """
    source = Path(source_path).resolve()
    chain: list[Path] = []
    project = _nearest(source.parent, suffix)
    if project is not None:
        chain.append(project)
    specific = source.with_suffix(suffix)
    if specific.is_file() and specific not in chain:
        chain.append(specific)
    return chain


def _nearest(start: Path, suffix: str) -> Path | None:
    for directory in (start, *start.parents):
        candidate = directory / suffix
        if candidate.is_file():
            return candidate
        if (directory / ".git").exists():
            break
    return None
