"""Mathematical dictionary senses, distinct from general English membership."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).with_name("data") / "mathematical-senses.json"
USAGE_PATH = PATH.with_name("mathematical-usage.json")


@lru_cache(maxsize=2)
def _read(modified):
    data = json.loads(PATH.read_text(encoding="utf-8"))
    if data.get("schema") != 1:
        raise ValueError("unsupported mathematical dictionary format")
    return data


def data():
    return _read(PATH.stat().st_mtime_ns)


def senses(term, pos=None):
    dictionary = data()
    term = " ".join(term.casefold().split())
    keys = [term, *dictionary["forms"].get(term, [])]
    return tuple(sense for key in keys for sense in dictionary["entries"].get(key, [])
                 if pos is None or sense["pos"] == pos)


@lru_cache(maxsize=2)
def _usage(modified):
    return json.loads(USAGE_PATH.read_text(encoding="utf-8"))


def usage(term):
    return _usage(USAGE_PATH.stat().st_mtime_ns)["phrases"].get(term, 0)


def modifier_heads(term):
    return _usage(USAGE_PATH.stat().st_mtime_ns).get("modifier_heads", {}).get(term, {})
