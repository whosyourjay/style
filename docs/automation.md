# Automation and hooks

The hooks run `styleck` after an agent edits a TeX source or before Git creates
a commit. They compare against the committed version and report only new
findings. Neither hook compiles LaTeX.

## Agent post-edit hook

The same script supports Claude Code and Codex. It understands Claude's
`file_path` input and extracts every touched path from Codex's `apply_patch`
input.

For Claude Code, add this to `.claude/settings.json` in the paper repository:

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

For Codex, add this to `~/.codex/hooks.json` for every repository, or to
`<repo>/.codex/hooks.json` for one repository:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "^apply_patch$",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /absolute/path/to/style/hooks/styleck_hook.py",
            "timeout": 30,
            "statusMessage": "Checking writing style"
          }
        ]
      }
    ]
  }
}
```

Codex asks you to review a new or changed command hook before it runs. Use
`/hooks` once after installing or changing it.

The hook reports without editing files. Set `STYLECK_AUTOFIX=1` to permit
mechanical repairs in place. Leave it unset for older papers when a whole-file
repair would obscure the current change.

An error stops the agent with a file, line, and rule id:

```text
styleck: your edit to paper.tex introduced 1 style error(s). Fix them now.
  paper.tex:453:11: error[the-display] nobody says "the display"; ...
```

Warnings arrive as context but do not interrupt the agent.

## Git pre-commit hook

Link the shared hook into a paper repository:

```sh
ln -s /absolute/path/to/style/hooks/styleck_pre_commit.py .git/hooks/pre-commit
```

It checks the versions staged in Git, so unstaged edits do not affect a
commit. New errors stop the commit; warnings are printed but do not stop it.
Findings already present in `HEAD` stay silent.
