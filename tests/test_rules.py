"""Unit tests for the checkers. Each test states its own input."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from styleck import check_document  # noqa: E402
from styleck.document import Document  # noqa: E402
from styleck.fixers import apply_fixes  # noqa: E402

PREAMBLE = "\\documentclass{article}\n\\begin{document}\n"


def tex(body: str) -> Document:
    return Document("t.tex", PREAMBLE + body + "\n\\end{document}\n")


def ids(document: Document) -> list[str]:
    return [v.rule_id for v in check_document(document)]


class TestTrailingPunctuation(unittest.TestCase):
    def test_period_after_display_is_flagged(self):
        self.assertIn("eq-trailing-punct", ids(tex("\\[\n  x = y .\n\\]")))

    def test_comma_before_row_break_is_flagged(self):
        body = "\\begin{align}\n  a &= b, \\\\\n  c &= d\n\\end{align}"
        self.assertIn("eq-trailing-punct", ids(tex(body)))

    def test_clean_display_passes(self):
        self.assertNotIn("eq-trailing-punct", ids(tex("\\[\n  x = y\n\\]")))

    def test_matrix_placeholder_dots_are_not_punctuation(self):
        body = "\\[\n\\begin{bmatrix}\n  1 & . \\\\\n  . & 1\n\\end{bmatrix}\n\\]"
        self.assertNotIn("eq-trailing-punct", ids(tex(body)))

    def test_decimal_point_is_not_flagged(self):
        self.assertNotIn("eq-trailing-punct", ids(tex("\\[\n  x = 0.5\n\\]")))

    def test_fix_removes_the_punctuation_and_its_trailing_space(self):
        source = PREAMBLE + "\\[\n  x = y .\n\\]\n"
        self.assertEqual(apply_fixes("t.tex", source), PREAMBLE + "\\[\n  x = y\n\\]\n")

    def test_fix_keeps_indentation(self):
        source = PREAMBLE + "\\[\n    x = y,\n\\]\n"
        self.assertEqual(apply_fixes("t.tex", source), PREAMBLE + "\\[\n    x = y\n\\]\n")


class TestNeedsAlign(unittest.TestCase):
    def test_chain_of_three_relations_is_flagged(self):
        self.assertIn("eq-needs-align", ids(tex("\\[\n  a = b = c = d\n\\]")))

    def test_single_relation_passes(self):
        self.assertNotIn("eq-needs-align", ids(tex("\\[\n  a = b + c\n\\]")))

    def test_small_second_side_is_allowed(self):
        self.assertNotIn("eq-needs-align", ids(tex("\\[\n  \\sum_i x_i = y_i + z_i = 0\n\\]")))

    def test_relation_inside_subscript_does_not_count(self):
        self.assertNotIn("eq-needs-align", ids(tex("\\[\n  \\sum_{i=1}^n x_i = y\n\\]")))

    def test_align_environment_is_exempt(self):
        body = "\\begin{align}\n  a &= b \\\\\n  &= c\n\\end{align}"
        self.assertNotIn("eq-needs-align", ids(tex(body)))

    def test_relations_inside_matrix_do_not_count(self):
        body = "\\[\n  A = \\begin{bmatrix} x \\le y \\\\ z \\ge w \\end{bmatrix}\n\\]"
        self.assertNotIn("eq-needs-align", ids(tex(body)))


class TestTextGap(unittest.TestCase):
    def test_stub_between_displays_is_flagged(self):
        self.assertIn("tex-text-gap", ids(tex("\\[ a \\]\nFor example\n\\[ b \\]")))

    def test_substantial_paragraph_passes(self):
        gap = (
            "The left side counts every pair twice, so halving it gives the number "
            "of edges. The same argument applies at every vertex. Summing over the "
            "graph yields the second bound."
        )
        self.assertNotIn("tex-text-gap", ids(tex(f"\\[ a \\]\n{gap}\n\\[ b \\]")))

    def test_adjacent_displays_are_not_a_gap(self):
        self.assertNotIn("tex-text-gap", ids(tex("\\[ a \\]\n\\[ b \\]")))

    def test_structural_break_is_ignored(self):
        body = "\\[ a \\]\n\\end{proof}\n\\begin{proof}\n\\[ b \\]"
        self.assertNotIn("tex-text-gap", ids(tex(body)))


class TestShortLines(unittest.TestCase):
    def test_run_of_stubby_lines_is_flagged(self):
        body = "The bound follows\nfrom convexity of\nthe square function\nand nothing else."
        self.assertIn("tex-short-lines", ids(tex(body)))

    def test_one_long_line_passes(self):
        body = "The bound follows from convexity of the square function and nothing else."
        self.assertNotIn("tex-short-lines", ids(tex(body)))

    def test_bibliography_entries_are_exempt(self):
        body = (
            "\\begin{thebibliography}{9}\n\\bibitem{A}\nM. Blaser,\n"
            "\\textit{Tensors},\npp. 1-10\n\\end{thebibliography}"
        )
        self.assertNotIn("tex-short-lines", ids(tex(body)))

    def test_fix_rewraps_and_keeps_the_words(self):
        body = "The bound follows\nfrom convexity of\nthe square function\nand nothing else."
        fixed = apply_fixes("t.tex", PREAMBLE + body + "\n")
        self.assertNotIn("tex-short-lines", ids(Document("t.tex", fixed)))
        self.assertEqual(fixed.split(), (PREAMBLE + body + "\n").split())

    def test_fix_never_splits_inline_math(self):
        body = "A short line here\nwith $x + y + z$\nand a bit more\ntext to wrap now."
        fixed = apply_fixes("t.tex", PREAMBLE + body + "\n")
        for line in fixed.split("\n"):
            self.assertEqual(line.count("$") % 2, 0, line)


class TestProse(unittest.TestCase):
    def test_the_display_is_flagged(self):
        self.assertIn("the-display", ids(tex("Combining the display with Lemma 2 works.")))

    def test_trailing_adverb_is_flagged(self):
        self.assertIn("adverb-tail", ids(tex("We arrange the deck cleanly.")))

    def test_adverb_tail_message_asks_rather_than_orders(self):
        found = [v for v in check_document(tex("It is applied unevenly."))
                 if v.rule_id == "adverb-tail"]
        self.assertEqual(len(found), 1)
        self.assertIn("delete it and reread", found[0].message)
        self.assertEqual(found[0].severity, "warn")

    def test_respectively_is_allowed(self):
        self.assertNotIn("adverb-tail", ids(tex("The columns are $i$ and $j$, respectively.")))

    def test_only_is_not_an_adverb_tail(self):
        self.assertNotIn("adverb-tail", ids(tex("This holds for the first case only.")))

    def test_passive_naming_is_flagged(self):
        self.assertIn("voice-naming", ids(tex("A vertex of high degree is called heavy.")))

    def test_hedge_is_flagged(self):
        self.assertIn("voice-hedge", ids(tex("It can be shown that $\\Phi$ decreases.")))

    def test_prose_rules_ignore_math_content(self):
        self.assertNotIn("empty-adverb", ids(tex("\\[ \\text{clearly} = x \\]")))

    def test_preamble_is_not_prose(self):
        document = Document("t.tex", "\\title{A novel method}\n\\begin{document}\nHi.\n")
        self.assertNotIn("empty-adjective", ids(document))


class TestMetaCommentary(unittest.TestCase):
    def test_history_in_tex_comment_is_flagged(self):
        self.assertIn("meta-commentary", ids(tex("% changed from a linear bound as requested")))

    def test_ordinary_comment_passes(self):
        self.assertNotIn("meta-commentary", ids(tex("% bound the potential from above")))

    def test_prose_saying_previously_is_not_a_comment(self):
        self.assertNotIn("meta-commentary", ids(tex("Previously we bounded the rank.")))


class TestMarkdown(unittest.TestCase):
    def test_inline_code_is_not_prose(self):
        self.assertNotIn("the-display", ids(Document("t.md", "Bad: `the display` here.\n")))

    def test_fenced_block_is_not_prose(self):
        source = "Text.\n\n```\nIt can be shown that clearly the display works.\n```\n"
        self.assertEqual(ids(Document("t.md", source)), [])

    def test_markdown_prose_is_still_checked(self):
        self.assertIn("the-display", ids(Document("t.md", "Combining the display works.\n")))


class TestScope(unittest.TestCase):
    """The repo checks writing, not code."""

    def test_no_rule_targets_python(self):
        source = "def f():\n" + "".join(f"    x = {i}\n" for i in range(200))
        self.assertEqual(ids(Document("t.py", source)), [])

    def test_long_tex_prose_line_is_allowed(self):
        self.assertEqual(ids(tex("word " * 40)), [])

    def test_registry_holds_no_coding_rules(self):
        from styleck.rule import REGISTRY

        banned = {"line-length", "file-length", "function-length", "dry"}
        self.assertEqual(banned.intersection(REGISTRY), set())


if __name__ == "__main__":
    unittest.main()
