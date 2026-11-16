"""Offset-preserving phrases and dictionary-backed morphology."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from .document import Document
from .tex_args import braced_arg_at, optional_arg_at

WORD = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)*-?\Z")
COMMAND = re.compile(r"\\([A-Za-z@]+\*?|.)")
TEXT_COMMANDS = frozenset({"term", "deftext", "emph", "textit", "textbf", "textrm", "textsc", "textsf"})


class VocabularySetupError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def resources():
    try:
        from nltk.corpus import wordnet
        from nltk.tag import PerceptronTagger
        from nltk.tokenize import PunktTokenizer, TreebankWordTokenizer
        wordnet.ensure_loaded()
        return wordnet, PerceptronTagger(), TreebankWordTokenizer(), PunktTokenizer("english")
    except (ImportError, LookupError) as error:
        raise VocabularySetupError(
            "terminology checks require NLTK and its English resources; "
            "install requirements.txt, then run python3 -m nltk.downloader "
            "wordnet averaged_perceptron_tagger_eng punkt_tab"
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

    @property
    def key(self) -> str:
        pos = {"J": "a", "V": "v", "R": "r"}.get(self.tag[:1], "n")
        return lemma(self.text, pos)


def tokens(text: str) -> list[Token]:
    _, tagger, tokenizer, sentences = resources()
    result = []
    for begin, end in sentences.span_tokenize(text):
        spans = [(begin + left, begin + right)
                 for left, right in tokenizer.span_tokenize(text[begin:end])]
        words = [text[left:right] for left, right in spans]
        # Restore the shared head in “yes- or no-instances” without altering offsets.
        for i in range(len(words) - 2):
            if words[i].endswith("-") and words[i + 1] in {"or", "and"} and "-" in words[i + 2]:
                words[i] += words[i + 2].split("-", 1)[1]
        result.extend(Token(value, *span, tag)
                      for (value, tag), span in zip(tagger.tag(words), spans))
    return result


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
    tagged = resources()[1].tag(word.split("-"))
    return any(tag not in {"DT", "PDT", "UH", "CC", "IN", "TO"} for _, tag in tagged[:-1])


def phrases(tagged: list[Token], math_spans=(), source: str = "") -> list[Phrase]:
    """Noun phrases and their suffixes, with sentence-local usage features."""
    result = []
    math_index = 0
    for i, head in enumerate(tagged):
        if (not head.tag.startswith("NN") or not WORD.fullmatch(head.text)
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
            if not previous.tag.startswith(("NN", "JJ")) or not WORD.fullmatch(previous.text):
                break
            left -= 1
        for first in range(left, i + 1):
            content = tagged[first:i + 1]
            context = set()
            for step, origin in ((-1, first - 1), (1, i + 1)):
                for j in range(origin, origin + step * 7, step):
                    if not 0 <= j < len(tagged) or tagged[j].text in {".", "!", "?", ";"}:
                        break
                    if tagged[j].tag.startswith(("NN", "JJ", "VB")) and WORD.fullmatch(tagged[j].text):
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
