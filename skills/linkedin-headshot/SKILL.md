---
name: linkedin-headshot
description: Make a LinkedIn headshot from the human's photos. Use when the human asks for a LinkedIn or professional headshot, profile photo, to change or redo one from an earlier run, or for more like a candidate they picked.
license: MIT
compatibility: Requires uv, network access to api.openai.com, an OPENAI_API_KEY, and a one-time face-model download (about 300 MB, 650 MB unpacked in ~/.insightface). Not for sandboxed API code execution.
metadata:
  version: "0.1.0"
---

# LinkedIn headshot

You run the whole pipeline; the human supplies photos, answers questions, approves spend and judges the results by eye. Read `references/rules.md` (spend, API key, images) before step 1: its rules hold at every step.

`<skill-dir>` in the commands below is this skill's folder: `${CLAUDE_SKILL_DIR}`. If that still shows a `${...}` placeholder, use the absolute path of the folder that contains this SKILL.md. `<ws>` is the workspace from step 1.1: the folder that holds `photos/`, `out/` and `look.toml`. `generate.py ...` and `rank.py ...` below are short for `uv run <skill-dir>/scripts/generate.py --workspace <ws> ...` and `uv run <skill-dir>/scripts/rank.py --workspace <ws> ...`; always run the full form, with both paths absolute, because the shell's folder moves with `cd`. Relative paths in arguments and results (`out/<run>`, `photos/holdout/`) are inside `<ws>`, and every result except `--check-key` echoes `workspace`; if it differs from `<ws>`, fix the command before going on.

Every command takes `--json`: one object on stdout with `exit_code`, plus `error` on failure. Exit codes: 0 ok, 2 input error (fix the cause), 3 needs spend approval, 4 OpenAI or unexpected failure (relay `error`; a run may have been billed). Only `generate.py --dry-run` returns a per-field `errors` map.

## Steps

### 1. Intake
Done when `split` exits 0 and the human knows which photos became references, which were held back and why any were rejected.

1. Pick `<ws>`. If the current folder already holds `look.toml` or `photos/`, propose it; otherwise propose `~/Headshots`, a folder outside Desktop, Documents and iCloud Drive, which can sync to the cloud. Confirm with AskUserQuestion, create it with `mkdir -p`, and keep its absolute path.
2. Run `generate.py --check-key --json`. If `key_present` is false, give the human the API key instructions from `references/rules.md`. Continue intake meanwhile; spend waits for the key.
3. Ask the image opt-in once, with AskUserQuestion: "No, keep my photos and results off Claude (recommended)" first, then "Yes, Claude may look at the top 3 results to comment".
4. Find the photos. Before copying any folder into `<ws>/photos/inbox/`, ask the human to confirm that every photo in it shows only them; another person's face would be uploaded to OpenAI and blended into the result. If `photos/inbox/` already has files, list their names and count and ask whether to keep them.
5. Run `rank.py split --json` with Bash `timeout: 600000` (the first run downloads a 289 MB face model; tell the human).
6. Report the result in plain words: refs, holdout, and every reject with its reason.
   - "may be a different person": tell the human which files, and ask them to remove photos of anyone else.
   - `unknown_files`: split found files it did not create in `photos/refs/` or `photos/holdout/` and changed nothing. Show the list and ask whether to move them into `photos/inbox/` (use `mv -n`); keep every file.
   - Other exit 2: turn `error` into a concrete ask ("add 2 more photos where you face the camera"), then re-run `split` after they add photos.

### 2. Interview
Done when every field below has an answer, in at most 2 AskUserQuestion calls. Each call holds at most 4 questions with at most 4 options each; the tool adds "Other" for free text. Label "(recommended)" only on look and run-size options, never on facts about the human.

**Round 1, facts:**
1. Field and seniority: "Law, finance, government or executive" / "Tech, product, engineering or startup" / "Healthcare, education, creative or marketing" / Other.
2. Glasses: "Keep my glasses as in my photos" / "No glasses".
3. Distinctive marks (moles, freckles, scars, birthmarks, tattoos near the face) to preserve: "None" / "Yes, I'll describe them next".
4. Run size: "2 at medium, to explore (recommended for a first run)" / "4 at high, final quality" / "1 at low, cheapest test".

**Round 2, look**, options taken from the round-1 field's row below, recommended first:
1. Outfit.
2. Background. If the human wants a brand colour, get it as a named colour ("deep teal"); turn a hex code into the nearest colour name and confirm it.
3. Expression: rungs 3 (recommended), 4 and 1 of the expression ladder below, word for word.
4. Only if marks were "Yes": ask them to type a description in Other: what, where, which side as seen in the photo (for example "a small mole above the right eyebrow").

Seniority: for senior or executive roles, pick the more formal option in the row as the recommendation.

Every cell is a prompt-ready phrase: write the chosen text into look.toml word for word.

