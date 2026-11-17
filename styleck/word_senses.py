"""Compare local use with dictionary senses without exposing the source text."""

from __future__ import annotations

import re
from functools import lru_cache

from .linguistics import parser, resources
from .math_dictionary import senses


@lru_cache(maxsize=8192)
def descriptions(term, mathematical=False):
    result = [sense["gloss"] for sense in senses(term)]
    if not mathematical:
        result.extend(synset.definition() for synset in resources()[0].synsets(term.replace(" ", "_")))
    return tuple(dict.fromkeys(result))


@lru_cache(maxsize=16384)
def vector(text):
    import numpy as np
    vocabulary = parser().vocab
    words = (vocabulary[word] for word in re.findall(r"[A-Za-z]+", text.casefold()))
    values = [word.vector for word in words if word.has_vector and not word.is_stop]
    result = np.mean(values, axis=0) if values else np.zeros(vocabulary.vectors_length)
    norm = np.linalg.norm(result)
    return result / norm if norm else result


def best_sense(term, context, mathematical=False):
    local = vector(" ".join(sorted(context)))
    scores = [(float(local @ vector(gloss)), gloss) for gloss in descriptions(term, mathematical)]
    return max(scores, default=(0.0, ""))
