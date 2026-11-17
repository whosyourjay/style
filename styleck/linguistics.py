"""Offset-preserving phrases and dictionary-backed morphology."""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from functools import lru_cache

from .document import DISPLAY, INLINE, Document
from .math_dictionary import senses
from .tex_args import braced_arg_at, optional_arg_at

WORD = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)*-?\Z")
COMPOUND = re.compile(r"\b[A-Za-z]+(?:-[A-Za-z]+)+\b|\b[A-Za-z]+-(?=\s+(?:or|and)\b)")
COMMAND = re.compile(r"\\([A-Za-z@]+\*?|.)")
TEXT_COMMANDS = frozenset({"term", "deftext", "emph", "textit", "textbf", "textrm", "textsc", "textsf"})


class VocabularySetupError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def resources():
    try:
        from nltk.corpus import wordnet
        wordnet.ensure_loaded()
        return (wordnet,)
    except (ImportError, LookupError) as error:
        raise VocabularySetupError(
            "terminology checks require NLTK's dictionary; install requirements.txt, "
            "then run python3 -m nltk.downloader wordnet"
        ) from error


@lru_cache(maxsize=1)
def parser():
    try:
        # The parser is local. urllib3's TLS warning is unrelated to loading it.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*", module="urllib3")
            import spacy
        return spacy.load("en_core_web_md", exclude=["ner"])
    except (ImportError, OSError) as error:
        raise VocabularySetupError(
            "terminology checks require spaCy's English model; install requirements.txt"
        ) from error


@lru_cache(maxsize=32768)
def lemma(word: str, pos: str = "n") -> str:
    """Keep unknown spellings; never manufacture a shorter stem."""
    word = word.casefold()
    if "-" in word:
        parts = word.split("-")
        return "-".join([*parts[:-1], lemma(parts[-1], pos)])
    return resources()[0].morphy(word, pos) or word


def phrase_key(text: str) -> str:
    words = text.casefold().split()
    if words:
        words[-1] = lemma(words[-1])
    return " ".join(words)


@lru_cache(maxsize=8192)
def word_family(word: str) -> frozenset[str]:
    """Direct dictionary derivations, not synonyms or guessed suffixes."""
    wordnet = resources()[0]
    found = {lemma(word, pos) for pos in ("n", "v", "a", "r")}
    for synset in wordnet.synsets(word):
        for entry in synset.lemmas():
            if entry.name().casefold() not in found:
                continue
            found.update(item.name().casefold().replace("_", " ")
                         for item in entry.derivationally_related_forms())
    return frozenset(found)


def observed_variants(term: str, prose: str) -> set[str]:
    """Inflected spellings actually present in the document."""
    words = term.split()
    if not words:
        return {term}
    head = lemma(words[-1])
    return {term} | {
        " ".join([*words[:-1], match.group(0)])
        for match in re.finditer(r"[A-Za-z]+(?:-[A-Za-z]+)*", prose)
        if lemma(match.group(0)) == head
    }


def prose_text(document: Document) -> str:
    """Retain text arguments, but mask TeX identifiers and optional arguments."""
    text = list(document.prose_mask())
    source = "".join(text)
    for match in COMMAND.finditer(source):
        name = match.group(1).rstrip("*")
        end = match.end()
        if name not in TEXT_COMMANDS:
            _, end = optional_arg_at(source, end)
            _, end = braced_arg_at(source, end)
            if name == "begin":
                _, end = optional_arg_at(source, end)
        text[match.start():end] = " " * (end - match.start())
    return "".join(text).translate(str.maketrans({"{": " ", "}": " ", "~": " "}))


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int
    tag: str
    sentence: int = 0
    is_math: bool = False
    pos: str = ""
    dependency: str = ""

    @property
    def key(self) -> str:
        pos = {"J": "a", "V": "v", "R": "r"}.get(self.tag[:1], "n")
        return lemma(self.text, pos)


def tokenized(nlp, text):
    parsed = nlp.make_doc(text)
    compounds = [parsed.char_span(match.start(), match.end()) for match in COMPOUND.finditer(text)]
    with parsed.retokenize() as retokenizer:
        for span in compounds:
            if span is not None and len(span) > 1:
                retokenizer.merge(span)
    return parsed


def tokens(text: str, math_spans=()) -> list[Token]:
    analysis = list(text)
    for span in math_spans:
        analysis[span.start] = "X"
    nlp = parser()
    parsed = nlp(tokenized(nlp, "".join(analysis)))
    result = []
    math_index = 0
    for sentence, span in enumerate(parsed.sents):
        for token in span:
            if token.is_space:
                continue
            start, end = token.idx, token.idx + len(token)
            while math_index < len(math_spans) and math_spans[math_index].end <= start:
                math_index += 1
            mathematical = math_index < len(math_spans) and math_spans[math_index].start < end
            if mathematical:
                end = max(end, math_spans[math_index].end)
            word = token.text
            if (word.endswith("-") and token.i + 2 < len(parsed)
                    and parsed[token.i + 1].text in {"or", "and"} and "-" in parsed[token.i + 2].text):
                word += parsed[token.i + 2].text.split("-", 1)[1]
            result.append(Token(word, start, end, token.tag_, sentence, mathematical,
                                token.pos_, token.dep_))
    return result


