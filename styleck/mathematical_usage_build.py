"""Count phrase usage across independent mathematical dictionary entries."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from .linguistics import WORD, lemma, parser as english_parser, tokenized
from .math_dictionary import PATH

def entry_phrases(document):
    result = set()
    words = [token for token in document if not token.is_space]
    for end, token in enumerate(words):
        if token.pos_ not in {"NOUN", "PROPN"} or not WORD.fullmatch(token.text):
            continue
        head = lemma(token.text)
        result.add(head)
        prefix = []
        for start in range(end - 1, max(-1, end - 4), -1):
            previous = words[start]
            if (not WORD.fullmatch(previous.text)
                    or not (previous.pos_ in {"NOUN", "PROPN", "ADJ"} or previous.tag_ in {"VBG", "VBN"})):
                break
            prefix.insert(0, previous.text.casefold())
            result.add(" ".join([*prefix, head]))
    return result


def build(path):
    raw = path.read_bytes()
    dictionary = json.loads(raw)
    counts = Counter()
    nlp = english_parser()
    documents = (tokenized(nlp, ". ".join(sense["gloss"] for sense in senses))
                 for senses in dictionary["entries"].values())
    for document in nlp.pipe(documents, disable=["parser", "lemmatizer"], batch_size=64):
        counts.update(entry_phrases(document))
    heads = defaultdict(dict)
    for phrase, count in counts.items():
        words = phrase.split()
        if len(words) == 2 and count >= 2:
            heads[words[0]][words[1]] = count
    # One entry contributes at most once, regardless of senses or inflections.
    return {"schema": 1, "source_sha256": hashlib.sha256(raw).hexdigest(),
            "source": dictionary.get("sources", dictionary["source"]), "attribution": dictionary["attribution"],
            "license": dictionary["license"], "entries": len(dictionary["entries"]),
            "phrases": dict(sorted(counts.items())),
            "modifier_heads": {word: dict(sorted(values.items())) for word, values in sorted(heads.items())}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=PATH)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build(args.source)
    args.output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(f"Recorded {len(result['phrases'])} recurring phrases across {result['entries']} mathematical entries")


if __name__ == "__main__":
    main()
