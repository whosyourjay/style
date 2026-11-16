"""Regression coverage for preserving prose in mathematical transcriptions."""

import itertools
import tempfile
import unittest
from pathlib import Path

from styleck import check_document
from styleck.document import Document
from styleck.fixers import apply_fixes


class SelectionTests(unittest.TestCase):
    def test_transcription_profile_keeps_prose_and_math_checks(self):
        profile = """[transcription]
paths = original.tex
rules = math-fraction eq-trailing-punct
"""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / ".git").mkdir()
            (root / ".styleck-rules").write_text(profile, encoding="utf-8")
            original = str(root / "original.tex")
            new = str(root / "new.tex")
            for passive, separator in itertools.product(
                ["is computed", "is assigned", "is encoded"], [";", ":"]
            ):
                prose = f"The value {passive}{separator} the algorithm halts.\n"
                text = prose + r"$1/2$" + "\n" + r"\[x=1.\]"
                findings = check_document(Document(original, text))
                self.assertEqual(
                    {v.rule_id for v in findings},
                    {"math-fraction", "eq-trailing-punct"},
                )
                fixed = apply_fixes(original, text)
                self.assertTrue(fixed.startswith(prose))
                self.assertIn(r"\[x=1\]", fixed)
                self.assertIn(
                    "voice-passive",
                    {v.rule_id for v in check_document(Document(new, text))},
                )

    def test_explicit_rules_cannot_reenable_excluded_grammar(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / ".git").mkdir()
            (root / ".styleck-rules").write_text(
                "[paper]\npaths = *.tex\nrules = math-fraction\n",
                encoding="utf-8",
            )
            document = Document(str(root / "paper.tex"), "The value is computed.")
            self.assertEqual(
                check_document(document, frozenset({"voice-passive"})), []
            )
