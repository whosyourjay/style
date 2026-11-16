"""Regression and generated cases for phrase-level mathematical vocabulary."""

from __future__ import annotations

import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from styleck.document import Document
from styleck.linguistics import lemma, prose_text, tokens
from styleck.vocabulary import Evidence, findings, fingerprint


def document(body: str, path="paper.tex"):
    return Document(path, "\\begin{document}\n" + body + "\n\\end{document}")


class TestMathematicalVocabulary(unittest.TestCase):
    def test_yes_and_suspended_compounds_keep_their_words(self):
        self.assertEqual(lemma("yes"), "yes")
        self.assertEqual(lemma("yes-instances"), "yes-instance")
        text = "The reduction returns a yes- or no-instance. " * 4
        tagged = tokens(text)
        self.assertIn("yes-instance", [item.key for item in tagged])
        self.assertNotIn("ye", [item.key for item in tagged])
        for item in tagged:
            self.assertEqual(text[item.start:item.end], item.text
                             if item.text != "yes-instance" else "yes-")
        self.assertEqual(list(findings(document(text))), [])

    def test_common_words_can_name_an_undefined_class(self):
        rng = random.Random(10419)
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "paper.tex")
            # Background knowledge of the head must not declare every modifier.
            (Path(folder) / ".styleck-terms").write_text("vertex\n")
            for _ in range(12):
                modifier = rng.choice(("copper", "velvet", "amber"))
                separator = rng.choice((" ", "\n", "  "))
                phrase = f"{modifier}{separator}vertices"
                body = f"The {phrase} of $G$ meet each vertex. " * rng.randrange(4, 8)
                found = list(findings(document(body, path)))
                self.assertTrue(any(item[1] == f"{modifier} vertices" for item in found))
                match = next(item for item in found if item[1] == f"{modifier} vertices")
                self.assertEqual(document(body, path).text[match[0]:match[0] + len(modifier)], modifier)
                defined = f"A \\deftext{{{modifier} vertex}} has the stated property. " + body
                self.assertEqual(list(findings(document(defined, path))), [])
                named = f"A vertex is {modifier} if it has the stated property. " + body
                self.assertEqual(list(findings(document(named, path))), [])

    def test_reference_support_excludes_self_and_duplicate_documents(self):
        target = document("A copper vertex of $G$ meets its neighbor.")
        digest = fingerprint(prose_text(target))
        entries = {"copper vertex": [4, ["vertex", "graph"], False]}
        model = {"general": {}, "general_documents": 500, "sources": [
            {"profile": "fixture", "path": "copy.tex", "sha256": digest, "terms": entries},
            {"profile": "fixture", "path": "paper.tex", "sha256": "old revision", "terms": entries},
            {"profile": "fixture", "path": "book.tex", "sha256": "containing document", "terms": entries,
             "members": [["paper.tex", "older revision"]]},
            {"profile": "fixture", "path": "reference.tex", "sha256": "independent", "terms": entries},
            {"profile": "fixture", "path": "duplicate.tex", "sha256": "independent", "terms": entries},
        ]}
        with patch("styleck.vocabulary.configuration", return_value=({"fixture"}, [model])):
            evidence = Evidence(target, [])
        self.assertEqual(evidence.support["copper vertex"], {"independent"})


if __name__ == "__main__":
    unittest.main()
