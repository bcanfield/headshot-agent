# headshot-agent

Turns your own photos into LinkedIn headshots: an agent skill runs the OpenAI image API on them, then ranks the results locally by how much they look like you.

**Intended use: your own photos only.** See [privacy.md](skills/linkedin-headshot/references/privacy.md) for what that means and what leaves your machine.

**Install** the `linkedin-headshot` skill (the [skills/linkedin-headshot](skills/linkedin-headshot) folder):

- Claude Code, Codex, Cursor and other agents that read skills: `npx skills add https://github.com/bcanfield/headshot-agent` (add `-g` for every project).
- Claude Code plugin: `/plugin marketplace add https://github.com/bcanfield/headshot-agent.git`, then `/plugin install linkedin-headshot@headshot-agent`.

**Use:** say "make my LinkedIn headshot". The skill keeps your photos and results in a workspace folder of their own (it suggests `~/Headshots`) and asks before spending anything.

**Needs:** macOS, [uv](https://docs.astral.sh/uv/), and an OpenAI API key in your shell profile (`export OPENAI_API_KEY=...`).

**Privacy:** only 3-4 of your photos (metadata stripped) and the prompt go to OpenAI; ranking runs on your machine. Details in [privacy.md](skills/linkedin-headshot/references/privacy.md).

**Licence:** MIT, for this repo's code and docs only. It does not cover the insightface `buffalo_l` models (non-commercial use only) or the third-party prompts that `prompt.txt` adapts (CC BY 4.0). Terms and credits are in [NOTICE.md](skills/linkedin-headshot/NOTICE.md).
