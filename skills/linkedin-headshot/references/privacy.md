# Privacy and intended use

What to tell the human when they ask what this skill does with their data. The rules the agent follows are in SKILL.md's Rules section.

## Intended use

- Use it on photos of yourself, as an adult, to make headshots of yourself.
- Use photos of other people only with their explicit consent. Do not use photos of minors.
- Do not use it to impersonate anyone. LinkedIn requires a profile photo to be your own likeness.
- Follow OpenAI's usage policies.
- Keep provenance: outputs are left as OpenAI returns them, and nothing here removes the C2PA or other provenance metadata. Leave it in place.

## What leaves your machine

- Only the 3-4 reference photos, re-encoded from pixels as JPEG with no EXIF,
  GPS, XMP or ICC metadata (colours converted to sRGB first), under neutral
  names `ref1.jpg`..., plus the prompt. Held-back photos and all scoring stay local.
- When you ask for "more like" a candidate, that generated image is also sent
  (re-encoded the same way, as `chosen.jpg`) as a scene reference. It is never
  used as a source for your face; your own photos are sent again every round.
- OpenAI keeps API inputs and outputs for up to 30 days for abuse monitoring.
  Zero data retention needs separate approval.
- The agent running this skill never looks at your photos. It looks at the top 3 results only if
  you opt in when asked; otherwise it opens them on your screen for you to judge.
- Your OpenAI key lives only in your shell profile, never in the chat.
- `run.json` stores the prompt (including your marks text), hashes of the
  uploaded files, request id and usage. No filenames, absolute paths or keys.
- iCloud Drive (Desktop & Documents) or employer backup agents may copy
  `photos/` and `out/`. Keep the workspace (for example `~/Headshots`)
  somewhere excluded if that matters.
- Debug logging (`OPENAI_LOG=debug`) can print request bodies. Leave it off.
- If your account is not yet verified, the first call can fail until you
  complete API Organization Verification.
- The first face-ranking run downloads the insightface `buffalo_l` model
  (~289 MB from GitHub, to `~/.insightface`; no photos are sent). Its licence
  is non-commercial; see [NOTICE.md](../NOTICE.md).