def analyze(document: Document):
    prose = prose_text(document)
    mathematics = [span for span in document.spans_of(INLINE, DISPLAY)
                   if span.start >= document.body_start]
    return prose, phrases(tokens(prose, mathematics), mathematics, prose)


@dataclass(frozen=True)
class Phrase:
    key: str
    start: int
    end: int
    head: str
    context: frozenset[str]
    near_math: bool = False


@lru_cache(maxsize=4096)
def content_compound(word: str) -> bool:
    """Function-word prefixes do not introduce an unexplained classifier."""
    if "-" not in word:
        return True
    tagged = parser()(word.replace("-", " "), disable=["parser", "lemmatizer"])
    return any(token.pos_ not in {"DET", "INTJ", "CCONJ", "ADP", "PART"} for token in tagged[:-1])


def phrases(tagged: list[Token], math_spans=(), source: str = "") -> list[Phrase]:
    """Noun phrases and their suffixes, with sentence-local usage features."""
    result = []
    math_index = 0
    for i, head in enumerate(tagged):
        noun = head.pos in {"NOUN", "PROPN"} if head.pos else head.tag.startswith("NN")
        # English taggers often call a nominal participle (e.g. a matching) a verb.
        if not noun and head.tag in {"VBG", "VBN"} and senses(lemma(head.text), "noun") and i:
            previous = tagged[i - 1]
            noun = previous.sentence == head.sentence and (
                previous.tag == "DT" or previous.dependency in {"compound", "amod"}
                or (previous.pos in {"NOUN", "ADJ"} and i + 1 < len(tagged)
                    and tagged[i + 1].text.casefold() == "of"))
        if (head.is_math or not noun or not WORD.fullmatch(head.text)
                or head.text.isupper() or not content_compound(head.text)):
            continue
        while math_index < len(math_spans) and math_spans[math_index].end <= head.end:
            math_index += 1
        near_math = False
        if math_index < len(math_spans):
            distance = math_spans[math_index].start - head.end
            bridge = source[head.end:math_spans[math_index].start]
            near_math = (0 <= distance < 40 and bool(re.fullmatch(
                r"\s*(?:(?:of|in|on|for|at|with)\s*)?", bridge)))
        left = i
        while left > max(0, i - 3):
            previous = tagged[left - 1]
            gap = source[previous.end:tagged[left].start]
            if (previous.is_math or previous.sentence != head.sentence
                    or not (previous.pos == "ADJ" or previous.tag.startswith(("NN", "JJ"))
                            or previous.dependency == "amod")
                    or not WORD.fullmatch(previous.text)
                    or (source and (len(gap) > 40 or re.search(r"\n\s*\n", gap)))):
                break
            left -= 1
        for first in range(left, i + 1):
            content = tagged[first:i + 1]
            context = set()
            for step, origin in ((-1, first - 1), (1, i + 1)):
                for j in range(origin, origin + step * 7, step):
                    if (not 0 <= j < len(tagged) or tagged[j].sentence != head.sentence
                            or tagged[j].text in {".", "!", "?", ";"}):
                        break
                    if (not tagged[j].is_math and tagged[j].tag.startswith(("NN", "JJ", "VB"))
                            and WORD.fullmatch(tagged[j].text)):
                        context.add(tagged[j].key)
            key = " ".join([*(token.text.casefold() for token in content[:-1]), lemma(head.text)])
            result.append(Phrase(key, content[0].start, head.end, lemma(head.text),
                                 frozenset(context), near_math))
    return result


@lru_cache(maxsize=1)
def mathematical_domains():
    wordnet = resources()[0]
    roots = [wordnet.synset("mathematics.n.01"), wordnet.synset("computer_science.n.01")]
    domains = set(roots)
    for root in roots:
        domains.update(root.closure(lambda item: item.hyponyms()))
    return frozenset(domains)


@lru_cache(maxsize=8192)
def mathematical_contexts(term: str) -> tuple[frozenset[str], ...]:
    """WordNet's subject-labelled mathematical senses, including inherited ones."""
    domains = mathematical_domains()
    result = []
    for synset in resources()[0].synsets(term.replace(" ", "_"), pos="n"):
        ancestors = {synset, *synset.closure(lambda item: item.hypernyms(), depth=3)}
        if not any(item in domains or domains.intersection(item.topic_domains())
                   for item in ancestors):
            continue
        result.append(frozenset(lemma(word) for word in re.findall(r"[A-Za-z]+", synset.definition())))
    return tuple(result)
