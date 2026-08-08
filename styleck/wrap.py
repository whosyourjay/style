"""Line wrapping shared by the short-line check and its fixer.

Both must agree on what counts as an atom. If they disagree the checker can
flag a line the fixer is unable to lengthen.
"""

from __future__ import annotations

import re

WRAP_TARGET = 80

DOLLAR_RE = re.compile(r"(?<!\\)\$")


def unescaped_dollars(text: str) -> int:
    return len(DOLLAR_RE.findall(text))


def atoms(text: str) -> list[str]:
    """Whitespace tokens, with `$...$` groups kept whole."""
    found, buffer = [], ""
    for token in text.split():
        buffer = token if not buffer else buffer + " " + token
        if unescaped_dollars(buffer) % 2 == 0:
            found.append(buffer)
            buffer = ""
    if buffer:
        found.append(buffer)
    return found


def wrap(text: str, indent: str) -> list[str]:
    """Greedy wrap to the target width that never splits inline math."""
    lines, current = [], ""
    for atom in atoms(text):
        candidate = indent + atom if not current else current + " " + atom
        if current and len(candidate) > WRAP_TARGET:
            lines.append(current)
            current = indent + atom
            continue
        current = candidate
    if current.strip():
        lines.append(current)
    return lines or [indent.rstrip()]


def first_atom(text: str) -> str:
    found = atoms(text)
    return found[0] if found else ""
