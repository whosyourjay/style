"""Generate subject profiles from reference documents, with source provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from functools import lru_cache

from .document import DISPLAY, INLINE, Document
from .linguistics import Token, analyze, lemma, phrase_key, phrases, prose_text
from .terms import introduced_terms
from .vocabulary import fingerprint, productive_modifiers

INPUT = re.compile(r"\\(?:input|include)\s*\{([^{}]+)\}")


@lru_cache(maxsize=512)
def source_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def inputs(path: Path, root: Path):
    visible = Document(str(path), source_text(path)).prose_mask()
    for match in INPUT.finditer(visible):
        candidate = path.parent / match[1]
        if not candidate.suffix:
            candidate = candidate.with_suffix(".tex")
        candidate = candidate.resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            yield match, candidate


def expanded(path: Path, root: Path, members: set[Path], stack=()) -> str:
    if path in stack:
        return ""
    members.add(path)
    text = source_text(path)
    for match, child in reversed(list(inputs(path, root))):
        text = text[:match.start()] + expanded(child, root, members, (*stack, path)) + text[match.end():]
    return text


def source_name(path: Path, root: Path) -> str:
    return str(Path(root.parent.name) / root.name / path.relative_to(root))


def common_context(counter, count):
    return [word for word, _ in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:count]]


def ordinary_prose():
    """Use Brown's supplied POS annotations; no model fitting on the target."""
    from nltk.corpus import brown
    counts = Counter()
    features = Counter()
    contexts = defaultdict(Counter)
    for source in brown.fileids():
        seen = set()
        seen_features = set()
        for sentence in brown.tagged_sents(source):
            tagged = [Token(word, i, i + 1, tag.split("-")[0])
                      for i, (word, tag) in enumerate(sentence)]
            for phrase in phrases(tagged):
                seen.add(phrase.key)
                contexts[phrase.key].update(phrase.context)
                seen_features.update(phrase.context)
        counts.update(seen)
        features.update(seen_features)
    return ({key: [count, common_context(contexts[key], 12)]
             for key, count in sorted(counts.items()) if count >= 3}, len(brown.fileids()),
            {word: count for word, count in sorted(features.items()) if count >= 3})


def shingles(text: str) -> frozenset[int]:
    words = text.casefold().split()
    hashes = {int.from_bytes(hashlib.sha256(" ".join(words[i:i + 5]).encode()).digest()[:8], "big")
              for i in range(max(0, len(words) - 4))}
    return frozenset(sorted(hashes)[:128])


def reference(path: Path, profile: str, root: Path):
    members = set()
    document = Document(str(path), expanded(path, root, members))
    text, candidates = analyze(document)
    names = {phrase_key(term) for term in introduced_terms(document.prose_mask())}
    counts = Counter()
    contexts = defaultdict(Counter)
    for phrase in candidates:
        counts[phrase.key] += 1
        contexts[phrase.key].update(phrase.context)
    terms = {key: [count, common_context(contexts[key], 8), key in names]
             for key, count in sorted(counts.items())}
    provenance = [[source_name(member, root), fingerprint(prose_text(Document(str(member), source_text(member))))]
                  for member in sorted(members)]
    return {"path": source_name(path, root), "profile": profile,
            "sha256": fingerprint(text), "members": provenance, "terms": terms}, shingles(text)


def collect(profiles):
    source_text.cache_clear()
    sources, signatures = [], []
    for profile, location in profiles:
        root = Path(location).resolve()
        files = sorted(root.rglob("*.tex")) if root.is_dir() else [root]
        base = root if root.is_dir() else root.parent
        children = {child for path in files for _, child in inputs(path, base)}
        roots = [path for path in files if path not in children]
        for path in roots or files[:1]:
            source, signature = reference(path, profile, base)
            if any(source["sha256"] == item["sha256"] for item in sources):
                continue
            if signature and any(len(signature & other) / max(len(signature), len(other)) >= 0.8
                                 for other in signatures):
                continue
            sources.append(source)
            signatures.append(signature)
    return sources


def compact(sources):
    """Retain cross-document evidence and definitions, not whole reference text."""
    counts = Counter(key for source in sources for key in source["terms"])
    for source in sources:
        source["terms"] = {key: entry for key, entry in source["terms"].items()
                           if counts[key] >= 2 or entry[2]}
    return productive_modifiers(sources)


def build(profiles):
    sources = collect(profiles)
    modifiers = compact(sources)
    general, general_documents, context_documents = ordinary_prose()
    return {"schema": 1, "generator": "styleck.vocabulary_build", "nltk": "3.9.2",
            "general_source": "Brown corpus (NLTK), document frequencies and context words",
            "morphology": "Princeton WordNet 3.0 via NLTK",
            "sources": sources, "modifiers": modifiers,
            "general": general, "general_documents": general_documents,
            "context_documents": context_documents}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", nargs=2, action="append", required=True,
                        metavar=("NAME", "REFERENCE_PATH"))
    parser.add_argument("--output", type=Path, help="write JSON here instead of stdout")
    args = parser.parse_args()
    model = build(args.profile)
    rendered = json.dumps(model, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
