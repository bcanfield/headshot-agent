# Rules

These hold at every step of the skill.

- **Spend:** pass `--max-cost` only with a dollar figure the human approved in this conversation (the CLI caps it at $10). Every real OpenAI call is the human's to approve.
- **API key:** the secret is human-only. `generate.py --check-key` is the only way to learn about `OPENAI_API_KEY`; keep its value unread, unprinted and out of chat. When it reports the key missing, tell the human to add `export OPENAI_API_KEY=...` to their shell profile (for example `~/.zshrc`) themselves, typing the key only there, then quit the agent (for example Claude Code) and start it again. That one-time line is the only file the human edits.
- **Images:** viewing an image sends it to the model provider, so handle `photos/` and `out/` by path and `open` them on the human's screen. The one exception: if the human opted in at intake, Read the top 3 ranked outputs of a run (only those, only after ranking) to comment on them. `photos/` stays unviewed either way.
- **Personal data:** `photos/`, `out/` and `look.toml` in the workspace hold the human's face and choices. The scripts give `photos/` and `out/` a `.gitignore` of `*`; keep all three out of version control and out of the skill folder.
