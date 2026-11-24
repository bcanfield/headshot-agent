# More like this

Every round after the first. `generate.py ...` and `rank.py ...` are the short forms defined at the top of SKILL.md: run the full `uv run <skill-dir>/scripts/... --workspace <ws>` form. `generate.py --more-like <run_dir>/<NN>.png` re-sends the original photos as images 1-N and the pick as one more image, labelled as a scene reference only: framing, pose, outfit, background and lighting. The face is redrawn from the photos every round, so it varies a little.

**Resample**: new samples of one run's look from the original photos, with no pick: `--from <run_dir>` plus any field changes, never `--more-like`. `<run_dir>` is the run of the candidate in question, so every look field the human approved so far carries over. When its dry run reports `duplicate_of` with `duplicate_finished: true` (a resample with no field change of a run made without a pick), pass `--again`: the result is new samples. Run a resample through steps 3-7 below with `--from <run_dir>` in place of `--more-like <file>`.

## Steps

### 1. Resolve the pick
Done when you hold one file path, or 2-3 candidate paths for the step 4 question, and have said the pick back as "run B, 03.png, ranked 2nd".

Map the human's words to your run labels and the rank rows you reported. "That", "it", or feedback with no candidate named means the current pick: the candidate the human last named or picked. If "#2" has 2-3 plausible readings (rank 2, file `02.png`, an earlier run), carry them into step 4 as "Which image?"; with more, ask now.

### 2. Triage the feedback
Done when the feedback sits on exactly one route below and, for route 1, you hold the exact field phrase(s).

1. **Look change**: any of `outfit`, `background`, `lighting`, `framing` and `expression`, together in one round; `glasses` in a round of its own. Write each value as a full prompt-ready phrase (single line, at most 120 characters). Changes the human approved in earlier rounds stay: if the pick's run predates one (they asked "less smiley" in run D but the pick is still from run B), pass it again as an override alongside the new change.
2. **Ambiguous**: two or three readings. Put them in the step 4 question as "Which did you mean?", each showing the exact phrase.
3. **Likeness complaint** (the face, eyes, nose, teeth or smile shape look unlike them): the pick's face is part of the problem, so leave it out. If another candidate scores higher, offer it first (free). Otherwise resample the pick's run: new faces from the original photos, the same approved look.
4. **Out of reach**: explain why, then offer the row's nearest feasible alternative as a route-1 change.

With no feedback, run route 1 with no field change.

Expression moves along the ladder in SKILL.md step 2. If the run's current expression is not a rung, put the target rung for each of the 2 nearest rungs into "Which did you mean?". At rung 1 or 5 there is no further rung in that direction: say so and offer keeping the pick.

| Feedback | Route | What to do |
|---|---|---|
| "less smiley", "more serious" | 1 | `expression`: one rung down. |
| "more smiley", "friendlier" | 1 | `expression`: one rung up. |
| "look more confident" | 1 | `expression` = rung 3, or rung 2 if already at rung 3 or above. Say that the steady gaze and posture come from the pick. |
| "different tie", "different jacket" | 1 | Rewrite the whole `outfit` phrase with the item named ("a dark navy suit jacket over a white shirt and a plain burgundy tie"). Ask for the colour if none was given. |
| "darker background", "office background" | 1 | `background`, as a named colour or setting ("plain deep-navy"). |
| "zoom out", "show more shoulders" | 1 | `framing` = "head and upper torso, face filling about 40% of the frame". Mention that LinkedIn shows a circle crop. |
| "zoom in", "crop tighter" | 1 | `framing` = "head-and-shoulders, tightly framed, face filling about 70% of the frame". |
| "less serious" | 2 | Expression one rung up / a less formal outfit from the field's table row / a lighter background. |
| "warmer" | 2 | Warmer light (`lighting` = "warm soft window light from the front-left with gentle fill") / a warmer background colour ("plain warm-beige") / a friendlier expression (one rung up). |
| "fix my hair" | 2, then 3 or 4 | Ask whether the hair looks *wrong* (likeness: route 3) or *untidy* (route 4). |
| "doesn't look like me", "eyes look off", "teeth look fake" | 3 | As route 3 above. |
| "#2's outfit with #4's background" | 4 | Nearest: keep one pick, ask them to describe the other image's outfit or background in words, and use that phrase. |
| "younger", "fresher" | 4 | Nearest: expression one rung up and `lighting` = "soft, even window light with gentle fill". |
| "slimmer" | 4 | Nearest: a darker, structured outfit ("a dark navy suit jacket over a white shirt"). |
| "smoother skin" | 4 | Nearest: `lighting` = "soft, even window light with gentle fill". |
| "whiter teeth" | 4 | Nearest: a closed-mouth expression (rung 2 or 3). |
| hair colour or style, untidy hair | 4 | Nearest: new photos with the wanted hair (back to SKILL.md step 1), or keep it. |

