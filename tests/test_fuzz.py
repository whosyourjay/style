"""Fuzz tests.

These assert invariants rather than specific findings: the scanner must cover
the input exactly, nothing may crash, and a fixed file must stay fixed.
"""

from __future__ import annotations

import random
import string
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from styleck import check_document  # noqa: E402
from styleck.document import Document, scan  # noqa: E402
from styleck.fixers import FIXERS, apply_fixes  # noqa: E402
from styleck.wrap import WRAP_TARGET, atoms  # noqa: E402

ROUNDS = 400

FRAGMENTS = [
    "Let $x$ be a vertex of high degree.",
    "\\[\n  a = b = c .\n\\]",
    "\\begin{align}\n  a &= b, \\\\\n  c &= d\n\\end{align}",
    "\\begin{bmatrix} 1 & . \\\\ . & 1 \\end{bmatrix}",
    "% changed from a linear bound as requested",
    "\\begin{verbatim}\n$ \\[ unbalanced\n\\end{verbatim}",
    "It can be shown that the display is called heavy clearly.",
    "The residual is accepted by the search and was chosen for us.",
    "A \\term{terminal occurrence} is a slot; the boundary occurrences differ.",
    "An attachment meets it. A second attachment. A third. A fourth attachment.",
    "short\nlines\nhere\nand\nmore",
    "\\begin{algorithmic}\n\\State Swap $a$ and $b$.\n\\end{algorithmic}",
    "\\begin{thebibliography}{9}\n\\bibitem{A}\nM. B,\npp. 1-2\n\\end{thebibliography}",
    "$",
    "\\[",
    "\\begin{align}",
    "\\end{document}",
    "&",
    "{",
    "}",
    "\\\\",
    "\\text{clearly}",
    "$x = \\text{a very long piece of inline mathematics indeed here}$",
]

ALPHABET = string.ascii_letters + " \n${}\\%&[]^_.,;:="


def random_document(rng: random.Random) -> str:
    parts = ["\\documentclass{article}", "\\begin{document}"]
    for _ in range(rng.randint(0, 12)):
        parts.append(rng.choice(FRAGMENTS))
    parts.append("\\end{document}")
    return "\n".join(parts)


def random_noise(rng: random.Random) -> str:
    return "".join(rng.choice(ALPHABET) for _ in range(rng.randint(0, 300)))


class TestScanner(unittest.TestCase):
    def test_spans_partition_the_input(self):
        rng = random.Random(1)
        for _ in range(ROUNDS):
            text = random_document(rng) if rng.random() < 0.5 else random_noise(rng)
            spans = scan(text)
            cursor = 0
            for span in spans:
                self.assertEqual(span.start, cursor, text)
                self.assertGreaterEqual(span.end, span.start)
                cursor = span.end
            self.assertEqual(cursor, len(text), text)

    def test_line_and_column_round_trip(self):
        rng = random.Random(2)
        for _ in range(ROUNDS):
            text = random_document(rng)
            document = Document("f.tex", text)
            for _ in range(10):
                offset = rng.randrange(len(text))
                if text[offset] == "\n":
                    continue
                line = document.line_of(offset)
                column = document.column_of(offset)
                self.assertEqual(document.lines[line - 1][column - 1], text[offset])


class TestNoCrash(unittest.TestCase):
    def test_checking_arbitrary_input_never_raises(self):
        rng = random.Random(3)
        for _ in range(ROUNDS):
            text = random_document(rng) if rng.random() < 0.5 else random_noise(rng)
            for name in ("f.tex", "f.md", "f.txt"):
                check_document(Document(name, text))

    def test_violations_point_inside_the_file(self):
        rng = random.Random(4)
        for _ in range(ROUNDS):
            text = random_document(rng)
            document = Document("f.tex", text)
            for violation in check_document(document):
                self.assertGreaterEqual(violation.line, 1)
                self.assertLessEqual(violation.line, len(document.lines))
                self.assertGreaterEqual(violation.column, 1)


class TestFixers(unittest.TestCase):
    def test_fixing_is_idempotent(self):
        rng = random.Random(5)
        for _ in range(ROUNDS):
            text = random_document(rng)
            once = apply_fixes("f.tex", text)
            self.assertEqual(apply_fixes("f.tex", once), once, text)

    def test_fixed_file_has_no_fixable_violations_left(self):
        rng = random.Random(6)
        fixable = frozenset(FIXERS)
        for _ in range(ROUNDS):
            text = random_document(rng)
            fixed = apply_fixes("f.tex", text)
            left = [v.rule_id for v in check_document(Document("f.tex", fixed))]
            self.assertFalse(fixable.intersection(left), f"{text}\n---\n{fixed}")

    def test_fixing_never_loses_a_word(self):
        rng = random.Random(7)
        for _ in range(ROUNDS):
            text = random_document(rng)
            fixed = apply_fixes("f.tex", text)
            self.assertEqual(_letters(fixed), _letters(text))

    def test_wrapping_keeps_math_balanced(self):
        rng = random.Random(8)
        for _ in range(ROUNDS):
            text = random_document(rng)
            fixed = apply_fixes("f.tex", text)
            self.assertEqual(fixed.count("$") % 2, text.count("$") % 2)

    def test_atoms_never_split_inline_math(self):
        rng = random.Random(9)
        for _ in range(ROUNDS):
            words = [rng.choice(["a", "bb", "$x", "y$", "$z$", "ccc"]) for _ in range(12)]
            for atom in atoms(" ".join(words)):
                if atom.count("$") % 2:
                    self.assertEqual(atom, atoms(" ".join(words))[-1])


def _letters(text: str) -> str:
    return "".join(char for char in text if char.isalnum())


class TestWrap(unittest.TestCase):
    def test_short_atoms_wrap_within_target(self):
        rng = random.Random(10)
        from styleck.wrap import wrap

        for _ in range(ROUNDS):
            words = ["x" * rng.randint(1, 9) for _ in range(rng.randint(1, 40))]
            for line in wrap(" ".join(words), ""):
                self.assertLessEqual(len(line), WRAP_TARGET)


if __name__ == "__main__":
    unittest.main()
