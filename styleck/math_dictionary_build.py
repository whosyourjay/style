"""Extract mathematical senses and inflections from Wiktextract JSONL."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

SOURCE = ("https://kaikki.org/dictionary/English/topics/yQ/mathematics/"
          "kaikki.org-dictionary-English-topic-mathematics.jsonl")
TOPICS = {"mathematics", "computing", "logic"}


def normalize(word):
    return " ".join(word.casefold().split())


def selected_senses(entry):
    if entry.get("pos") not in {"noun", "adj", "verb", "adv", "phrase"}:
        return []
    senses = []
    for sense in entry.get("senses", []):
        if not TOPICS.intersection(sense.get("topics", [])):
            continue
        gloss = " ".join(sense.get("glosses", []))
        if not gloss or sense.get("form_of") or "form-of" in sense.get("tags", []):
            continue
        record = {"pos": entry["pos"], "gloss": gloss,
                  "topics": sorted(sense.get("topics", []))}
        if sense.get("raw_tags"):
            record["qualifiers"] = sense["raw_tags"]
        senses.append(record)
    return senses


def compile_dictionary(stream, origin, deadline):
    entries = defaultdict(list)
    forms = defaultdict(set)
    digest = hashlib.sha256()
    count = 0
    for line in stream:
        if time.monotonic() > deadline:
            raise TimeoutError("dictionary processing exceeded its time limit")
        digest.update(line)
        entry = json.loads(line)
        count += 1
        word = normalize(entry.get("word", ""))
        if not word:
            continue
        for sense in selected_senses(entry):
            if sense not in entries[word]:
                entries[word].append(sense)
        if word in entries:
            for form in entry.get("forms", []):
                spelling = normalize(form.get("form", ""))
                if spelling and spelling != word:
                    forms[spelling].add(word)
        for sense in entry.get("senses", []):
            for parent in sense.get("form_of", []):
                if parent.get("word"):
                    forms[word].add(normalize(parent["word"]))
    return {"schema": 1, "source": origin, "source_sha256": digest.hexdigest(),
            "source_entries": count,
            "attribution": "English Wiktionary contributors; Wiktextract / Kaikki.org",
            "license": "https://creativecommons.org/licenses/by-sa/4.0/",
            "entries": dict(sorted(entries.items())),
            "forms": {word: sorted(parents & entries.keys()) for word, parents in sorted(forms.items())
                      if parents & entries.keys()}}


def build(source, seconds):
    deadline = time.monotonic() + seconds
    if source.startswith("https://"):
        request = urllib.request.Request(source, headers={"Accept-Encoding": "gzip", "User-Agent": "styleck"})
        with urllib.request.urlopen(request, timeout=5) as response:
            stream = gzip.GzipFile(fileobj=response) if response.headers.get("Content-Encoding") == "gzip" else response
            return compile_dictionary(stream, source, deadline)
    with Path(source).open("rb") as stream:
        return compile_dictionary(stream, str(Path(source).resolve()), deadline)


def merge_dictionaries(left, right):
    entries = left["entries"]
    forms = left["forms"]
    for word, values in right["entries"].items():
        entries[word] = [*entries.get(word, []), *(sense for sense in values if sense not in entries.get(word, []))]
    for word, values in right["forms"].items():
        forms[word] = sorted(set(forms.get(word, [])) | set(values))
    sources = left.get("sources", [{"url": left["source"], "sha256": left["source_sha256"]}])
    sources.append({"url": right["source"], "sha256": right["source_sha256"]})
    left["sources"] = sources
    left["source_entries"] += right["source_entries"]
    return left


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", help="Wiktextract JSONL URL or local file; repeat to combine")
    parser.add_argument("--merge", type=Path, help="extend an existing generated dictionary")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-seconds", type=float, default=50)
    args = parser.parse_args()
    data = json.loads(args.merge.read_text()) if args.merge else None
    deadline = time.monotonic() + args.max_seconds
    for source in args.source or [SOURCE]:
        additional = build(source, max(0, deadline - time.monotonic()))
        data = merge_dictionaries(data, additional) if data is not None else additional
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    print(f"Extracted {len(data['entries'])} mathematical entries and {len(data['forms'])} inflections")


if __name__ == "__main__":
    main()
