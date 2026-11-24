# headshot-agent

Turns your own photos into LinkedIn headshots: Claude Code runs the OpenAI image API on them, then ranks the results locally by how much they look like you.

**Intended use: your own photos only.** See [PRIVACY.md](PRIVACY.md) for what that means and what leaves your machine.

**Use:** open [Claude Code](https://claude.com/claude-code) in this folder and say "make my LinkedIn headshot". It asks before spending anything.

**Needs:** macOS, [uv](https://docs.astral.sh/uv/), and an OpenAI API key in your shell profile (`export OPENAI_API_KEY=...`).

**Privacy:** only 3-4 of your photos (metadata stripped) and the prompt go to OpenAI; ranking runs on your machine. Details in [PRIVACY.md](PRIVACY.md).

**Licence:** MIT, for this repo's code and docs only. It does not cover the insightface `buffalo_l` models (non-commercial use only) or the third-party prompts that `prompt.txt` adapts (CC BY 4.0). Terms and credits are in [NOTICE.md](NOTICE.md).
