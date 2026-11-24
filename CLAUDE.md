# headshot-agent

Turns the user's own photos into LinkedIn headshot candidates: `generate.py` (OpenAI image edits) and `rank.py` (local face-likeness ranking). Run the whole flow with the `linkedin-headshot` skill (`.claude/skills/linkedin-headshot/SKILL.md`) whenever the human wants a headshot.

## Rules

- Spend: pass `--max-cost` only with a dollar figure the human approved in this conversation (the CLI caps it at $10). Real OpenAI calls are the human's to approve; tests never make them.
- API key: the secret is human-only. `generate.py --check-key` is the only way to learn about `OPENAI_API_KEY`; keep its value unread, unprinted and out of chat. When it reports the key missing, tell the human to add `export OPENAI_API_KEY=...` to their shell profile (for example `~/.zshrc`) themselves, typing the key only there, then quit Claude Code and start it again in this folder. That one-time line is the only file the human edits.
- Images: viewing an image sends it to Anthropic, so handle `photos/` and `out/` by path and `open` them on the human's screen. The one exception: if the human opted in at intake, Read the top 3 ranked outputs of a run (only those, only after ranking) to comment on them. `photos/` stays unviewed either way.
- Tooling: `uv` only (`uv run pytest -q` runs the tests, no network).
- Version control: `photos/`, `out/` and `look.toml` hold personal data and are gitignored; commit none of them.
