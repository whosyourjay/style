"""Regressions and fuzz coverage for rules shared with lecture books."""

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from styleck import Document, REGISTRY, check_document
from styleck import book
from styleck.docgen import render

SHARED = {
    "E102": book.check_display_punctuation,
    "E103": book.check_multi_relation_display,
    "E105": book.check_title_case,
    "E107": book.check_ellipsis,
    "E108": book.check_display_fractions,
}


def findings(source):
    return check_document(Document("paper.tex", source),
                          frozenset(book.STYLE_RULE_IDS.values()))


def legacy_pairs(source):
    aliases = {rule: legacy for legacy, rule in book.STYLE_RULE_IDS.items()}
    return sorted((v.line, aliases[v.rule_id]) for v in findings(source))


class SharedBookRules(unittest.TestCase):
    def test_rules_reach_the_normal_checker_and_guide(self):
        source = "\\section{Bad Heading}\n$x_1,\\ldots,x_n$\n\\[ a/b \\]"
        self.assertEqual({rule_id for _, rule_id in legacy_pairs(source)},
                         {"E105", "E107", "E108"})
        for rule_id in book.STYLE_RULE_IDS.values():
            self.assertIn(f"**{rule_id}**", render())
        self.assertIn("small-explicit-constants", REGISTRY)
        self.assertNotIn("E104", REGISTRY)
        self.assertNotIn("E104", book.RULES)

    def test_inline_and_script_fractions_are_checked(self):
        source = (
            r"$a/b$" "\n"
            r"\[ 2^{(n+1)/2}+\frac{a}{b}+\text{a/b} \]" "\n"
            r"\[ \begin{bmatrix} 1 & \cdots & 1 \end{bmatrix} \]"
        )
        self.assertEqual(legacy_pairs(source), [(1, "E108"), (2, "E108")])

    def test_examples_do_not_become_prose_findings(self):
        source = (
            "\\begin{verbatim}\n\\section{Bad Heading}\n"
            "$x_1,\\ldots,x_n$\n\\[ a/b \\]\n\\end{verbatim}\n"
            "\\[ c/d \\]"
        )
        self.assertEqual(legacy_pairs(source), [(6, "E108")])

    def test_nested_align_punctuation_is_checked(self):
        source = "\n".join([
            r"\[", r"\begin{aligned}", r"a &= b, \\",
            r"c &= d", r"\end{aligned}", r"\]",
        ])
        self.assertEqual(legacy_pairs(source), [(3, "E102")])

    def test_comments_do_not_supply_punctuation_or_relations(self):
        source = "\\[\nx=y % z=a=b.\n\\]"
        self.assertEqual(findings(source), [])

    def test_fuzz_book_and_registry_use_the_same_detectors(self):
        rng = random.Random(104108)
        fragments = [
            r"\section{Expected cost}", r"\section{Expected Cost}",
            r"\chapter{Expected cost}", r"\chapter{Expected Cost}",
            r"$x_1,\ldots,x_n$", r"$(x_i)_{i\in[n]}$",
            r"\[ a/b \]", r"\[ \frac{a}{b} \]",
            r"\[ 2^{n/2} \]", r"\[ \text{a/b} \]",
            r"\[ \begin{pmatrix} 1 & \cdots & 1 \end{pmatrix} \]",
            r"% \section{Not a Heading} \[ a/b \]",
            "", r"\[", r"\]", "{", "}", r"\frac", r"\section",
            r"\[ a=b=c \]", r"\[ x=y. \]", r"$a=b=c$",
        ]
        for _ in range(150):
            source = "\n".join(rng.choices(fragments, k=rng.randrange(1, 20)))
            expected = sorted(
                (line, rule_id)
                for check in SHARED.values()
                for line, rule_id, _ in check(source)
            )
            actual = legacy_pairs(source)
            self.assertEqual(actual, expected)
            self.assertTrue(all(1 <= line <= source.count("\n") + 1
                                for line, _ in actual))


if __name__ == "__main__":
    unittest.main()
