"""Tests for high-recall lexical audits."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from styleck.concordance import concordance  # noqa: E402
from styleck.document import Document  # noqa: E402


class TestConcordance(unittest.TestCase):
    def test_lists_every_prose_occurrence(self):
        source = (
            "\\begin{document}\n"
            "The first line has the word twice.\n"
            "$\\text{the}$ is math, not prose.\n"
            "\\end{document}\n"
        )
        entries = concordance(Document("paper.tex", source), "the")
        self.assertEqual([(entry.line, entry.column) for entry in entries], [(2, 1), (2, 20)])

    def test_query_is_one_word(self):
        with self.assertRaises(ValueError):
            concordance(Document("paper.tex", "two words"), "two words")


if __name__ == "__main__":
    unittest.main()