Route 4 rows share one reason: the model cannot change the face or body and keep the likeness, and LinkedIn wants a photo that looks like them.

### 3. Dry run
Done when `generate.py --dry-run --json --more-like <file> [--<field> "<phrase>" ...] -n <n> --quality <q>` (or the resample form) exits 0 for every run size you will offer.

Recommend "4 at high" for a pick; when the pick's run was `low`, recommend at least medium. Dry-run each option to get its `estimate_usd`.

Read the output:
- `depth_warning` (a pick of a pick): the pick passed the drift gate, so keep it and recommend the `--more-like` run. A resample of the pick's run may be one more option, never the recommended one.
- `duplicate_of` with `duplicate_finished: true`: those images already exist. For a route 3 resample, add `--again` without asking. Otherwise tell the human in plain text, before the question, that you can reopen them for free, and make each paid option an `--again` one labelled "new samples".
- Exit 2 explains itself in `error`. The common ones:
  - "rank first" or "re-rank" (`stale_rankings`): run `rank.py rank out/<run> --json` for each run named, then retry. Rankings move with the held-back photos, so a stale one is redone, never reused.
  - "drifted" (with `pick_score` and `root_median`): the pick's face has moved away from the human's photos. Say so, and offer a resample of the pick's run with the same field change.
  - "more than one large face": that image is unscored; ask for another pick.
  - "photos/refs no longer matches": the photo set changed; start a fresh run from look.toml (SKILL.md step 3).
  - A refused field combination: glasses goes in a round of its own; do it first and say the rest comes next round.

### 4. One approval question
Done when the human has chosen the pick (if open), an interpretation (if ambiguous) and a run size with its ceiling, or cancelled.

Ask one AskUserQuestion with up to 3 questions, each with at most 4 options:
1. Only if step 1 left 2-3 readings: "Which image?".
2. Only if route 2: "Which did you mean?".
3. "Run size": options in the SKILL.md step 4.2 format, for example "4 at high: estimate $0.27-$1.89, ceiling $1.90 (recommended for a pick)" / "2 at medium: estimate $0.10-$0.68, ceiling $0.70" / "Cancel". With a depth or duplicate option to add, drop "2 at medium" first.

The question text restates the pick ("run B, 03.png, ranked 2nd"), the exact field phrase(s), SKILL.md step 4.2's cost sentence, and: "I'll keep its framing, outfit, background and light. Your face is redrawn from your own photos each time, so it will vary a little." For a resample, say instead that the look stays and every image is new. If the human loves the pick's face itself, recommend keeping that file rather than paying for more.

The approval covers this one run only.

### 5. Run
Done when the paid run has finished and the human has heard the real cost against the estimate.

Run `generate.py --json --more-like <file> [--<field> "<phrase>" ...] -n <n> --quality <q> --max-cost <the human's figure>` (or the resample form; `--again` only where step 3 says so) exactly as in SKILL.md step 4.3-4.7.

### 6. Rank
Done when SKILL.md step 5 has run on the new run.

### 7. Relay the pick comparison
Done when every item below that is present in the rank JSON has been said in plain words.

- Order is still by likeness to the held-back photos (`holdout_median`).
- `chosen.holdout_median`: the pick's own score now. `delta_vs_chosen` per row is information only; new samples usually score a little below a pick that was chosen for scoring well.
- `chosen_sim` (pick-sim): how much of the pick's look carried over. It is not likeness.
- "may copy the picked image's face (provisional)": that image sits closer to the pick's face than the pick's own siblings do. The threshold is uncalibrated; suggest comparing it with a real photo by eye.
- `drift.drift_warning` true: this run's median likeness is more than 0.03 below the root run's. Recommend a resample of this run.
- A `warnings` entry about the picked image (missing, changed or faceless): the pick comparisons are blank; the ranking itself is still valid.
