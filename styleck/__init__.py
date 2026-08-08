"""styleck — machine-checked writing style for math papers.

Scope is writing quality: LaTeX layout, equations, diagrams, and prose. It is
not a code linter and holds no coding standards.

Importing the package registers every rule.
"""

from __future__ import annotations

from .document import Document, load
from .rule import REGISTRY, Violation, all_rules, check_document

from . import rules_tex  # noqa: F401  (import registers rules)
from . import rules_prose  # noqa: F401
from . import rules_manual  # noqa: F401

__all__ = [
    "Document",
    "REGISTRY",
    "Violation",
    "all_rules",
    "check_document",
    "load",
]
