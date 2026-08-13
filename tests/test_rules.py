"""Unit tests for the checkers. Each test states its own input."""

from __future__ import annotations

import sys
import tempfile
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

    def test_period_before_label_is_flagged(self):
        body = "\\begin{equation}\n  x = y. \\label{eq:x}\n\\end{equation}"
        self.assertIn("eq-trailing-punct", ids(tex(body)))

    def test_fix_preserves_label(self):
        source = PREAMBLE + "\\[\n  x = y. \\label{eq:x}\n\\]\n"
        expected = PREAMBLE + "\\[\n  x = y \\label{eq:x}\n\\]\n"
        self.assertEqual(apply_fixes("t.tex", source), expected)

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


class TestMalformedControl(unittest.TestCase):
    def test_bare_math_command_is_flagged(self):
        body = r"$m \geq 1, qquadE \log M=\nu$"
        self.assertIn("tex-malformed-control", ids(tex(body)))

    def test_escaped_math_command_passes(self):
        body = r"$m \geq 1, \qquad \E \log M=\nu$"
        self.assertNotIn("tex-malformed-control", ids(tex(body)))

    def test_math_word_inside_text_group_passes(self):
        self.assertNotIn("tex-malformed-control", ids(tex(r"$\text{quad}$")))

    def test_command_word_in_prose_passes(self):
        self.assertNotIn("tex-malformed-control", ids(tex("A quad has four sides.")))

    def test_control_character_is_flagged(self):
        self.assertIn("tex-malformed-control", ids(tex("bad\x0ccommand")))


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

    def test_vague_theorem_reference_is_flagged(self):
        self.assertIn("precise-reference", ids(tex("The theorem permits equality.")))

    def test_numbered_theorem_reference_passes(self):
        body = r"Theorem~\ref{thm:main} permits equality."
        self.assertNotIn("precise-reference", ids(tex(body)))

    def test_modified_lemma_reference_is_flagged(self):
        body = "The clean alignment lemma supplies the factorization."
        self.assertIn("precise-reference", ids(tex(body)))

    def test_proof_of_numbered_theorem_passes(self):
        body = r"Only one change to the proof of Theorem~\ref{thm:main} is needed."
        self.assertNotIn("precise-reference", ids(tex(body)))

    def test_bare_abstract_referent_is_flagged(self):
        self.assertIn("vague-referent", ids(tex("The functional is bounded.")))

    def test_modified_abstract_referent_is_flagged(self):
        body = "The same high-entropy dichotomy proves the converse."
        self.assertIn("vague-referent", ids(tex(body)))

    def test_equation_qualified_estimate_passes(self):
        body = r"The estimate \eqref{eq:local} bounds the error."
        self.assertNotIn("vague-referent", ids(tex(body)))

    def test_unspecified_convention_is_flagged(self):
        body = "A fixed convention handles the final coordinate."
        self.assertIn("state-conventions", ids(tex(body)))

    def test_explicit_convention_passes(self):
        body = "If the action crosses $x_n$, emit the remaining suffix unchanged."
        self.assertNotIn("state-conventions", ids(tex(body)))


class TestTermFirstUse(unittest.TestCase):
    def test_earlier_multiword_term_is_flagged(self):
        body = (
            "The alignment path records the script.\n"
            "The \\term{alignment path} is a lattice path."
        )
        self.assertIn("term-first-use", ids(tex(body)))

    def test_marked_first_use_passes(self):
        body = "The \\term{alignment path} records the script."
        self.assertNotIn("term-first-use", ids(tex(body)))

    def test_definition_title_is_not_counted_as_prior_use(self):
        body = (
            "\\begin{definition}[Alignment path]\n"
            "The \\term{alignment path} records the script.\n"
            "\\end{definition}"
        )
        self.assertNotIn("term-first-use", ids(tex(body)))

    def test_math_occurrence_is_not_counted_as_prior_prose(self):
        body = "$\\text{alignment path}$\nThe \\term{alignment path} records the script."
        self.assertNotIn("term-first-use", ids(tex(body)))

    def test_single_word_terms_remain_judgment_calls(self):
        body = "An anchor comes first. We mark an \\term{anchor} later."
        self.assertNotIn("term-first-use", ids(tex(body)))


class TestTermVocabulary(unittest.TestCase):
    def document(self, root: Path, body: str) -> Document:
        return Document(str(root / "paper.tex"), PREAMBLE + body + "\n\\end{document}\n")

    def test_background_term_is_not_marked_as_new(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            (root / "paper.styleck-terms").write_text("relative entropy\n")
            document = self.document(root, r"The \term{relative entropy} is finite.")
            self.assertIn("term-background", ids(document))

    def test_source_file_can_supply_background_terms(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            (root / "source.tex").write_text(r"A \term{renewal process}.")
            (root / "paper.styleck-terms").write_text("@source.tex\n")
            document = self.document(root, r"A \term{renewal process} appears.")
            self.assertIn("term-background", ids(document))

    def test_background_formula_definition_is_flagged(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            (root / "paper.styleck-terms").write_text("binary entropy function\n")
            body = (
                "The binary entropy function is\n"
                r"$h_2(p)=-p\log p-(1-p)\log(1-p)$."
            )
            self.assertIn("background-redefinition", ids(self.document(root, body)))

    def test_background_property_is_not_a_redefinition(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            (root / "paper.styleck-terms").write_text("relative entropy\n")
            document = self.document(root, "Relative entropy is nonnegative.")
            self.assertNotIn("background-redefinition", ids(document))

    def test_background_notation_convention_is_allowed(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            (root / "paper.styleck-terms").write_text("relative entropy\n")
            document = self.document(root, r"Write $D(P\Vert Q)$ for relative entropy.")
            self.assertNotIn("background-redefinition", ids(document))

    def test_single_use_multiword_term_is_flagged(self):
        document = tex(r"Let \term{window family} denote the intervals.")
        self.assertIn("term-single-use", ids(document))

    def test_reused_multiword_term_passes(self):
        body = r"Let \term{window family} denote the intervals. The window family is finite."
        self.assertNotIn("term-single-use", ids(tex(body)))

    def test_plural_reuse_passes(self):
        body = r"Define an \term{alignment path}. The two alignment paths then meet."
        self.assertNotIn("term-single-use", ids(tex(body)))

    def test_definition_title_does_not_count_as_reuse(self):
        body = (
            r"\begin{definition}[Window family]" "\n"
            r"Let \term{window family} denote the intervals." "\n"
            r"\end{definition}"
        )
        self.assertIn("term-single-use", ids(tex(body)))


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
