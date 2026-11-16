# Mathematical vocabulary

`term-undeclared` checks repeated noun phrases, including specialized uses of
ordinary words. NLTK identifies grammatical roles; WordNet supplies morphology
and subject-labelled mathematical senses. Unknown spellings stay intact.
Diagnostics quote the source text and explain the evidence for checking it.

The bundled model records usage across complexity course notes. A phrase needs
support from three reference documents to count as established vocabulary.
Brown corpus frequencies and nearby words provide an ordinary-prose comparison.
Context comparisons give less weight to words common across the reference corpus.
English frequency alone never exempts a new compound such as `heavy vertex`.
For a common noun, a warning requires repeated attachment to mathematical notation,
mathematical context words, and little overlap with its ordinary contexts.

These are conservative lexical signals, not a proof that two uses have the same
meaning. Established mathematical terms can acquire new meanings that the
checker misses. NLTK's general English tagger can also miss mathematical phrases.
The initial subject coverage is complexity theory, not all mathematical fields.

## Select a profile

Without configuration, the checker selects a subject from an established compound
or several words unusually frequent in that subject's references. To select explicitly,
create `.styleck-vocabulary` (or `paper-name.styleck-vocabulary`):

```json
{"profiles": ["complexity"]}
```

`profiles: []` uses WordNet and ordinary-prose evidence without a subject corpus.
Existing `.styleck-terms` files remain the way to declare assumed vocabulary.
Definitions marked with `\term` or `\deftext` apply to the complete phrase.
The checker also recognizes narrow naming constructions such as
“A vertex is heavy if ...” and “We call a vertex heavy if ...”.

## Generate a profile

Install the build-only corpus once:

```sh
python3 -m nltk.downloader brown
```

From the style repository:

```sh
python3 -m styleck.vocabulary_build --profile complexity ../tcs-courses/lectures --output vocabulary.json
```

`--profile NAME PATH` accepts a TeX file or a directory and may be repeated.
Inputs inside the selected reference directory count with their parent document.
Use reference material independently of the paper being checked. Load the result
from the paper repository with paths relative to the configuration file:

```json
{"profiles": ["complexity"], "models": ["references/vocabulary.json"]}
```

The generator records source paths, normalized-content hashes, definition
markings, frequencies, and nearby words. It excludes exact duplicates and near
duplicates identified by shared text shingles. During checking, matching source
paths and hashes, including those of input files, are excluded from reference support. Repetition in the target
paper never trains its own background vocabulary.

The data contains frequencies and short sets of context words, not copies of
the reference documents. The generator uses NLTK 3.9.2, Princeton WordNet 3.0,
and the Brown corpus distributed through NLTK. The default complexity sources
are recorded individually in `styleck/data/vocabulary.json`.
