"""Select rule profiles for matching source paths."""

from __future__ import annotations

from configparser import ConfigParser
from fnmatch import fnmatchcase
from pathlib import Path

from .config import config_chain


def selected_rules(
    source_path: str, requested: frozenset[str] | None = None
) -> frozenset[str] | None:
    """Intersect requested checks with any matching .styleck-rules profiles."""
    source = Path(source_path).resolve()
    selected = requested
    for config in config_chain(source_path, ".styleck-rules"):
        parser = ConfigParser(interpolation=None)
        parser.read(config, encoding="utf-8")
        relative = source.relative_to(config.parent).as_posix()
        for section in parser.sections():
            patterns = parser.get(section, "paths").splitlines()
            if not any(fnmatchcase(relative, p.strip()) for p in patterns if p.strip()):
                continue
            rules = frozenset(parser.get(section, "rules").split())
            if not rules:
                raise ValueError(f"{config}: profile {section!r} has no rules")
            selected = rules if selected is None else selected & rules
    return selected
