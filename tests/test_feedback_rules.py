"""Regressions from annotated mathematical prose and literal-syntax controls."""

import unittest

from styleck import Document, check_document


def findings(text, rule, path="paper.tex"):
    return check_document(Document(path, text), only=frozenset({rule}))


class FeedbackRulesTests(unittest.TestCase):
    def test_gerund_subjects_from_eopl_feedback(self):
        for source in (
            r"Deleting $L_T$ exposes the crossing heads.",
            r"Following $P$ recovers a source.",
            "Using fewer bits simplifies the construction.",
            r"Applying Lemma~\ref{lem:one} gives the bound.",
            r"Applying \eqref{eq:bound} proves the lemma.",
            r"Encoding each case with $O(h)$ variables lets us apply the lemma.",
            "Removing vertices from the graph\nreduces its size.",
            "Fix the graph. Counting its vertices gives the answer.",
            r"\begin{proof} Sorting the labels uses $O(k^2m)$ gates.\end{proof}",
            r"\caption{Deleting $L_T$ exposes two sources.}",
        ):
            with self.subTest(source=source):
                self.assertEqual(len(findings(source, "gerund-subject")), 1)

    def test_gerunds_are_not_a_blanket_ban(self):
        for source in (
            r"Delete $L_T$. The crossing heads become sources.",
            r"Using $P$, we recover a source.",
            r"Assuming $n$ is positive, apply the lemma.",
            "Remaining vertices have degree two.",
            "String matching is polynomial.",
            r"\section{Finding an endpoint from an empty cut}",
            r"\section{Removing vertices reduces the dimension}",
            r"\paragraph{Sorting the labels uses few gates.}",
            r"\texttt{Removing vertices reduces the dimension.}",
            "% Removing vertices reduces the dimension.",
            r"$\text{Removing vertices reduces the dimension.}$",
        ):
            with self.subTest(source=source):
                self.assertEqual(findings(source, "gerund-subject"), [])
        self.assertEqual(findings(
            "# Removing vertices reduces the dimension\n\nUse the smaller graph.",
            "gerund-subject", "paper.md",
        ), [])

    def test_descriptions_without_the_existing_symbols(self):
        for phrase in (
            "the predecessor and successor circuits", "these circuits",
            "the incoming-edge and outgoing-edge indicators", "the supplied pointer circuits",
            "this formulation", "the named subcircuits",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(findings(phrase + " suffice.", "vague-referent"))
        for source in (
            r"Use the circuits $P,S$.",
            r"Use the construction in Lemma~\ref{lem:cut}.",
            r"Use the self-pointer formulation~\eqref{eq:standard}.",
            r"Use the SAT algorithms of~\cite[Section 2]{sat}.",
            "Algorithms that inspect polynomial-size circuit descriptions can help.",
            "Solve the general circuit-counting problem.",
            r"\section{The supplied pointer circuits}",
            "% these circuits\n$\text{these circuits}$",
        ):
            with self.subTest(source=source):
                self.assertEqual(findings(source, "vague-referent"), [])

    def test_named_and_wordy_conditions_from_pdf_notes(self):
        self.assertEqual(len(findings("Retain the named subcircuits.", "named-reference")), 1)
        self.assertEqual(findings(r"Retain $P_0,S_0,H$.", "named-reference"), [])
        for source in ("% named subcircuits", r"\texttt{named}", r"$\text{named}$"):
            with self.subTest(source=source):
                self.assertEqual(findings(source, "named-reference"), [])
        self.assertTrue(findings(r"A zero value of $H(x)$ leaves an edge.", "wordy-math-condition"))
        self.assertEqual(findings(r"When $H(x)=0$, keep the edge.", "wordy-math-condition"), [])
        self.assertTrue(findings("Exact counting supplies decision.", "proof-step-action"))

    def test_clause_separators_from_feedback(self):
        source = (
            "The algorithm need not identify this $k$: its existence suffices.\n"
            "Let $x=0$; then return the empty set.\n"
            "The theorem uses this assumption; its probability is over the input."
        )
        reports = findings(source, "prose-clause-separator")
        self.assertEqual([report.line for report in reports], [1, 2, 3])
        self.assertEqual(source[reports[0].column - 1], ":")

    def test_literal_syntax_and_labels_are_not_clauses(self):
        source = r"""\section{Algorithms: correctness and complexity}
Input: a graph and an integer

See \ref{eq:the bound} and \url{https://example.com/a;b}.
Let $S=\{x: x>0\}$ and $f(x;y)=x+y$.
The estimate is
\[f(x;y)=x:y\]
We use the following facts:
\begin{itemize}
\item Every set is finite
\end{itemize}
We obtain:
\[x=y\]
The graph satisfies these conditions:
\begin{conditions}{T}
\item All vertices have degree two
\end{conditions}
The theorem has the following consequence:
\begin{corollary} The graph is bipartite. \end{corollary}
Define the problem as follows:
\npprob[\pagewidth]{\pclique}{A graph $G$}{$k$}{Find a clique}
"""
        self.assertEqual(findings(source, "prose-clause-separator"), [])
        markdown = "# Algorithms: correctness and complexity\n\n`x; y` and `a: b`."
        self.assertEqual(findings(markdown, "prose-clause-separator", "paper.md"), [])

    def test_caption_labels_do_not_inherit_command_names(self):
        source = r"""\begin{figure}
\centering
\input{figures/characters.tex}
\caption{Left: each element has $s$ preimages. Right: the character terms align.}
\end{figure}
"""
        self.assertEqual(findings(source, "prose-clause-separator"), [])
        clause = r"\caption{The terms align: their phases agree.}"
        self.assertEqual(len(findings(clause, "prose-clause-separator")), 1)

    def test_named_bounds_describe_an_application(self):
        bad = (
            "A Chernoff bound limits the probability.",
            "The Chernoff bound gives the estimate.",
            "We use a multiplicative Chernoff bound.",
            "A union bound over all choices gives the claim.",
        )
        for source in bad:
            with self.subTest(source=source):
                self.assertEqual(len(findings(source, "apply-named-bound")), 1)
        good = (
            r"Apply the Chernoff bound to obtain $p\le e^{-n}$.",
            r"Applying the Chernoff bound gives $p\le e^{-n}$.",
            "By the union bound, the event has probability at most one half.",
            "We prove a new concentration bound.",
        )
        for source in good:
            with self.subTest(source=source):
                self.assertEqual(findings(source, "apply-named-bound"), [])
                self.assertEqual(findings(source, "vague-referent"), [])

    def test_actions_and_overhead_from_feedback(self):
        source = (
            "Simulation reaches its completion within a fixed polynomial overhead "
            "of its running time. Its existence proves the estimate. "
            "The completeness guarantee then supplies a graph. "
            "This step is an application of the lemma."
        )
        self.assertEqual(len(findings(source, "proof-step-action")), 4)
        self.assertEqual(len(findings(source, "polynomial-overhead")), 1)
        self.assertEqual(findings("The graph is bipartite.", "proof-step-action"), [])
        self.assertEqual(findings(r"The polynomial overhead is $O(T^2)$.", "polynomial-overhead"), [])
        self.assertEqual(findings(r"The simulation has polynomial overhead $O(T^2)$.", "polynomial-overhead"), [])

    def test_slash_fractions_in_every_math_context(self):
        source = r"""$1/2$, $s/4$, and $g(k)/h(k)$
\(n^{1/k}+a_{s/4}\)
\[\frac{a/b}{c}+x\slash y\]
"""
        reports = findings(source, "math-fraction")
        self.assertEqual([report.line for report in reports], [1, 1, 1, 2, 2, 3, 3])
        typeset = r"$\frac{1}{2}+n^{\sfrac{1}{k}}+a_{\frac{s}{4}}$"
        self.assertEqual(findings(typeset, "math-fraction"), [])
        literals = r"$\text{and/or}+\ref{eq:a/b}+\url{https://example.com/a/b}$"
        self.assertEqual(findings(literals, "math-fraction"), [])