| Field | Outfit options | Background options |
|-------|----------------|--------------------|
| Law, finance, government, executive | "a dark navy suit jacket over a white shirt"; "a charcoal suit jacket over a light-blue shirt"; "a dark blazer over a plain light blouse" | "plain neutral-grey"; "plain deep-navy" |
| Tech, product, engineering, startup | "a light-blue open-collar button-down shirt"; "a navy casual blazer over a plain white T-shirt"; "a plain charcoal crew-neck sweater" | "modern office"; "plain light-grey" |
| Healthcare, education, creative, marketing | "a smart charcoal knit sweater"; "a soft blue collared shirt"; "a textured olive jacket over a plain cream top" | "plain warm-beige"; "modern office"; "plain <named brand colour>" |
| Other or unsure | "a plain charcoal blazer over a white shirt" | "plain mid-grey" |

Lighting and framing stay at their defaults unless the human raises them.

**Expression ladder**, calm to broad. Every expression value you write is one of these rungs, word for word (the CLI's default is rung 3):
1. "a calm, neutral expression, lips together"
2. "a faint closed-mouth smile, lips together, cheeks relaxed"
3. "a natural closed-mouth smile"
4. "a relaxed smile showing a little teeth"
5. "a broad, warm smile showing teeth"

If the human answers the expression question with Other, write the rung nearest in meaning and tell them which one you used. A run whose expression is not a rung (an older run) is handled in `more-like.md` step 2.

### 3. Write and validate look.toml
Done when `generate.py --dry-run --json -n <n> --quality <q>` exits 0 with `"errors": {}`.

Write `<ws>/look.toml` with string keys `outfit`, `background`, `marks` (empty for none), `glasses` (`keep` or `none`), `expression`, and `lighting` and `framing` (omit either to keep its default). Each value is one line of at most 120 characters. Exit 2 lists bad fields under `errors`; fix and repeat.

If this dry run returns `duplicate_of` with `duplicate_finished: true`, a run with this exact look.toml already finished: tell the human and go to step 5 with `out/<duplicate_of>` instead of paying again. Use `--again` only when the human wants new samples of the identical settings, under a new approval.

### 4. Spend gate
Done when the human has approved a dollar ceiling, the run has finished, and the human has heard the real cost against the estimate.

1. Show the dry run's `estimate_usd` range in plain words.
2. Ask for approval with AskUserQuestion. Each run option carries its estimate and its ceiling (the upper bound rounded up to the next 10 cents), for example "4 at high: estimate $0.27-$1.73, ceiling $1.80"; add "Cancel". The question text says: "The run starts only if the estimate's upper bound is under the ceiling. OpenAI bills by tokens, so the real cost can come out higher." The CLI refuses ceilings above $10.
3. Run `generate.py --json --max-cost <the human's figure> -n <n> --quality <q>` with Bash `run_in_background: true`, then wait for the completion notification. A paid call can take several minutes; while it runs, leave it alone: no kill, no second run.
   Label each run with a letter in the order you make it (run A, run B, ...) and keep the label → `run_dir` mapping; the human only ever hears the label.
4. Exit 0: report `cost_usd` against `estimate_usd` and the approved ceiling. If `over_ceiling` is true, say plainly that the real cost exceeded the ceiling and by how much. If `cost_usd` is above the estimate's upper bound, say that estimates for this kind of run come out low. If `status` is `partial`, say how many images came back unreadable (`bad_outputs`).
5. Exit 3: the ceiling is under the upper bound. Return to the human with the estimate and take any new ceiling from them.
6. Exit 2 with `duplicate_of`: an identical run exists or may have been billed. For a finished run, apply the duplicate rule of the step you came from (step 3, or `more-like.md` step 3). Otherwise have the human check the OpenAI usage page, and pass `--again` once they say so, under a ceiling they approve.
7. Exit 4: relay `error` and `request_id`. With `possibly_billed` true, ask the human to check the OpenAI usage page before any retry.

### 5. Rank and show
Done when the top candidates and one real photo are open on the human's screen and explained.

1. Run `rank.py rank <run_dir> --json`.
2. `open` the top 3 rows' files (paths inside `<ws>`) (all of them if fewer), plus the first file in `photos/holdout/` so the human compares against a real photo. Name every candidate by run label, filename and rank ("run B, 03.png, ranked 2nd"), never by a bare number.
3. Explain in plain words:
   - Scores order the candidates by likeness to the held-back photos; differences under 0.02 are noise; the human's eye decides.
   - `baseline` is how alike the human's own held-back photos are to each other; scores near it mean "looks like you".
   - "likely copy of a reference": the image sits much closer to an uploaded photo than to the held-back ones; look for a near-paste.
   - "could not read" or face-count flags: that file is unscored; skip it.
   - `partial` and `bad_outputs`: some images came back unreadable and are not ranked.
   - Pass on every `warnings` entry.
4. If the human opted in at intake, Read the top 3 output files now and add brief comments on visible flaws (hands, teeth, clothing artefacts, likeness to the brief).
5. For a `--more-like` run, also relay the pick comparison as described in `more-like.md` step 7.
6. Ask which candidate they like, and what, if anything, to change.

### 6. Iterate
Done when the human picks a file or stops.

Follow `more-like.md` in this folder for every further round: feedback on a candidate ("more like run B 03.png", "less smiley"), feedback that names no candidate (it applies to the current pick), and new samples with no pick ("more, but different", which is a resample there).

### 7. Finish
Tell the human the absolute path of the chosen file and that they upload it to LinkedIn themselves. If they ask what left their machine, answer from `references/privacy.md`.
