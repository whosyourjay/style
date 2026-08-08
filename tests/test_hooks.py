"""Tests for the Claude/Codex and Git hook adapters."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hooks.styleck_hook import _targets  # noqa: E402
from hooks.styleck_pre_commit import staged_findings  # noqa: E402

PREAMBLE = "\\documentclass{article}\n\\begin{document}\n"
CLEAN = PREAMBLE + "\\[\n  x = y\n\\]\n"
BAD = PREAMBLE + "\\[\n  x = y .\n\\]\n"


class TestAgentPayloads(unittest.TestCase):
    def test_claude_file_path(self):
        payload = {"cwd": "/repo", "tool_input": {"file_path": "paper.tex"}}
        self.assertEqual(_targets(payload), [Path("/repo/paper.tex")])

    def test_codex_apply_patch_paths(self):
        patch = """*** Begin Patch
*** Update File: chapters/one.tex
@@
-old
+new
*** Add File: appendix with spaces.tex
+text
*** Update File: old-name.tex
*** Move to: new-name.tex
@@
-old
+new
*** End Patch"""
        payload = {"cwd": "/repo", "tool_input": {"command": patch}}
        self.assertEqual(
            _targets(payload),
            [
                Path("/repo/chapters/one.tex"),
                Path("/repo/appendix with spaces.tex"),
                Path("/repo/old-name.tex"),
                Path("/repo/new-name.tex"),
            ],
        )

    def test_duplicate_patch_path_is_checked_once(self):
        patch = """*** Begin Patch
*** Update File: paper.tex
*** Update File: paper.tex
*** End Patch"""
        payload = {"cwd": "/repo", "tool_input": {"command": patch}}
        self.assertEqual(_targets(payload), [Path("/repo/paper.tex")])


class TestPreCommit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self._run("init", "-q")
        self._run("config", "user.email", "t@example.com")
        self._run("config", "user.name", "t")

    def _run(self, *args: str) -> None:
        subprocess.run(
            ["git", *args], cwd=self.root, capture_output=True, check=True
        )

    def _commit(self, text: str) -> Path:
        path = self.root / "paper.tex"
        path.write_text(text, encoding="utf-8")
        self._run("add", "paper.tex")
        self._run("commit", "-q", "-m", "baseline")
        return path

    def test_reads_staged_content_not_unstaged_content(self):
        path = self._commit(CLEAN)
        path.write_text(BAD, encoding="utf-8")
        self._run("add", "paper.tex")
        path.write_text(CLEAN, encoding="utf-8")
        self.assertEqual(
            [v.rule_id for v in staged_findings(self.root)],
            ["eq-trailing-punct"],
        )

    def test_legacy_findings_are_silent(self):
        path = self._commit(BAD)
        path.write_text(BAD + "More text.\n", encoding="utf-8")
        self._run("add", "paper.tex")
        self.assertEqual(staged_findings(self.root), [])

    def test_new_file_has_no_baseline(self):
        path = self.root / "new.tex"
        path.write_text(BAD, encoding="utf-8")
        self._run("add", "new.tex")
        self.assertEqual(
            [v.rule_id for v in staged_findings(self.root)],
            ["eq-trailing-punct"],
        )


if __name__ == "__main__":
    unittest.main()
