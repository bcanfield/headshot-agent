# headshot-agent

LinkedIn headshots from your own photos, made by your coding agent.

```sh
npx skills add https://github.com/bcanfield/headshot-agent
```

Then tell your agent: **"make my LinkedIn headshot"**.

It interviews you, generates candidates with OpenAI's image API, ranks them locally by how much they look like you, and asks before spending anything.

**Needs:** macOS, [uv](https://docs.astral.sh/uv/), and `export OPENAI_API_KEY=...` in your shell profile.

Claude Code plugin instead: `/plugin marketplace add https://github.com/bcanfield/headshot-agent.git`, then `/plugin install linkedin-headshot@headshot-agent`.

Your own photos only. 3-4 of them (metadata stripped) go to OpenAI, and nothing else leaves your machine: [privacy](skills/linkedin-headshot/references/privacy.md).

MIT licence. Model and prompt credits are in [NOTICE](skills/linkedin-headshot/NOTICE.md).
