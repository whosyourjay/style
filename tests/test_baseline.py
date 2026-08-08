"""Tests for reporting only what an edit introduced."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from styleck import check_document  # noqa: E402
from styleck.baseline import git_baseline, new_violations  # noqa: E402
from styleck.document import Document  # noqa: E402

PREAMBLE = "\\documentclass{article}\n\\begin{document}\n"
LEGACY = PREAMBLE + "\\[\n  x = y .\n\\]\n\\[\n  a = b .\n\\]\n"


def doc(text: str) -> Document:
    return Document("paper.tex", text)


def findings(document: Document) -> list:
    return check_document(document)


def fresh(current_text: str, baseline_text: str | None) -> list[str]:
    current = doc(current_text)
    baseline = None if baseline_text is None else doc(baseline_text)
    prior = [] if baseline is None else findings(baseline)
    return [v.rule_id for v in new_violations(current, findings(current), baseline, prior)]


class TestNewViolations(unittest.TestCase):
    def test_untouched_legacy_findings_are_silent(self):
        self.assertEqual(fresh(LEGACY, LEGACY), [])

    def test_a_new_finding_is_reported(self):
        added = LEGACY + "Combining the display with Lemma 2 gives the bound.\n"
        self.assertEqual(fresh(added, LEGACY), ["the-display"])

    def test_inserting_text_does_not_resurface_later_findings(self):
        shifted = PREAMBLE + "A new opening sentence sits here.\n" + LEGACY[len(PREAMBLE):]
        self.assertEqual(fresh(shifted, LEGACY), [])

    def test_a_second_copy_of_the_same_finding_is_new(self):
        added = LEGACY + "\\[\n  p = q .\n\\]\n"
        self.assertEqual(fresh(added, LEGACY), ["eq-trailing-punct"])

    def test_fixing_a_legacy_finding_reports_nothing(self):
        cleaned = LEGACY.replace("x = y .", "x = y")
        self.assertEqual(fresh(cleaned, LEGACY), [])

    def test_no_baseline_reports_everything(self):
        self.assertEqual(len(fresh(LEGACY, None)), 2)


class TestGitBaseline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self._run("git", "init", "-q")
        self._run("git", "config", "user.email", "t@example.com")
        self._run("git", "config", "user.name", "t")

    def _run(self, *args: str) -> None:
        subprocess.run(args, cwd=self.root, capture_output=True, check=True)

    def test_returns_the_committed_text(self):
        path = self.root / "paper.tex"
        path.write_text(LEGACY, encoding="utf-8")
        self._run("git", "add", "paper.tex")
        self._run("git", "commit", "-q", "-m", "add")
        path.write_text(LEGACY + "More text here.\n", encoding="utf-8")
        baseline = git_baseline(path)
        self.assertIsNotNone(baseline)
        self.assertEqual(baseline.text, LEGACY)

    def test_untracked_file_has_no_baseline(self):
        path = self.root / "new.tex"
        path.write_text(LEGACY, encoding="utf-8")
        self.assertIsNone(git_baseline(path))

    def test_path_outside_any_repo_has_no_baseline(self):
        with tempfile.TemporaryDirectory() as plain:
            path = Path(plain) / "paper.tex"
            path.write_text(LEGACY, encoding="utf-8")
            self.assertIsNone(git_baseline(path))


if __name__ == "__main__":
    unittest.main()
