"""Reference evidence for mathematical terminology, separate from the target."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

from .config import config_chain
from .document import DISPLAY, INLINE, Document
from .linguistics import (Phrase, VocabularySetupError, analyze, mathematical_contexts,
                          phrase_key, prose_text, word_family)
from .math_dictionary import modifier_heads, senses, usage
from .terms import background_terms, introduced_terms
from .word_senses import best_sense

MODEL_PATH = Path(__file__).with_name("data") / "vocabulary.json"
MIN_USES = 4
MIN_DOCUMENTS = 3


def fingerprint(text: str) -> str:
    normalized = " ".join(text.casefold().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


@lru_cache(maxsize=16)
def _load(path: str, modified: int):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != 1:
        raise VocabularySetupError(f"unsupported vocabulary model: {path}")
    return data


def _read_model(path: Path):
    try:
        return _load(str(path), path.stat().st_mtime_ns)
    except (OSError, ValueError) as error:
        raise VocabularySetupError(f"cannot load vocabulary model {path}: {error}") from error


def configuration(path: str):
    profiles = None
    models = [MODEL_PATH]
    for file in config_chain(path, ".styleck-vocabulary"):
        try:
            config = json.loads(file.read_text(encoding="utf-8"))
            if not isinstance(config, dict):
                raise ValueError("expected a JSON object")
            if "profiles" in config:
                if not isinstance(config["profiles"], list) or not all(isinstance(x, str) for x in config["profiles"]):
                    raise ValueError("profiles must be a list of names")
                profiles = set(config["profiles"])
            if not isinstance(config.get("models", []), list) or not all(isinstance(x, str) for x in config.get("models", [])):
                raise ValueError("models must be a list of paths")
            models.extend(file.parent / name for name in config.get("models", []))
        except (OSError, ValueError, TypeError) as error:
            raise VocabularySetupError(f"invalid vocabulary configuration {file}: {error}") from error
    loaded = [_read_model(path) for path in dict.fromkeys(models)]
    available = {source["profile"] for model in loaded for source in model["sources"]}
    if profiles is not None and profiles - available:
        raise VocabularySetupError("unknown vocabulary profiles: " + ", ".join(sorted(profiles - available)))
    return profiles, loaded


def definitions(document: Document) -> set[str]:
    """Explicit markings and narrow naming constructions, not arbitrary 'is'."""
    visible = document.prose_mask()
    result = {phrase_key(term) for term in introduced_terms(visible)}
    titles = re.finditer(r"\\begin\{definition\}\s*\[([A-Za-z][A-Za-z -]+)\]", visible)
    result.update(phrase_key(match[1]) for match in titles)
    result.update(phrase_key(term) for term in background_terms(document.path))
    prose = prose_text(document)
    word = r"[A-Za-z]+(?:-[A-Za-z]+)*"
    # “A vertex is heavy if ...” defines the phrase “heavy vertex”.
    predicate = re.compile(
        rf"\b(?:a|an|the)\s+({word}(?:\s+{word}){{0,2}})\s+is\s+"
        rf"({word})\s+(?:if|when|whenever|iff)\b", re.I)
    result.update(phrase_key(f"{match[2]} {match[1]}") for match in predicate.finditer(prose))
    # “We call a vertex heavy if ...” has the same effect.
    naming = re.compile(
        rf"\bcall\s+(?:a|an|the|these|those)\s+({word}(?:\s+{word}){{0,2}})\s+"
        rf"({word})\s+(?:if|when|whenever|iff)\b", re.I)
    result.update(phrase_key(f"{match[2]} {match[1]}") for match in naming.finditer(prose))
    called = re.compile(
        rf"\b(?:called|termed|named)\s+(?:an?\s+)?"
        rf"({word}(?:\s+{word}){{0,3}}?)\s+(?:if|when|whenever|iff|provided)\b", re.I)
    result.update(phrase_key(match[1]) for match in called.finditer(prose))
    nominal = re.compile(
        rf"\b(?:a|an)\s+({word}(?:\s+{word}){{0,3}})\s+(?:is|means|denotes)\s+(?:a|an)\s+{word}", re.I)
    result.update(phrase_key(match[1]) for match in nominal.finditer(prose))
    explicit = re.compile(
        rf"\b(?:define|refer\s+to)\s+(?:a\s+|an\s+|the\s+)?"
        rf"({word}(?:\s+{word}){{0,3}}?)\s+as\b", re.I)
    result.update(phrase_key(match[1]) for match in explicit.finditer(prose))
    return result


def declared(key: str, vocabulary: set[str]) -> bool:
    if key in vocabulary:
        return True
    words = key.split()
    for term in vocabulary:
        other = term.split()
        if len(other) == len(words) and all(
                left == right or right in word_family(left) for left, right in zip(words, other)):
            return True
    # An explicitly defined adjective may name a class of an established object.
    return (len(words) == 2 and words[0] in vocabulary
            and bool(mathematical_contexts(words[1])))


def similarity(left, right, frequencies, document_count) -> float:
    if not left or not right:
        return 0.0
    left, right = set(left), set(right)
    weights = {word: math.log((document_count + 1) / (frequencies.get(word, 0) + 1)) ** 2
               for word in left | right}
    product = sum(weights[word] for word in left & right)
    norm = (sum(weights[word] for word in left) * sum(weights[word] for word in right)) ** 0.5
    return product / norm if norm else 0.0


def productive_modifiers(sources):
    heads = defaultdict(lambda: defaultdict(set))
    documents = defaultdict(lambda: defaultdict(set))
    for source in sources:
        for key in source["terms"]:
            words = key.split()
            if len(words) == 2:
                heads[source["profile"]][words[0]].add(words[1])
                documents[source["profile"]][words[0]].add(source["sha256"])
    return {profile: sorted(word for word, values in entries.items()
                            if len(values) >= 6 and len(documents[profile][word]) >= 4)
            for profile, entries in heads.items()}


class Evidence:
    def __init__(self, document: Document, candidates: list[Phrase]):
        selected, models = configuration(document.path)
        digest = fingerprint(prose_text(document))
        target = Path(document.path).resolve().as_posix()
        self.contexts = defaultdict(list)
        self.support = defaultdict(set)
        self.general = {}
        self.modifiers = set()
        self.profiles = set()
        self.defined = defaultdict(set)
        self.general_documents = 1
        self.context_documents = Counter()
        seen = set()
        active = []
        keys = {item.key for item in candidates}
        for model in models:
            self.general_documents = max(self.general_documents, model["general_documents"])
            for word, count in model.get("context_documents", {}).items():
                self.context_documents[word] = max(count, self.context_documents[word])
            for key, value in model["general"].items():
                if value[0] > self.general.get(key, [0])[0]:
                    self.general[key] = value
            profiles = selected if selected is not None else self._infer(model, keys)
            self.profiles.update(profiles)
            for source in model["sources"]:
                members = [(source["path"], source["sha256"]), *source.get("members", [])]
                if (source["profile"] not in profiles or source["sha256"] in seen
                        or any(sha == digest or target.endswith("/" + path) for path, sha in members)):
                    continue
                seen.add(source["sha256"])
                active.append(source)
                for key, entry in source["terms"].items():
                    self.support[key].add(source["sha256"])
                    self.contexts[key].append(frozenset(entry[1]))
                    if entry[2]:
                        self.defined[key].add(source["sha256"])
        for modifiers in productive_modifiers(active).values():
            self.modifiers.update(modifiers)
        self.reference_count = len(seen)

    @staticmethod
    def _infer(model, keys):
        matched = defaultdict(Counter)
        totals = Counter(source["profile"] for source in model["sources"])
        for source in model["sources"]:
            matched[source["profile"]].update(key for key in source["terms"] if key in keys)
        selected = set()
        for profile, matches in matched.items():
            compounds = any(count >= MIN_DOCUMENTS and (" " in key or "-" in key)
                            for key, count in matches.items())
            enriched = sum(count >= MIN_DOCUMENTS and count / totals[profile]
                           > 4 * model["general"].get(key, [0])[0] / model["general_documents"]
                           for key, count in matches.items())
            if compounds or enriched >= 2:
                selected.add(profile)
        return selected

    def standard(self, key: str) -> bool:
        return (len(self.support[key]) >= MIN_DOCUMENTS or bool(mathematical_contexts(key))
                or bool(senses(key)) or usage(key) >= (1 if " " in key else MIN_DOCUMENTS))

    def mathematical(self, key: str) -> bool:
        subject_rate = len(self.support[key]) / max(1, self.reference_count)
        ordinary_rate = self.general.get(key, [0])[0] / self.general_documents
        enriched = len(self.support[key]) >= MIN_DOCUMENTS and subject_rate > 4 * ordinary_rate
        return (bool(mathematical_contexts(key)) or bool(senses(key))
                or len(self.defined[key]) >= 2 or enriched)

    def reason(self, uses: list[Phrase]) -> str | None:
        key, head = uses[0].key, uses[0].head
        context = set().union(*(item.context for item in uses))
        field_words = {word for word in context if self.mathematical(word)}
        math_uses = sum(item.near_math for item in uses)
        ordinary = self.general.get(key, [0, []])
        weights = self.context_documents, self.general_documents
        overlap = similarity(context, ordinary[1], *weights)
        field_overlap = max((similarity(context, example, *weights)
                             for example in self.contexts[key]), default=0.0)
        sense_overlap = max((similarity(context, example, *weights)
                             for example in mathematical_contexts(key)), default=0.0)
        if self.standard(key):
            if (senses(key) and math_uses >= MIN_USES and len(field_words) >= 2
                    and best_sense(key, context)[0] < 0.4):
                return "its use does not match the dictionary's established senses"
            return None
        modifiers = key.split()[:-1]
        if modifiers and self.standard(head) and all(
                word in self.modifiers or len(modifier_heads(word)) >= 4
                or best_sense(word, context | {head})[0] >= 0.75
                or best_sense(word, context | {head}, mathematical=True)[0] >= 0.6
                for word in modifiers):
            return None
        compound = bool(modifiers) or "-" in key
        mathematical = self.mathematical(head) or math_uses >= 2
        if not mathematical:
            return None
        if ordinary[0] >= MIN_DOCUMENTS:
            # A common word only merits a warning when its mathematical use differs
            # from the ordinary contexts, with repeated evidence beyond proximity.
            if (self.standard(head) or math_uses < 2 or len(field_words) < 2
                    or max(overlap, field_overlap) >= 0.15 or best_sense(key, context)[0] >= 0.75):
                return None
            return "its repeated mathematical use differs from the ordinary reference contexts"
        if compound and (self.standard(head) or (math_uses >= 2 and len(field_words) >= 2)):
            return "a repeated mathematical object has an unexplained classifier"
        if math_uses >= 2 and field_words:
            return "its repeated mathematical use has little support in the reference texts"
        return None


def findings(document: Document):
    prose, candidates = analyze(document)
    groups = defaultdict(list)
    for candidate in candidates:
        groups[candidate.key].append(candidate)
    repeated = {key: uses for key, uses in groups.items() if len(uses) >= MIN_USES}
    if not repeated:
        return
    evidence = Evidence(document, candidates)
    vocabulary = definitions(document)
    declared_keys = {key for key in groups if declared(key, vocabulary)}
    introduced_spans = [(item.start, item.end) for key in declared_keys for item in groups[key]]
    accepted = []
    for key, uses in repeated.items():
        if key in declared_keys:
            continue
        uses = [item for item in uses if not any(left <= item.start and item.end <= right
                                                for left, right in introduced_spans)]
        if len(uses) < MIN_USES:
            continue
        reason = evidence.reason(uses)
        if reason:
            accepted.append((uses, reason))
    # Report the full repeated phrase once, rather than each constituent word.
    accepted.sort(key=lambda item: (-len(item[0][0].key.split()), item[0][0].start))
    covered = set()
    for uses, reason in accepted:
        if all((item.start, item.end) in covered for item in uses):
            continue
        first = uses[0]
        yield first.start, " ".join(document.text[first.start:first.end].split()), len(uses), reason
        for item in uses:
            covered.update((candidate.start, candidate.end) for candidate in candidates
                           if item.start <= candidate.start and candidate.end <= item.end)
