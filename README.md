# styleck

A linter for writing quality in math papers, and the tooling to make an agent
actually follow the rules instead of reading them once and forgetting.

Scope is writing: LaTeX layout, equations, diagrams, prose. No coding standards.

## Why a prose style guide does not stick on its own

A hand-written list of writing rules, handed to an agent at the start of a
session, gets applied unevenly. Three things work against it:

- The rules were read once at the top of a session and never checked again, so
  attention to them decayed over a long editing session.
- Several were unverifiable while writing. "At least 3 lines of explanation
  between equations" needs counting, which nothing prompted the agent to do.
- Thresholds were implied, not stated. "Do not make weird short lines" gives an
  agent nothing to test a line against.

## What replaces the list

**One source of truth.** A rule carries the instruction an agent reads *and*
the detector that catches breaches, in the same object. `claude.md` is
generated from the registry, so the prose and the checker cannot disagree.

**A feedback loop.** A `PostToolUse` hook runs the checker after every edit to
a `.tex` file. The agent gets its findings back immediately, by rule id.

**Only what the edit added.** The hook compares against the committed version
of the file, so a paper written before these rules existed keeps its old
findings and the agent hears only about what it just introduced.

**Two severities.** Errors block: the agent must fix them before moving on.
Warnings inform: they come back as advice the agent can weigh and never
interrupt a run.

## Use

`bin/styleck` runs from any directory. Symlink it onto your `PATH`, or call it
by absolute path.

```
styleck paper.tex                    # report
styleck --fix paper.tex              # repair what is mechanical
styleck --new-since HEAD paper.tex   # only what is not yet committed
styleck --docs                       # print the style guide
styleck --summary                    # one line per rule
styleck --rules eq-needs-align paper.tex
```

Exit status is 1 when an error-level rule fires, 0 otherwise. `--warn-exit`
makes warnings count too.

Nothing here runs during a LaTeX build or can fail one. The checker reads
`.tex` source and never invokes `pdflatex`.

## Install the hook

Add to `.claude/settings.json` in the repo where you write papers:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /absolute/path/to/style/hooks/styleck_hook.py"
          }
        ]
      }
    ]
  }
}
```

The hook reports without editing your files. Set `STYLECK_AUTOFIX=1` to let it
also repair the mechanical rules in place; leave it off on a repo whose papers
predate these rules, where a whole-file repair would bury the real change.

### What an agent sees

An edit that introduces an error stops the agent with the file, line, and rule:

```
styleck: your edit to paper.tex introduced 1 style error(s). Fix them now.
  paper.tex:453:11: error[the-display] nobody says "the display"; ...
```

An edit that only raises warnings does not interrupt anything; the findings
arrive as context alongside the tool result.

## Share the rules across repos

Each paper repo keeps its own hand-written `claude.md` for coding and workflow
rules. The writing rules are generated into `writing-style.md` next to it and
pulled in with an import line, so they stay in one place:

```
python -m styleck --sync ~/research               # write writing-style.md
python -m styleck --sync ~/research --add-import  # and add @writing-style.md
```

A `writing-style.md` that this tool did not generate is never overwritten.

## Add a rule

Write the check in `styleck/rules_tex.py` or `styleck/rules_prose.py`:

```python
@register(
    id="eq-trailing-punct",
    section="Equations",
    severity=ERROR,
    applies_to=TEX,
    summary="Put no punctuation between display equations or at the end of one.",
    bad="\\[ x = y . \\]",
    good="\\[ x = y \\]",
)
def check_eq_trailing_punct(document): ...
```

The guide picks it up on the next `--docs`. A rule with no possible checker
goes in `styleck/rules_manual.py` via `manual(...)`; it appears in the guide
tagged **judgment** and is never reported as a violation.

To make it auto-fixable, add an entry to `FIXERS` in `styleck/fixers.py`. The
fuzz tests then require that fixing is idempotent, loses no words, and leaves
no violation of that rule behind.

## Tests

```
python -m unittest discover -s tests
```

`test_fuzz.py` asserts invariants over generated documents: the scanner covers
its input exactly, nothing crashes on malformed LaTeX, and a fixed file stays
fixed. The linter also runs clean on its own source and on the guide it
generates.
