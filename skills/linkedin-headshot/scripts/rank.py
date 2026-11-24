# /// script
# requires-python = ">=3.13,<3.15"
# dependencies = [
#     "openai>=3",
#     "pillow>=11",
#     "pillow-heif>=1.0",
#     "numpy>=2",
#     # insightface's pretrained buffalo_l models are non-commercial research use
#     # only; this skill's MIT licence does not cover them (see NOTICE.md).
#     "insightface>=2.1",
#     "onnxruntime>=1.20",
#     "scikit-image<2.2",
# ]
# ///
"""Photo split, pre-flight check and likeness ranking, all local. Owns insightface.

Usage (SKILL = this skill's folder; WS = the workspace holding photos/ and out/):
    uv run SKILL/scripts/rank.py --workspace WS split      # photos/inbox -> refs + holdout
    uv run SKILL/scripts/rank.py --workspace WS check      # free pre-flight on refs and holdout
    uv run SKILL/scripts/rank.py --workspace WS rank out/<ts>

--workspace defaults to $HEADSHOT_WORKSPACE, then the current folder; the skill
folder itself, / and $HOME are refused. Relative paths resolve against it.

Every command takes --json: one JSON object on stdout (with "error" and
"exit_code" on failure), human text and model-download output on stderr.
Exit codes: 0 ok, 2 user/input error (also a failed check or split), 4 unexpected
failure (for example the face-model download). Never prompts.

Scores order candidates for you to judge by eye. They are not a verdict.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

# An installed skill folder must stay byte-identical, so sibling modules leave no __pycache__.
sys.dont_write_bytecode = True

import cli
import imaging
import workspace

LARGE_FACE_RATIO = 0.25  # a second face this fraction of the largest (by area) counts
MIN_FACE_PX = 256  # warn below this face width in the (resized) photo
NEAR_DUP_SIM = 0.95
NOISE = 0.02
COPY_MARGIN = 0.10  # likely copy: max_ref_sim - holdout_median above this
# --more-like runs (both uncalibrated guesses until real runs exist):
GENERATED_COPY_MARGIN = 0.10  # provisional: chosen_sim above the pick's sibling similarity by this
DRIFT_MARGIN = 0.03  # run median this far below the root run's median = drift
MIN_REFS, MAX_REFS = 3, 4
MIN_HOLDOUT = 2
# split picks references that are near-frontal and sharp. Both thresholds are
# guesses to tune on first real use.
MAX_YAW = 0.25  # |nose offset along the eye line| / eye distance (roll-invariant)
MIN_SHARPNESS = 15.0  # Laplacian variance of the lightly blurred 128x128 grey face crop
SHARPNESS_BLUR = 1.0  # Gaussian radius applied first, so sensor noise does not read as detail
SAME_PERSON_SIM = 0.30  # split rejects a photo whose median similarity to the others is below
SPLIT_MANIFEST = ".split_manifest.json"  # under photos/: the files split wrote
IGNORED_NAMES = {".DS_Store"}  # Finder litter split neither owns nor objects to


@dataclass
class Face:
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2
    embedding: np.ndarray
    yaw: float = 0.0  # 0 = frontal; grows as the head turns
    sharpness: float = 1e9  # higher = sharper

    @property
    def area(self) -> float:
        return max(0.0, self.bbox[2] - self.bbox[0]) * max(0.0, self.bbox[3] - self.bbox[1])

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]


@dataclass
class PhotoInfo:
    name: str
    main: Face | None
    n_large: int
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class RankError(Exception):
    def __init__(self, message: str, **extra):
        super().__init__(message)
        self.extra = extra


# ------------------------------------------------------------- pure logic


def unit(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float64)
    n = np.linalg.norm(v)
    return v / n if n else v


def cosine(a, b) -> float:
    return float(np.dot(unit(a), unit(b)))


def analyze_faces(name: str, faces: list[Face]) -> PhotoInfo:
    if not faces:
        return PhotoInfo(name, None, 0, problems=["no face found"])
    faces = sorted(faces, key=lambda f: f.area, reverse=True)
    main = faces[0]
    n_large = sum(1 for f in faces if f.area >= LARGE_FACE_RATIO * main.area)
    info = PhotoInfo(name, main, n_large)
    if n_large > 1:
        info.problems.append(f"{n_large} large faces")
    return info


def baseline(embeddings: list[np.ndarray]) -> dict | None:
    """Pairwise similarity among the real holdout photos."""
    if len(embeddings) < 2:
        return None
    sims = [cosine(a, b) for a, b in itertools.combinations(embeddings, 2)]
    return {"mean": float(np.mean(sims)), "min": min(sims), "max": max(sims), "pairs": len(sims)}


def sibling_similarity(pick_emb, siblings: list[np.ndarray]) -> float | None:
    """Median cosine between the pick and the other outputs of its own run: how
    alike two samples of the same look are anyway. None without siblings."""
    if not siblings:
        return None
    return float(np.median([cosine(pick_emb, s) for s in siblings]))


def add_pick_columns(
    rows: list[dict],
    embeddings: dict[str, np.ndarray],
    pick_emb,
    pick_score: float,
    sibling_sim: float | None,
) -> None:
    """chosen_sim (look carry-over, not likeness), delta_vs_chosen (information
    only) and the provisional copied_generated_face flag."""
    for r in rows:
        emb = embeddings.get(r["file"])
        if emb is None or r["holdout_median"] is None:
            continue
        r["chosen_sim"] = cosine(emb, pick_emb)
        r["delta_vs_chosen"] = r["holdout_median"] - pick_score
        if sibling_sim is not None:
            r["copied_generated_face"] = r["chosen_sim"] - sibling_sim > GENERATED_COPY_MARGIN
            if r["copied_generated_face"]:
                r["flags"].append("may copy the picked image's face (provisional)")


def drift_check(run_scores: list[float], root_scores: list[float]) -> dict | None:
    """Run-level drift: this run's median likeness against its root run's."""
    if not run_scores or not root_scores:
        return None
    run_median, root_median = float(np.median(run_scores)), float(np.median(root_scores))
    diff = run_median - root_median
    return {
        "run_median": run_median,
        "root_median": root_median,
        "difference": diff,
        "margin": DRIFT_MARGIN,
        "drift_warning": diff < -DRIFT_MARGIN,
    }


def near_duplicates(named: list[tuple[str, np.ndarray]]) -> list[tuple[str, str, float]]:
    out = []
    for (na, ea), (nb, eb) in itertools.combinations(named, 2):
        s = cosine(ea, eb)
        if s > NEAR_DUP_SIM:
            out.append((na, nb, s))
    return out


def likeness(emb, holdout: list[np.ndarray]) -> float:
    """The score: median cosine to the real holdout photos."""
    return float(np.median([cosine(emb, h) for h in holdout]))


def finite(x) -> float | None:
    return float(x) if x is not None and math.isfinite(x) else None


def score_outputs(
    outputs: list[PhotoInfo], holdout: list[np.ndarray], refs: list[np.ndarray]
) -> list[dict]:
    """One row per output, sorted best first. Likeness = median cosine to the
    holdout photos only. max_ref_sim and likely_copy use the uploaded refs.
    An output with no face or more than one large face stays unscored."""
    rows = []
    for info in outputs:
        row = {
            "file": info.name,
            "holdout_median": None,
            "max_ref_sim": None,
            "likely_copy": False,
            "large_faces": info.n_large,
            "flags": list(info.problems),
        }
        if info.main is not None and not info.problems:
            emb = info.main.embedding
            row["holdout_median"] = finite(likeness(emb, holdout))
            if row["holdout_median"] is None:
                row["flags"].append("score is not a number")
            elif refs:
                row["max_ref_sim"] = max(cosine(emb, r) for r in refs)
                if row["max_ref_sim"] - row["holdout_median"] > COPY_MARGIN:
                    row["likely_copy"] = True
                    row["flags"].append("likely copy of a reference")
        rows.append(row)
    rows.sort(key=lambda r: (r["holdout_median"] is None, -(r["holdout_median"] or 0)))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


# ------------------------------------------------------------- insightface


class InsightFaceEmbedder:
    """Lazy wrapper: embedder(bgr_uint8_array) -> list[Face]."""

    def __init__(self, root: str | None = None):
        self._app = None
        self._root = root

    def _load(self):
        import os

        from insightface.app import FaceAnalysis

        root = self._root or os.path.expanduser("~/.insightface")
        print(
            f"loading buffalo_l from {root}/models (first run downloads ~289 MB from "
            f"GitHub; no photos are sent)",
            file=sys.stderr,
        )
        with cli.stdout_to_stderr():  # download and provider chatter must not reach stdout
            app = FaceAnalysis(
                name="buffalo_l",
                root=root,
                allowed_modules=["detection", "recognition"],
                providers=["CoreMLExecutionProvider", "CPUExecutionProvider"],
            )
            app.prepare(ctx_id=0, det_size=(640, 640))  # det_thresh stays at default 0.5
        self._app = app

    def __call__(self, bgr: np.ndarray) -> list[Face]:
        if self._app is None:
            self._load()
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            found = self._app.get(bgr)
        return [self._face(bgr, f) for f in found]

    @staticmethod
    def _face(bgr: np.ndarray, f) -> Face:
        bbox = tuple(map(float, f.bbox))
        kps = getattr(f, "kps", None)
        yaw = yaw_from_kps(kps) if kps is not None else 0.0
        return Face(bbox, np.asarray(f.normed_embedding), yaw, face_sharpness(bgr, bbox))


def yaw_from_kps(kps) -> float:
    """Head turn from the 5 detection keypoints (left eye, right eye, nose, mouth
    corners): the nose offset from the eye midpoint, projected on the eye line and
    divided by the eye distance. Projecting on the eye line makes it ignore roll."""
    k = np.asarray(kps, dtype=np.float64)
    e = k[1] - k[0]
    d2 = float(np.dot(e, e))
    if d2 < 1e-12:
        return 0.0
    return float(np.dot(k[2] - (k[0] + k[1]) / 2, e) / d2)


def face_sharpness(bgr: np.ndarray, bbox) -> float:
    """Laplacian variance of the face crop, scaled to 128x128 so it is comparable,
    after a light blur so pixel noise does not count as detail."""
    h, w = bgr.shape[:2]
    x1, y1 = max(0, int(bbox[0])), max(0, int(bbox[1]))
    x2, y2 = min(w, int(bbox[2])), min(h, int(bbox[3]))
    if x2 - x1 < 8 or y2 - y1 < 8:
        return 0.0
    crop = Image.fromarray(bgr[y1:y2, x1:x2, ::-1]).convert("L").resize((128, 128))
    crop = crop.filter(ImageFilter.GaussianBlur(SHARPNESS_BLUR))
    a = np.asarray(crop, dtype=np.float64)
    lap = -4 * a[1:-1, 1:-1] + a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]
    return float(lap.var())


# ------------------------------------------------------------------- I/O


def embed_path(path: Path, embed, resize: bool = False) -> PhotoInfo:
    img = imaging.load_rgb(path)  # raises ImagingError: an unreadable image is an error
    if resize:
        img = imaging.resize_long_edge(img)
    info = analyze_faces(path.name, embed(imaging.to_bgr(img)))
    if info.main is not None and info.main.width < MIN_FACE_PX:
        info.warnings.append(f"small face ({info.main.width:.0f} px wide, want >= {MIN_FACE_PX})")
    return info


def load_folder(folder: Path, embed, resize: bool) -> list[PhotoInfo]:
    if not folder.is_dir():
        return []
    ok, skipped = imaging.list_photos(folder)
    for p in skipped:
        print(f"warning: skipping unsupported file {folder.name}/{p.name}", file=sys.stderr)
    return [embed_path(p, embed, resize) for p in ok]


def fmt(x) -> str:
    return "-" if x is None else f"{x:.2f}"


# ----------------------------------------------------------------- check


def cmd_check(root: Path, embed, say) -> tuple[int, dict]:
    problems: list[str] = []
    groups, listing = {}, {}
    for sub, resize in (("refs", True), ("holdout", False)):
        infos = load_folder(root / "photos" / sub, embed, resize)
        groups[sub] = infos
        listing[sub] = []
        say(f"\nphotos/{sub}: {len(infos)} photo(s)")
        for i in infos:
            width = f"{i.main.width:.0f}px" if i.main else "-"
            notes = i.problems + i.warnings
            say(f"  {i.name}: face {width}" + (f"  [{'; '.join(notes)}]" if notes else ""))
            listing[sub].append(
                {
                    "file": i.name,
                    "face_px": round(i.main.width) if i.main else None,
                    "problems": i.problems,
                    "warnings": i.warnings,
                }
            )
            problems += [f"{sub}/{i.name}: {p}" for p in i.problems]
    n_refs, n_hold = len(groups["refs"]), len(groups["holdout"])
    if not MIN_REFS <= n_refs <= MAX_REFS:
        problems.append(f"photos/refs needs {MIN_REFS}-{MAX_REFS} photos, has {n_refs}")
    if n_hold < MIN_HOLDOUT:
        problems.append(f"photos/holdout needs at least {MIN_HOLDOUT} photos, has {n_hold}")
    good = [
        (f"{sub}/{i.name}", i.main.embedding)
        for sub, infos in groups.items()
        for i in infos
        if i.main is not None and not i.problems
    ]
    dups = []
    for a, b, s in near_duplicates(good):
        cross = a.split("/")[0] != b.split("/")[0]
        dups.append({"a": a, "b": b, "similarity": round(s, 4), "cross_group": cross})
        if cross:
            problems.append(
                f"{a} and {b} are near-duplicates ({s:.2f}): a holdout photo must "
                "not be a copy of an uploaded reference"
            )
            say(f"\nproblem: near-duplicate across folders: {a} and {b} ({s:.2f}).")
        else:
            say(f"\nnear-duplicate: {a} and {b} ({s:.2f}); they add little. Replace one.")
    base = baseline([i.main.embedding for i in groups["holdout"] if i.main and not i.problems])
    if base:
        say(
            f"\nbaseline (your holdout photos vs each other): mean {base['mean']:.2f}, "
            f"min {base['min']:.2f}, max {base['max']:.2f} over {base['pairs']} pair(s)"
        )
    for p in problems:
        say(f"problem: {p}")
    say(
        "\n"
        + (
            "OK to generate."
            if not problems
            else f"{len(problems)} problem(s): fix before spending money."
        )
    )
    payload = {
        "ok": not problems,
        "refs": listing["refs"],
        "holdout": listing["holdout"],
        "near_duplicates": dups,
        "baseline": base,
        "problems": problems,
    }
    return (0 if not problems else 2), payload


# ----------------------------------------------------------------- split


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_manifest(photos: Path) -> dict[str, str]:
    """{"refs/01_a.jpg": sha256, ...} for the files an earlier split wrote."""
    path = photos / SPLIT_MANIFEST
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text())
        files = data.get("files", {}) if isinstance(data, dict) else {}
        return {str(k): str(v) for k, v in files.items()} if isinstance(files, dict) else {}
    except (OSError, ValueError):
        return {}


def unowned_files(photos: Path, manifest: dict[str, str]) -> list[str]:
    """Entries in refs/ and holdout/ that split did not write (or that changed since)."""
    unknown = []
    for sub in ("refs", "holdout"):
        folder = photos / sub
        if not folder.exists() and not folder.is_symlink():
            continue
        if folder.is_symlink() or not folder.is_dir():
            unknown.append(f"{sub} (not a plain folder)")
            continue
        for p in sorted(folder.iterdir()):
            if p.name in IGNORED_NAMES:
                continue
            rel = f"{sub}/{p.name}"
            if (
                p.is_symlink()
                or not p.is_file()
                or rel not in manifest
                or file_sha256(p) != manifest[rel]
            ):
                unknown.append(rel)
    return unknown


def remove_owned(photos: Path, manifest: dict[str, str]) -> None:
    """Delete only files split wrote, as recorded in the manifest."""
    for rel in manifest:
        p = photos / rel
        if p.is_file() and not p.is_symlink():
            p.unlink()


def candidate_order(info: PhotoInfo, why: list[str]):
    """Better photos sort first: eligible as a reference, then sharper."""
    return (bool(why), -info.main.sharpness)


def cmd_split(root: Path, embed, say) -> tuple[int, dict]:
    photos = root / "photos"
    inbox = photos / "inbox"
    if not inbox.is_dir():
        raise RankError(f"{inbox} does not exist; put your photos there")
    manifest = read_manifest(photos)
    unknown = unowned_files(photos, manifest)
    if unknown:  # refuse before touching anything
        raise RankError(
            "photos/refs or photos/holdout holds files that split did not create: "
            f"{', '.join(unknown)}. Nothing was changed. Move them into photos/inbox/ "
            "(or anywhere else) and run split again",
            unknown_files=unknown,
        )

    ok_files, skipped = imaging.list_photos(inbox)
    rejected = [{"file": p.name, "reason": "unsupported file type"} for p in skipped]
    found: list[tuple[Path, PhotoInfo, list[str]]] = []  # (path, info, why not a ref)
    for p in ok_files:
        try:
            info = embed_path(p, embed, resize=True)
        except imaging.ImagingError as exc:
            rejected.append({"file": p.name, "reason": f"cannot read: {exc}"})
            continue
        if info.problems:
            reason = (
                "no face found"
                if info.main is None
                else f"{info.n_large} large faces; use a photo of you alone"
            )
            rejected.append({"file": p.name, "reason": reason})
            continue
        f, why = info.main, []
        if f.width < MIN_FACE_PX:
            why.append(f"face only {f.width:.0f} px wide (want >= {MIN_FACE_PX})")
        if f.sharpness < MIN_SHARPNESS:
            why.append(f"soft focus (sharpness {f.sharpness:.0f}, want >= {MIN_SHARPNESS:.0f})")
        if abs(f.yaw) > MAX_YAW:
            why.append(f"head turned away from the camera (yaw {f.yaw:+.2f})")
        found.append((p, info, why))

    # Near-duplicates: keep the better photo of each pair (eligible, then sharper).
    kept: list[tuple[Path, PhotoInfo, list[str]]] = []
    for p, info, why in sorted(found, key=lambda u: candidate_order(u[1], u[2])):
        dup = next(
            (
                q.name
                for q, qi, _ in kept
                if cosine(qi.main.embedding, info.main.embedding) > NEAR_DUP_SIM
            ),
            None,
        )
        if dup:
            rejected.append({"file": p.name, "reason": f"near-duplicate of {dup} (kept that one)"})
        else:
            kept.append((p, info, why))
    order = {p: i for i, p in enumerate(ok_files)}
    kept.sort(key=lambda u: order[u[0]])

    # Same person: a photo unlike the others is probably someone else.
    medians = {}
    if len(kept) >= 2:
        for p, info, _ in kept:
            sims = [cosine(info.main.embedding, qi.main.embedding) for q, qi, _ in kept if q != p]
            medians[p] = float(np.median(sims))
    identity_base = baseline([i.main.embedding for _, i, _ in kept])
    usable, strangers = [], []
    for u in kept:
        m = medians.get(u[0])
        if m is not None and m < SAME_PERSON_SIM:
            strangers.append(u[0].name)
            rejected.append(
                {
                    "file": u[0].name,
                    "reason": (
                        f"may be a different person (median similarity {m:.2f} to your other "
                        f"photos, want >= {SAME_PERSON_SIM:.2f})"
                    ),
                }
            )
        else:
            usable.append(u)

    for r in rejected:
        say(f"rejected {r['file']}: {r['reason']}")
    if identity_base:
        say(
            f"same-person baseline (all usable photos vs each other): mean "
            f"{identity_base['mean']:.2f}, min {identity_base['min']:.2f}"
        )
    eligible = sorted((u for u in usable if not u[2]), key=lambda u: abs(u[1].main.yaw))
    n_refs = min(MAX_REFS, len(eligible), len(usable) - MIN_HOLDOUT)
    fail = None
    if len(usable) < MIN_REFS + MIN_HOLDOUT:
        fail = (
            f"only {len(usable)} usable photo(s); need at least {MIN_REFS + MIN_HOLDOUT}. "
            f"Add {MIN_REFS + MIN_HOLDOUT - len(usable)} more photos of you alone"
        )
        if strangers:
            fail += (
                f". {len(strangers)} photo(s) look like a different person: {', '.join(strangers)}"
            )
    elif n_refs < MIN_REFS:
        short = MIN_REFS - len(eligible)
        fail = (
            f"only {len(eligible)} photo(s) are large, sharp and front-facing enough "
            f"for references; add {short} more"
            if short > 0
            else f"need at least {MIN_HOLDOUT} more photos to hold back for scoring"
        )
    if fail:
        raise RankError(
            fail,
            rejected=rejected,
            usable=len(usable),
            identity_baseline=identity_base,
            not_reference_material=[{"file": p.name, "why": w} for p, _, w in usable if w],
        )

    ref_picks = eligible[:n_refs]
    ref_paths = {p for p, _, _ in ref_picks}
    plan = [(p, f"refs/{i:02d}_{p.name}") for i, (p, _, _) in enumerate(ref_picks, 1)]
    plan += [(p, f"holdout/{p.name}") for p, _, _ in usable if p not in ref_paths]
    remove_owned(photos, manifest)
    workspace.protect(photos)
    for sub in ("refs", "holdout"):
        (photos / sub).mkdir(parents=True, exist_ok=True)
    # The manifest is written before copying, so a crash mid-copy leaves only owned files.
    new_manifest = {rel: file_sha256(src) for src, rel in plan}
    (photos / SPLIT_MANIFEST).write_text(json.dumps({"files": new_manifest}, indent=2) + "\n")
    for src, rel in plan:
        shutil.copyfile(src, photos / rel)

    refs_out, hold_out = [], []
    for i, (p, info, _) in enumerate(ref_picks, 1):
        refs_out.append(
            {
                "file": p.name,
                "as": f"{i:02d}_{p.name}",
                "reason": f"near-frontal (yaw {info.main.yaw:+.2f}), face {info.main.width:.0f} px, "
                f"sharpness {info.main.sharpness:.0f}",
            }
        )
    for p, info, why in usable:
        if p in ref_paths:
            continue
        hold_out.append(
            {
                "file": p.name,
                "reason": ("kept for scoring: " + "; ".join(why))
                if why
                else "kept for scoring (not among the best frontal photos)",
            }
        )
    base = baseline([i.main.embedding for p, i, _ in usable if p not in ref_paths])
    say(f"refs: {len(refs_out)}, holdout: {len(hold_out)}, rejected: {len(rejected)}")
    return 0, {
        "ok": True,
        "refs": refs_out,
        "holdout": hold_out,
        "rejected": rejected,
        "baseline": base,
        "identity_baseline": identity_base,
        "same_person_threshold": SAME_PERSON_SIM,
    }


# ------------------------------------------------------------------ rank


def upload_hash(path: Path) -> str:
    """sha256 of the sanitised upload bytes, as generate.py records it in run.json."""
    return hashlib.sha256(imaging.sanitize_for_upload(path)).hexdigest()


def current_ref_hashes(refs_dir: Path) -> dict[str, str]:
    ok, _ = imaging.list_photos(refs_dir) if refs_dir.is_dir() else ([], [])
    return {f"ref{i}": upload_hash(p) for i, p in enumerate(ok, 1)}


def read_run(out_dir: Path) -> dict:
    meta = out_dir / "run.json"
    if not meta.is_file():
        return {}
    try:
        data = json.loads(meta.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def cmd_rank(root: Path, embed, out_arg: str, say) -> tuple[int, dict]:
    out_dir = Path(out_arg)
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    files = sorted(out_dir.glob("[0-9][0-9].png"))
    if not files:
        raise RankError(f"no NN.png outputs in {out_arg}")
    warnings: list[str] = []

    def warn(msg: str) -> None:
        warnings.append(msg)
        say(f"warning: {msg}")

    run_meta = read_run(out_dir)
    recorded = run_meta.get("refs")
    run_ref_hashes = set(recorded.values()) if isinstance(recorded, dict) else set()

    def usable(sub: str, resize: bool) -> list[PhotoInfo]:
        keep = []
        ok, skipped = (
            imaging.list_photos(root / "photos" / sub)
            if (root / "photos" / sub).is_dir()
            else ([], [])
        )
        for p in skipped:
            say(f"warning: skipping unsupported file {sub}/{p.name}")
        for path in ok:
            i = embed_path(path, embed, resize)
            if i.main is None or i.problems:
                warn(f"photos/{sub}/{i.name} left out of scoring: {'; '.join(i.problems)}")
            elif sub == "holdout" and run_ref_hashes and upload_hash(path) in run_ref_hashes:
                warn(
                    f"photos/holdout/{i.name} left out of scoring: it was uploaded as a "
                    "reference in this run, so it would inflate the scores"
                )
            else:
                keep.append(i)
        return keep

    holdout, refs = usable("holdout", False), usable("refs", False)
    if len(holdout) < MIN_HOLDOUT:
        raise RankError(
            f"need at least {MIN_HOLDOUT} usable photos in photos/holdout that were "
            f"not uploaded in this run (found {len(holdout)}); run `split` again"
        )
    if isinstance(recorded, dict):
        try:
            if recorded != current_ref_hashes(root / "photos" / "refs"):
                warn(
                    "photos/refs differs from the references this run was generated "
                    "from; max-ref and copy flags use the current photos/refs"
                )
        except (OSError, ValueError, imaging.ImagingError):
            warn("could not compare photos/refs with run.json")
    h_embs = [i.main.embedding for i in holdout]
    base = baseline(h_embs)
    # generate.py refuses a pick when this differs from the current photos/holdout.
    holdout_set = imaging.holdout_set(root / "photos" / "holdout")
    outputs = []
    for p in files:
        try:
            outputs.append(embed_path(p, embed))
        except imaging.ImagingError:
            outputs.append(PhotoInfo(p.name, None, 0, problems=["could not read"]))
    rows = score_outputs(outputs, h_embs, [i.main.embedding for i in refs])
    for r in rows:
        r.update(chosen_sim=None, delta_vs_chosen=None, copied_generated_face=None)
    chosen = pick_report(root, run_meta, embed, h_embs, warn)
    if chosen and chosen.get("_emb") is not None:
        add_pick_columns(
            rows,
            {o.name: o.main.embedding for o in outputs if o.main is not None},
            chosen["_emb"],
            chosen["holdout_median"],
            chosen["sibling_sim"],
        )
    if chosen:
        chosen.pop("_emb", None)
    drift = root_drift(root, out_dir, run_meta, rows, embed, h_embs, warn)

    say(
        f"baseline, your holdout photos vs each other: mean {base['mean']:.2f}, "
        f"max {base['max']:.2f}"
    )
    say(f"score = median similarity to holdout photos. Gaps under ~{NOISE} are noise.\n")
    say(f"{'rank':<5}{'file':<8}{'score':<8}{'max-ref':<9}{'pick-sim':<9}flags")
    for r in rows:
        say(
            f"{r['rank']:<5}{r['file']:<8}{fmt(r['holdout_median']):<8}"
            f"{fmt(r['max_ref_sim']):<9}{fmt(r['chosen_sim']):<9}{'; '.join(r['flags'])}"
        )
    if chosen and chosen["holdout_median"] is not None:
        say(
            f"\npick {chosen['file']}: score {chosen['holdout_median']:.2f}, similarity to its "
            f"siblings {fmt(chosen['sibling_sim'])}. pick-sim is look carry-over, not likeness."
        )
    if drift:
        say(
            f"root run {drift['root_run']}: median {drift['root_median']:.2f}; this run "
            f"{drift['run_median']:.2f}"
            + (
                f"  [DRIFT: more than {DRIFT_MARGIN} below the root run]"
                if drift["drift_warning"]
                else ""
            )
        )
    say(
        "\nThis only orders candidates. Open them next to a real photo and choose by eye;"
        " a faithful pick beats a flattering one."
    )

    csv_path = out_dir / "ranking.csv"
    try:
        rel_dir = out_dir.relative_to(root)
    except ValueError:
        rel_dir = Path(out_dir.name)

    def num(x) -> str:
        return "" if finite(x) is None else f"{x:.4f}"

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        # Later columns go after the earlier ones, so existing positions never move.
        w.writerow(
            [
                "rank",
                "file",
                "holdout_median",
                "max_ref_sim",
                "likely_copy",
                "large_faces",
                "flags",
                "baseline_mean",
                "baseline_max",
                "chosen_sim",
                "delta_vs_chosen",
                "copied_generated_face",
                "holdout_set",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    r["rank"],
                    str(rel_dir / r["file"]),
                    num(r["holdout_median"]),
                    num(r["max_ref_sim"]),
                    r["likely_copy"],
                    r["large_faces"],
                    "; ".join(r["flags"]),
                    num(base["mean"]),
                    num(base["max"]),
                    num(r["chosen_sim"]),
                    num(r["delta_vs_chosen"]),
                    "" if r["copied_generated_face"] is None else r["copied_generated_face"],
                    holdout_set,
                ]
            )
    say(f"wrote {rel_dir / 'ranking.csv'}")
    for r in rows:
        r["file"] = str(rel_dir / r["file"])
    bad_outputs = run_meta.get("bad_outputs") or []
    partial = run_meta.get("status") == "partial"
    if partial:
        say(
            f"note: this run is partial; {len(bad_outputs)} output(s) were unreadable "
            f"({', '.join(map(str, bad_outputs))}) and are not ranked"
        )
    return 0, {
        "ok": True,
        "baseline": base,
        "noise": NOISE,
        "rows": rows,
        "partial": partial,
        "bad_outputs": bad_outputs,
        "chosen": chosen,
        "drift": drift,
        "holdout_set": holdout_set,
        "warnings": warnings,
        "csv": str(rel_dir / "ranking.csv"),
    }


def _embed_usable(path: Path, embed, source: Path | bytes | None = None) -> Face | None:
    """The main face of one image, or None if unreadable or not exactly one large face."""
    try:
        img = imaging.load_rgb(path if source is None else source)
    except imaging.ImagingError:
        return None
    info = analyze_faces(path.name, embed(imaging.to_bgr(img)))
    return None if info.main is None or info.problems else info.main


def pick_report(root: Path, run_meta: dict, embed, holdout: list[np.ndarray], warn) -> dict | None:
    """The pick of a --more-like run, re-verified and scored fresh against the
    current holdout. Problems null the pick fields and warn; they never fail rank."""
    rel = run_meta.get("chosen")
    if not rel:
        return None
    report = {
        "file": rel,
        "verified": False,
        "holdout_median": None,
        "sibling_sim": None,
        "copy_flag": "provisional: copied_generated_face is uncalibrated",
        "_emb": None,
    }
    path = root / str(rel)
    try:
        raw = path.read_bytes()
    except OSError:
        warn(f"the picked image {rel} is missing; pick comparisons are left out")
        return report
    if hashlib.sha256(raw).hexdigest() != run_meta.get("chosen_sha256"):
        warn(
            f"the picked image {rel} changed since this run used it; pick comparisons are left out"
        )
        return report
    report["verified"] = True
    pick = _embed_usable(path, embed, raw)
    if pick is None:
        warn(f"the picked image {rel} has no single usable face; pick comparisons are left out")
        return report
    report["holdout_median"] = finite(likeness(pick.embedding, holdout))
    if report["holdout_median"] is None:
        warn(f"the picked image {rel} scored as not-a-number; pick comparisons are left out")
        return report
    report["_emb"] = pick.embedding
    parent_outputs = read_run(path.parent).get("outputs") or []
    siblings = [
        f
        for name in parent_outputs
        if isinstance(name, str) and name != path.name
        for f in [_embed_usable(path.parent / name, embed)]
        if f is not None
    ]
    report["sibling_sim"] = sibling_similarity(pick.embedding, [f.embedding for f in siblings])
    if report["sibling_sim"] is None:
        warn(
            "the pick's run has no other usable outputs, so the generated-face copy flag "
            "is off for this run"
        )
    return report


def root_drift(
    root: Path,
    out_dir: Path,
    run_meta: dict,
    rows: list[dict],
    embed,
    holdout: list[np.ndarray],
    warn,
) -> dict | None:
    """Compare this run's median likeness with its root run's, both computed now."""
    root_run = run_meta.get("root_run")
    if not root_run or not run_meta.get("chosen") or root_run == out_dir.name:
        return None
    if not isinstance(root_run, str) or Path(root_run).name != root_run or root_run in (".", ".."):
        warn("run.json has an invalid root_run; drift check left out")
        return None
    run_scores = [r["holdout_median"] for r in rows if r["holdout_median"] is not None]
    if not run_scores:
        warn("no output of this run has a single usable face; drift check left out")
        return None
    root_dir = out_dir.parent / str(root_run)
    root_scores = [
        s
        for p in sorted(root_dir.glob("[0-9][0-9].png"))
        for f in [_embed_usable(p, embed)]
        if f is not None
        for s in [finite(likeness(f.embedding, holdout))]
        if s is not None
    ]
    result = drift_check(run_scores, root_scores)
    if result is None:
        warn(f"could not score root run {root_run}; drift check left out")
        return None
    return {"root_run": root_run, **result}


def main(argv=None, *, embed=None, root: Path | None = None) -> int:
    """root (tests) overrides --workspace / $HEADSHOT_WORKSPACE / cwd."""
    p = cli.JsonArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ws_help = (
        f"folder holding photos/ and out/ (default ${workspace.ENV_VAR}, then the current folder)"
    )
    p.add_argument("--workspace", metavar="DIR", help=ws_help)
    sub = p.add_subparsers(dest="cmd", required=True)
    cmds = {
        "split": sub.add_parser(
            "split", help="copy photos/inbox into photos/refs and photos/holdout"
        ),
        "check": sub.add_parser(
            "check", help="free pre-flight check of photos/refs and photos/holdout"
        ),
        "rank": sub.add_parser("rank", help="rank the outputs of a run"),
    }
    cmds["rank"].add_argument("out_dir")
    for c in cmds.values():
        c.add_argument(
            "--json", action="store_true", help="one JSON object on stdout, human text on stderr"
        )
        # Also accepted after the subcommand; SUPPRESS keeps it from clobbering the top-level one.
        c.add_argument("--workspace", metavar="DIR", default=argparse.SUPPRESS, help=ws_help)
    try:
        args = cli.parse_args(p, argv)
    except cli.UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(cli.dumps({"exit_code": 2, "ok": False, "error": str(exc)}))
        return 2
    try:
        if root is None:
            root = workspace.resolve(args.workspace)
        else:
            root = Path(root)
            workspace.validate(root)
    except workspace.WorkspaceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if args.json:
            print(cli.dumps({"exit_code": 2, "ok": False, "error": str(exc)}))
        return 2
    if embed is None:
        embed = InsightFaceEmbedder()

    def say(text=""):
        print(text, file=sys.stderr if args.json else sys.stdout)

    try:
        with cli.stdout_to_stderr(args.json):
            if args.cmd == "check":
                code, payload = cmd_check(root, embed, say)
            elif args.cmd == "split":
                code, payload = cmd_split(root, embed, say)
            else:
                code, payload = cmd_rank(root, embed, args.out_dir, say)
    except (RankError, imaging.ImagingError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        code, payload = 2, {"ok": False, "error": str(exc), **getattr(exc, "extra", {})}
    except Exception as exc:  # noqa: BLE001 - e.g. the model download failed: still one JSON object
        print(f"error: {cli.unexpected(exc)}", file=sys.stderr)
        code, payload = 4, {"ok": False, "error": cli.unexpected(exc)}
    if args.json:
        print(cli.dumps({"exit_code": code, **payload, "workspace": str(root)}))
    return code


if __name__ == "__main__":
    sys.exit(main())
