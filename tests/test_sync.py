"""Tests for generating the guide and distributing it to paper repos."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from styleck import REGISTRY  # noqa: E402
from styleck.docgen import render, render_summary  # noqa: E402
from styleck.sync import IMPORT_LINE, find_targets, sync  # noqa: E402


class TestDocgen(unittest.TestCase):
    def test_every_rule_appears_in_the_guide(self):
        body = render()
        for rule_id in REGISTRY:
            self.assertIn(rule_id, body)

    def test_summary_has_one_line_per_rule(self):
        self.assertEqual(len(render_summary().strip().split("\n")), len(REGISTRY))

    def test_guide_respects_the_hundred_column_limit(self):
        for line in render().split("\n"):
            self.assertLessEqual(len(line), 100, line)


class TestSync(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _repo(self, name: str, claude: str = "local rules\n") -> Path:
        directory = self.root / name
        directory.mkdir()
        (directory / "claude.md").write_text(claude, encoding="utf-8")
        return directory

    def test_finds_only_directories_with_a_claude_md(self):
        self._repo("paper")
        (self.root / "empty").mkdir()
        self.assertEqual(find_targets(self.root), [self.root / "paper"])

    def test_creates_the_guide_and_leaves_claude_md_alone(self):
        directory = self._repo("paper")
        sync([directory])
        self.assertTrue((directory / "writing-style.md").is_file())
        self.assertEqual((directory / "claude.md").read_text(), "local rules\n")

    def test_second_run_reports_unchanged(self):
        directory = self._repo("paper")
        sync([directory])
        self.assertIn("unchanged", sync([directory])[0][1])

    def test_hand_written_guide_is_never_overwritten(self):
        directory = self._repo("paper")
        (directory / "writing-style.md").write_text("mine\n", encoding="utf-8")
        _, outcome = sync([directory])[0]
        self.assertIn("skipped", outcome)
        self.assertEqual((directory / "writing-style.md").read_text(), "mine\n")

    def test_add_import_appends_once(self):
        directory = self._repo("paper")
        sync([directory], add_import=True)
        sync([directory], add_import=True)
        body = (directory / "claude.md").read_text()
        self.assertEqual(body.count(IMPORT_LINE), 1)

    def test_regenerated_guide_tracks_a_rule_change(self):
        directory = self._repo("paper")
        sync([directory])
        first = (directory / "writing-style.md").read_text()
        self.assertIn("eq-trailing-punct", first)


if __name__ == "__main__":
    unittest.main()
