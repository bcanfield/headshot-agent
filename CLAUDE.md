# headshot-agent

This repo ships one agent skill, `linkedin-headshot`, in `skills/linkedin-headshot/`; that folder is all an installer copies. Whenever the human wants a headshot, run the skill (Claude Code loads it here through the `.claude/skills/linkedin-headshot` symlink); its own `references/rules.md` covers spend, the API key and images.

## Contributing

- Tooling: `uv` only. `uv run pytest -q` runs the tests with no network and no real OpenAI calls; `uvx ruff check` and `uvx ruff format --check` must stay clean.
- Everything the skill needs at run time lives inside the skill folder. The scripts are PEP 723 scripts with `uv lock --script` lockfiles: after changing a `# /// script` block, re-run `uv lock --script` on that script and keep the root `pyproject.toml` dependencies equal to the union of the blocks.
- The skill folder stays read-only at run time: data goes to the workspace (`--workspace`, then `$HEADSHOT_WORKSPACE`, then the current folder).
- Release: bump `metadata.version` in `SKILL.md` and `version` in `.claude-plugin/marketplace.json` together, then run `claude plugin validate .`.
- Version control: `photos/`, `out/` and `look.toml` hold personal data and are gitignored; commit none of them.
