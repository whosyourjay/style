"""The rule registry.

A rule carries both the instruction an agent reads and the detector that
catches violations. Generating the style guide from this registry keeps the
prose and the checker from drifting apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from .document import Document

ERROR = "error"
WARN = "warn"
MANUAL = "manual"


@dataclass(frozen=True)
class Violation:
    rule_id: str
    path: str
    line: int
    column: int
    message: str
    severity: str = ERROR

    def format(self) -> str:
        return (
            f"{self.path}:{self.line}:{self.column}: "
            f"{self.severity}[{self.rule_id}] {self.message}"
        )


@dataclass(frozen=True)
class Rule:
    """One style rule: what to do, why, and how to detect a breach."""

    id: str
    summary: str
    severity: str
    check: Callable[[Document], Iterable[Violation]]
    section: str = "General"
    applies_to: tuple[str, ...] = ("*",)
    detail: str = ""
    bad: str = ""
    good: str = ""

    def matches(self, document: Document) -> bool:
        return "*" in self.applies_to or document.suffix in self.applies_to


REGISTRY: dict[str, Rule] = {}
SECTION_ORDER: list[str] = []


def register(**kwargs) -> Callable:
    """Decorate a check function to register it as a rule."""

    def wrap(func: Callable[[Document], Iterable[Violation]]) -> Callable:
        rule = Rule(check=func, **kwargs)
        if rule.id in REGISTRY:
            raise ValueError(f"duplicate rule id: {rule.id}")
        REGISTRY[rule.id] = rule
        if rule.section not in SECTION_ORDER:
            SECTION_ORDER.append(rule.section)
        return func

    return wrap


def manual(**kwargs) -> None:
    """Register a rule that no checker can enforce, for the guide only."""
    register(severity=MANUAL, **kwargs)(lambda document: ())


def make(document: Document, rule_id: str, offset: int, message: str) -> Violation:
    """Build a violation from a character offset in `document`."""
    return Violation(
        rule_id=rule_id,
        path=document.path,
        line=document.line_of(offset),
        column=document.column_of(offset),
        message=message,
        severity=REGISTRY[rule_id].severity if rule_id in REGISTRY else ERROR,
    )


def at_line(document: Document, rule_id: str, lineno: int, message: str) -> Violation:
    """Build a violation anchored at the start of a 1-based line."""
    return Violation(
        rule_id=rule_id,
        path=document.path,
        line=lineno,
        column=1,
        message=message,
        severity=REGISTRY[rule_id].severity if rule_id in REGISTRY else ERROR,
    )


def all_rules() -> list[Rule]:
    return [REGISTRY[key] for key in sorted(REGISTRY)]


def check_document(document: Document, only: frozenset[str] | None = None) -> list[Violation]:
    """Run every applicable rule over one document."""
    found: list[Violation] = []
    for rule in all_rules():
        if only is not None and rule.id not in only:
            continue
        if not rule.matches(document):
            continue
        found.extend(rule.check(document))
    found.sort(key=lambda v: (v.line, v.column, v.rule_id))
    return found
