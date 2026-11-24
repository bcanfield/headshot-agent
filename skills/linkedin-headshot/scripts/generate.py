# /// script
# requires-python = ">=3.13,<3.15"
# dependencies = [
#     "openai>=3",
#     "pillow>=11",
#     "pillow-heif>=1.0",
#     "numpy>=2",
# ]
# ///
"""Generate LinkedIn headshot candidates with OpenAI image edits.

Usage (SKILL = this skill's folder; WS = the workspace holding photos/, out/ and look.toml):
    uv run SKILL/scripts/generate.py --check-key --json   # is OPENAI_API_KEY set? (never shows it)
    uv run SKILL/scripts/generate.py --workspace WS --dry-run --json   # validate look.toml, estimate
    uv run SKILL/scripts/generate.py --workspace WS --json --max-cost 1.50   # real run, only if
                                                          # the estimate's upper bound <= 1.50
    ... --from out/<ts> --background "light blue" --max-cost 1.50
    ... --more-like out/<ts>/02.png --max-cost 1.50   # more like a picked output

--workspace defaults to $HEADSHOT_WORKSPACE, then the current folder; the skill
folder itself, / and $HOME are refused. Relative paths resolve against it.

Exit codes: 0 ok, 2 user/input error, 3 needs spend approval (pass --max-cost),
4 OpenAI API error or unexpected failure. With --json, one JSON object goes to
stdout (with "error" and "exit_code" on failure) and human text to stderr;
nothing ever prompts. --max-cost must be a number above 0 and at most $10.
"""

# Must not import insightface (see rank.py).

from __future__ import annotations

import argparse
import base64
import binascii
import csv
import hashlib
import io
import json
import math
import os
import re
import secrets
import shlex
import statistics
import sys
import tomllib
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

# An installed skill folder must stay byte-identical, so sibling modules leave no __pycache__.
sys.dont_write_bytecode = True

import cli
import imaging
import workspace

DEFAULT_MODEL = "gpt-image-2.6-sunburst"
SIZE = "1024x1024"
DEFAULT_QUALITY = "high"
QUALITIES = ("low", "medium", "high")
DEFAULT_N = 4
MAX_N = 8
MIN_REFS, MAX_REFS = 3, 4
TIMEOUT_FLOOR_S = 300
TIMEOUT_PER_IMAGE_S = {"low": 30, "medium": 60, "high": 90}
# The agent's Bash tool kills a command at 600 s at most; the request must give
# up (and record itself as possibly billed) before that, whatever n is.
TIMEOUT_CAP_S = 540
MAX_COST_CAP_USD = 10.0  # --max-cost above this is refused outright (exit 2)

# Pricing per token (USD per 1M), per model. Source:
# https://developers.openai.com/api/docs/pricing, checked 2026-11-23.
# text_out: the pricing page shows "-" (no published text-output rate) for these
# models, so it is set to the image-output rate as a deliberate overestimate.
_GPT_IMAGE_2_RATES = {"image_in": 8.0, "image_out": 30.0, "text_in": 5.0, "text_out": 30.0}
PRICE_PER_M = {
    "gpt-image-2": _GPT_IMAGE_2_RATES,
    "gpt-image-2.6-sunburst": _GPT_IMAGE_2_RATES,
    "gpt-image-2.6-flare": _GPT_IMAGE_2_RATES,
}
# Rough guesses used ONLY for the pre-call estimate (low, high). OpenAI publishes
# no per-image token counts for these models; a community calculator gives about
# 196 / 1,756 / 7,024 output tokens at 1024x1024 low / medium / high, so the
# upper guesses sit above those. Recalibrate from the first real run's usage.
# Whether input is billed once per request or once per output image is unknown
# (unverified): the low bound assumes once per request, the high bound once per
# output image (the conservative case).
EST_IMAGE_IN_TOKENS_PER_REF = (700, 5000)
EST_TEXT_IN_TOKENS = 600
EST_IMAGE_OUT_TOKENS_PER_IMAGE = {
    "low": (150, 2000),
    "medium": (1200, 4500),
    "high": (2000, 9000),
}
ESTIMATE_DATE = "2026-11-23"

DEFAULT_EXPRESSION = "a natural closed-mouth smile"  # rung 3 of the skill's expression ladder
DEFAULT_LIGHTING = "soft window light from the front-left with gentle fill"
DEFAULT_FRAMING = "head-and-shoulders, chest up, face filling about 60% of the frame"
LOOK_KEYS = ("outfit", "background", "marks", "glasses", "expression", "lighting", "framing")
LOOK_DEFAULTS = {
    "marks": "",
    "glasses": "keep",
    "expression": DEFAULT_EXPRESSION,
    "lighting": DEFAULT_LIGHTING,
    "framing": DEFAULT_FRAMING,
}
REQUIRED_TEXT = ("outfit", "background", "expression", "lighting", "framing")
PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}|<[^<>]*>")
MAX_VALUE_CHARS = 120
# A look value must not be able to open a prompt block of its own or point at an
# image (which could re-target identity at the generated pick). Run on NFKC text.
_NUMBER = r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
_ORDINAL = r"(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|final|\d+(st|nd|rd|th))"
_IMAGE = r"(images?|photos?|pictures?|pics?|imgs?)"
BLOCK_LABEL_RE = re.compile(
    r"\b(identity|scene|realism|constraints)\b\s*(\([^)]*\)\s*)?(:|[-\u2013\u2014]+\s)"
    rf"|\b{_IMAGE}\s*(#|no\.?|number)?\s*{_NUMBER}\b"
    rf"|\b{_ORDINAL}\s+{_IMAGE}\b",
    re.IGNORECASE,
)
# Unicode categories a single-line, visible phrase never needs: controls (tab
# included), format characters such as zero-width spaces, line/paragraph separators.
BAD_CATEGORIES = ("Cc", "Cf", "Zl", "Zp")

# --more-like. Scene fields and expression may change together in one round; a
# glasses change goes alone; marks never change against the pick's run.
SOLO_FIELDS = ("glasses",)
PICK_COPIES = ("framing", "pose", "outfit", "background", "lighting")
PICK_STATUSES = ("ok", "partial")
DRIFT_MARGIN = 0.03  # a pick this far below its root run's median likeness is refused
DEPTH_WARN_AT = 2  # picks of picks: the skill also offers a resample from here


class GenerateError(Exception):
    """A user-facing failure (exit 2). Message is printed without a traceback."""

    code = 2

    def __init__(self, message: str, **extra):
        super().__init__(message)
        self.extra = extra


class NeedsApproval(GenerateError):
    code = 3


class ApiError(GenerateError):
    code = 4


# ---------------------------------------------------------------- prompt


def _and(items) -> str:
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def ref_images(n_refs: int) -> str:
    return f"images 1-{n_refs}"


def pick_role(n_refs: int, changed: list[str]) -> str:
    """The pick's role sentence. It copies only the scene aspects that did not
    change this round; for changed fields the model is told to ignore the pick."""
    copy = [f for f in PICK_COPIES if f not in changed]
    ignore = [f for f in LOOK_KEYS if f in changed]
    text = f"Image {n_refs + 1} is an earlier generated headshot I liked: copy its {_and(copy)}."
    if ignore:
        text += f" Ignore its {_and(ignore)}; use the {_and(ignore)} described below instead."
    return text + f" Do not copy its face: take every facial feature from {ref_images(n_refs)}."


def image_roles(n_refs: int, changed: list[str] | None = None) -> str:
    """changed is None for a run without a pick, else the look fields changed
    against the pick's run (possibly empty)."""
    if not MIN_REFS <= n_refs <= MAX_REFS:
        raise GenerateError(f"need {MIN_REFS}-{MAX_REFS} reference photos, got {n_refs}")
    text = (
        f"Images {_and([str(i) for i in range(1, n_refs + 1)])} are photos of the same real "
        f"adult, me. Image 1 is the clearest front-facing reference; images 2-{n_refs} "
        f"show other angles and lighting."
    )
    return text if changed is None else text + " " + pick_role(n_refs, changed)


def _text_problem(raw: str) -> str | None:
    """Why a look value cannot go into the prompt, or None."""
    if len(raw.splitlines()) > 1 or any(unicodedata.category(c) in BAD_CATEGORIES for c in raw):
        return (
            "must be a single line of visible text (no line breaks, tabs or invisible characters)"
        )
    value = unicodedata.normalize("NFKC", raw).strip()
    if len(value) > MAX_VALUE_CHARS:
        return f"is longer than {MAX_VALUE_CHARS} characters"
    if PLACEHOLDER_RE.search(value):
        return "contains a placeholder ({...} or <...>)"
    if BLOCK_LABEL_RE.search(value):
        return (
            "contains a prompt block label or an image reference (Identity:, Scene:, "
            "image 4, the fourth photo, ...)"
        )
    return None


def validate_look(look: dict) -> dict[str, str]:
    """Per-field problems (empty dict = valid). Defaults are applied first."""
    look = {**LOOK_DEFAULTS, **look}
    errors = {}
    for key in (*REQUIRED_TEXT, "marks"):
        raw = look.get(key, "")
        if not isinstance(raw, str):
            errors[key] = f"must be a string (got {type(raw).__name__})"
        elif not raw.strip():
            if key != "marks":
                errors[key] = "is empty"
        elif problem := _text_problem(raw):
            errors[key] = problem
    if look.get("glasses") not in ("keep", "none"):
        errors["glasses"] = "must be 'keep' or 'none'"
    return errors


def look_error(errors: dict[str, str]) -> GenerateError:
    detail = "; ".join(f"{k} {v}" for k, v in errors.items())
    return GenerateError(f"invalid look settings: {detail}", errors=errors)


def fill_prompt(template: str, look: dict, n_refs: int, changed: list[str] | None = None) -> str:
    """Fill the template. Raises if a look value is invalid or any {..} or
    <..> placeholder is left. changed: see image_roles (None = no pick)."""
    look = {**LOOK_DEFAULTS, **look}
    errors = validate_look(look)
    if errors:
        raise look_error(errors)
    marks = str(look["marks"]).strip()
    values = {
        "{image_roles}": image_roles(n_refs, changed),
        "{ref_images}": ref_images(n_refs),
        "{marks_clause}": f" ({marks})" if marks else "",
        "{glasses_sentence}": (
            f"Keep any glasses exactly as worn in {ref_images(n_refs)}."
            if look["glasses"] == "keep"
            else "No glasses."
        ),
        "{outfit}": str(look["outfit"]).strip(),
        "{background}": str(look["background"]).strip(),
        "{expression}": str(look["expression"]).strip(),
        "{lighting}": str(look["lighting"]).strip(),
        "{framing}": str(look["framing"]).strip(),
    }
    out = template
    for k, v in values.items():
        out = out.replace(k, v)
    left = PLACEHOLDER_RE.findall(out)
    if left:
        raise GenerateError(f"unfilled placeholder(s) in prompt: {', '.join(left)}")
    return out.strip() + "\n"


def load_look(path: Path) -> dict:
    try:
        data = tomllib.loads(path.read_text())
    except FileNotFoundError:
        raise GenerateError(
            f"missing {path.name}: the linkedin-headshot skill writes it (SKILL.md step 3)"
        ) from None
    except tomllib.TOMLDecodeError as exc:
        raise GenerateError(f"{path.name} is not valid TOML: {exc}") from exc
    unknown = sorted(set(data) - set(LOOK_KEYS))
    if unknown:
        raise GenerateError(
            f"{path.name} has unknown key(s): {', '.join(unknown)} "
            f"(allowed: {', '.join(LOOK_KEYS)})"
        )
    return {k: data[k] for k in LOOK_KEYS if k in data}


# ------------------------------------------------------------------ refs


def select_refs(refs_dir: Path, root: Path) -> list[Path]:
    if not refs_dir.is_dir():
        raise GenerateError(f"{refs_dir} does not exist")
    ok, skipped = imaging.list_photos(refs_dir)
    for p in skipped:
        print(f"warning: skipping unsupported file {p.name}", file=sys.stderr)
    out_dir = (root / "out").resolve()
    for p in ok:
        if p.resolve().is_relative_to(out_dir):
            raise GenerateError("generated images under out/ cannot be used as references")
    if not MIN_REFS <= len(ok) <= MAX_REFS:
        raise GenerateError(f"{refs_dir} must hold {MIN_REFS}-{MAX_REFS} photos, found {len(ok)}")
    return ok


def prepare_refs(paths: list[Path]) -> list[bytes]:
    out = []
    for p in paths:
        try:
            out.append(imaging.sanitize_for_upload(p))
        except imaging.ImagingError as exc:
            raise GenerateError(f"{p.name}: {exc}") from exc
    return out


# ------------------------------------------------------------ cost / guard


def rates(model: str) -> dict[str, float]:
    try:
        return PRICE_PER_M[model]
    except KeyError:
        raise GenerateError(
            f"no pricing known for model {model!r}, so its cost cannot be estimated or "
            f"gated. Known: {', '.join(PRICE_PER_M)}"
        ) from None


def estimate_cost(
    n: int, n_refs: int, quality: str = DEFAULT_QUALITY, model: str = DEFAULT_MODEL
) -> tuple[float, float]:
    """Rough (low, high) USD for one call. An estimate, not a quote."""
    price = rates(model)
    out_tokens = EST_IMAGE_OUT_TOKENS_PER_IMAGE[quality]
    est = []
    for i, input_copies in ((0, 1), (1, n)):  # high: input billed once per output image
        est.append(
            (
                input_copies
                * (
                    n_refs * EST_IMAGE_IN_TOKENS_PER_REF[i] * price["image_in"]
                    + EST_TEXT_IN_TOKENS * price["text_in"]
                )
                + n * out_tokens[i] * price["image_out"]
            )
            / 1e6
        )
    return est[0], est[1]


def _tokens(obj, name: str) -> int:
    value = getattr(obj, name, 0) or 0
    return value if isinstance(value, (int, float)) else 0


def cost_from_usage(usage, model: str = DEFAULT_MODEL) -> float | None:
    """USD from reported usage. Tokens the breakdowns do not account for are
    billed at the (higher) image rate, so this errs high, never low."""
    if usage is None:
        return None
    price = rates(model)
    total_in, total_out = _tokens(usage, "input_tokens"), _tokens(usage, "output_tokens")
    details = getattr(usage, "input_tokens_details", None)
    image_in, text_in = _tokens(details, "image_tokens"), _tokens(details, "text_tokens")
    image_in += max(0, total_in - image_in - text_in)
    out_details = getattr(usage, "output_tokens_details", None)
    image_out, text_out = _tokens(out_details, "image_tokens"), _tokens(out_details, "text_tokens")
    image_out += max(0, total_out - image_out - text_out)
    return (
        image_in * price["image_in"]
        + text_in * price["text_in"]
        + image_out * price["image_out"]
        + text_out * price["text_out"]
    ) / 1e6


def request_timeout(n: int, quality: str) -> int:
    return min(TIMEOUT_CAP_S, max(TIMEOUT_FLOOR_S, TIMEOUT_PER_IMAGE_S[quality] * n))


def fingerprint(
    model: str,
    prompt: str,
    ref_hashes: list[str],
    params: dict,
    chosen_upload_sha256: str | None = None,
) -> str:
    blob = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "refs": ref_hashes,
            "params": params,
            "chosen": chosen_upload_sha256,
        },
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()


# Errors that do not prove nothing was billed. Runs record this as
# "possibly_billed"; the names cover run.json files written before that key.
POSSIBLY_BILLED_ERRORS = ("APITimeoutError", "APIConnectionError", "NoValidImage")


def find_duplicate(out_root: Path, fp: str) -> tuple[str, bool] | None:
    """(run name, possibly_billed_but_unconfirmed) of an earlier identical run
    that may have been billed: ok, partial, pending, interrupted, or an error
    that does not prove nothing was billed (timeout, dropped connection)."""
    if not out_root.is_dir():
        return None
    for run in sorted(out_root.iterdir()):
        meta = run / "run.json"
        if not meta.is_file():
            continue
        try:
            data = json.loads(meta.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or data.get("fingerprint") != fp:
            continue
        status = data.get("status")
        if status in ("ok", "partial"):
            return run.name, False
        if status in ("pending", "interrupted") or (
            status == "error"
            and (data.get("possibly_billed") or data.get("error") in POSSIBLY_BILLED_ERRORS)
        ):
            return run.name, True
    return None


# ----------------------------------------------------------------- client


def make_client(http_client=None, timeout: int = TIMEOUT_FLOOR_S):
    """Real OpenAI client. No retries: a retried slow edit can bill twice."""
    from openai import OpenAI

    kwargs = {"max_retries": 0, "timeout": timeout}
    if http_client is not None:
        kwargs["http_client"] = http_client
    return OpenAI(**kwargs)


def explain_api_error(exc: Exception) -> str:
    import openai

    rid = getattr(exc, "request_id", None)
    suffix = f" (request id: {rid})" if rid else ""
    if isinstance(exc, openai.APITimeoutError):
        return (
            "the request timed out. It may still have been billed: check the OpenAI "
            "usage dashboard before running again" + suffix
        )
    if isinstance(exc, openai.APIConnectionError):
        return (
            f"could not reach OpenAI: {exc}. Nothing was retried. It may still have "
            "been billed: check the OpenAI usage dashboard before running again"
        )
    if isinstance(exc, openai.APIStatusError):
        code = getattr(exc, "code", None)
        msg = str(getattr(exc, "message", exc))
        if code == "moderation_blocked":
            return (
                "OpenAI's moderation blocked this request (code moderation_blocked). "
                "It was not retried." + suffix
            )
        if exc.status_code == 401:
            return "authentication failed: check OPENAI_API_KEY" + suffix
        if exc.status_code == 429:
            return "rate limit or quota reached; wait or check billing, then re-run" + suffix
        if exc.status_code == 403 or "verif" in msg.lower():
            return (
                "access denied. These image models may need API Organization "
                f"Verification in your OpenAI account settings. Detail: {msg}" + suffix
            )
        return f"OpenAI returned HTTP {exc.status_code} ({code or 'no code'}): {msg}" + suffix
    return str(exc)


# ------------------------------------------------------------------- run


def new_run_dir(out_root: Path) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%dT%H%M")
    path = out_root / f"{stamp}-{secrets.token_hex(2)}"
    path.mkdir(parents=True, exist_ok=False)
    workspace.protect(out_root)
    return path


def max_cost_arg(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--max-cost must be a dollar amount, got {text!r}"
        ) from None
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError(
            f"--max-cost must be a finite amount above 0, got {text!r}"
        )
    if value > MAX_COST_CAP_USD:
        raise argparse.ArgumentTypeError(
            f"--max-cost ${value:.2f} is above the hard cap of ${MAX_COST_CAP_USD:.2f}"
        )
    return value


def build_parser() -> argparse.ArgumentParser:
    p = cli.JsonArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument(
        "--workspace",
        metavar="DIR",
        help=f"folder holding photos/, out/ and look.toml (default ${workspace.ENV_VAR}, "
        "then the current folder)",
    )
    p.add_argument("--model", help=f"default {DEFAULT_MODEL}")
    p.add_argument("-n", type=int, help=f"images to generate, 1-{MAX_N} (default {DEFAULT_N})")
    p.add_argument("--quality", choices=QUALITIES, help=f"default {DEFAULT_QUALITY}")
    for key in LOOK_KEYS:
        if key == "glasses":
            p.add_argument("--glasses", choices=("keep", "none"))
        else:
            p.add_argument(f"--{key}")
    p.add_argument(
        "--from",
        dest="from_run",
        metavar="OUT_DIR",
        help="reuse look and settings of a previous run (original photos are reloaded)",
    )
    p.add_argument(
        "--more-like",
        metavar="OUT_DIR/NN.png",
        help="more like a picked output: implies --from its run; the pick is sent after "
        "the original photos as a scene reference only (the run must be ranked)",
    )
    p.add_argument(
        "--max-cost",
        type=max_cost_arg,
        metavar="USD",
        help=f"spend ceiling: run only if the estimate's upper bound is <= USD "
        f"(0 < USD <= {MAX_COST_CAP_USD:g})",
    )
    p.add_argument(
        "--check-key",
        action="store_true",
        help="report whether OPENAI_API_KEY is set (never its value), then exit",
    )
    p.add_argument("--again", action="store_true", help="allow repeating an identical run")
    p.add_argument(
        "--dry-run", action="store_true", help="validate settings and print the request, no network"
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="one JSON object on stdout, human text on stderr, never prompts",
    )
    return p


def fail(code: int, message: str, as_json: bool, **extra) -> int:
    print(f"error: {message}", file=sys.stderr)
    if as_json:
        print(cli.dumps({"ok": False, "exit_code": code, "error": message, **extra}))
    return code


def check_key(as_json: bool) -> int:
    present = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    if not present:
        return fail(
            2,
            "OPENAI_API_KEY is not set in the environment the agent was started from",
            as_json,
            key_present=False,
        )
    print("OPENAI_API_KEY is set.", file=sys.stderr if as_json else sys.stdout)
    if as_json:
        print(cli.dumps({"ok": True, "exit_code": 0, "key_present": True}))
    return 0


def main(argv=None, *, client=None, root: Path | None = None) -> int:
    """root (tests) overrides --workspace / $HEADSHOT_WORKSPACE / cwd."""
    try:
        args = cli.parse_args(build_parser(), argv)
    except cli.UsageError as exc:
        return fail(2, str(exc), True)
    if args.check_key:
        return check_key(args.json)
    try:
        if root is None:
            root = workspace.resolve(args.workspace)
        else:
            root = Path(root)
            workspace.validate(root)
    except workspace.WorkspaceError as exc:
        return fail(2, str(exc), args.json)
    ws = {"workspace": str(root)}
    result: dict = {}
    try:
        with cli.stdout_to_stderr(args.json):
            code = _run(args, client, root, result)
        text = cli.dumps({**result, **ws}) if args.json else None
    except GenerateError as exc:
        return fail(exc.code, str(exc), args.json, **exc.extra, **ws)
    except Exception as exc:  # noqa: BLE001 - never a bare traceback in place of the JSON contract
        return fail(4, cli.unexpected(exc), args.json, **ws)
    if text is not None:
        print(text)
    return code


def _abs(arg: str, root: Path) -> Path:
    path = Path(arg)
    return path if path.is_absolute() else root / path


def _real(arg: str, root: Path) -> Path:
    try:
        return _abs(arg, root).resolve()
    except (OSError, ValueError, RuntimeError) as exc:
        raise GenerateError(f"cannot resolve {arg!r}: {exc}") from exc


def check_path_args(args) -> None:
    """--more-like and --from must name something: an empty value (an unset shell
    variable) must never fall back to a fresh run from look.toml."""
    for flag, value in (("--more-like", args.more_like), ("--from", args.from_run)):
        if value is None:
            continue
        if not value.strip():
            raise GenerateError(f"{flag} needs a path (got an empty value)")
        if "\x00" in value:
            raise GenerateError(f"{flag} path contains a NUL byte")


def load_base_run(arg: str, root: Path) -> tuple[dict, Path]:
    run_dir = _abs(arg, root)
    meta = run_dir / "run.json"
    try:
        if not meta.is_file():
            raise GenerateError(f"{arg} has no run.json")
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # ValueError covers bad UTF-8 and bad JSON
        raise GenerateError(f"{arg}/run.json is unreadable: {exc}") from exc
    if not isinstance(data, dict):
        raise GenerateError(f"{arg}/run.json is not a JSON object")
    if not isinstance(data.get("look"), dict) or not data["look"]:
        raise GenerateError("that run.json has no recorded look settings")
    return data, run_dir.resolve()


# ------------------------------------------------------------- --more-like


@dataclass
class Pick:
    run: dict  # the pick's run.json
    run_dir: Path  # resolved out/<ts>
    name: str  # NN.png
    sha256: str  # raw file, as recorded in output_sha256
    upload: bytes  # sanitised JPEG sent as chosen.jpg
    upload_sha256: str
    depth: int  # depth of the new run
    root_run: str  # depth-0 ancestor
    score: float  # the pick's holdout likeness, from its run's ranking.csv
    root_median: float  # median likeness of the root run, from its ranking.csv

    @property
    def rel(self) -> str:
        return f"out/{self.run_dir.name}/{self.name}"


@dataclass
class Ranking:
    scores: dict[str, float | None]  # file name -> holdout_median; None = unscored
    multi_face: set[str]  # outputs with more than one large face (unscored)
    holdout_set: str | None  # imaging.holdout_set when ranked; None = unknown


def _finite_or_none(text) -> float | None:
    try:
        value = float((text or "").strip())
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def read_ranking(run_dir: Path) -> Ranking | None:
    """A run's ranking.csv, or None if not ranked. Multi-face and non-finite
    scores count as unscored, as rank.py treats them."""
    path = run_dir / "ranking.csv"
    scores, multi, sets = {}, set(), set()
    try:
        if not path.is_file():
            return None
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                name = Path(row.get("file") or "").name
                faces = _finite_or_none(row.get("large_faces"))
                if (faces is not None and faces > 1) or "large faces" in (row.get("flags") or ""):
                    multi.add(name)
                    scores[name] = None
                else:
                    scores[name] = _finite_or_none(row.get("holdout_median"))
                sets.add((row.get("holdout_set") or "").strip())
    except (OSError, ValueError, csv.Error) as exc:  # ValueError covers bad UTF-8
        raise GenerateError(
            f"out/{run_dir.name}/ranking.csv is unreadable: {exc}; "
            f"re-rank it (rank.py rank out/{run_dir.name})"
        ) from exc
    holdout = sets.pop() if len(sets) == 1 else None
    return Ranking(scores, multi, holdout or None)


def ranking_scores(run_dir: Path) -> dict[str, float | None] | None:
    """{file name: holdout_median} from a run's ranking.csv; None if not ranked."""
    ranking = read_ranking(run_dir)
    return None if ranking is None else ranking.scores


def load_pick(arg: str, root: Path, from_arg: str | None) -> Pick:
    """Accept a pick only if it is a verified output of a finished, ranked run."""
    out_root = (root / "out").resolve()
    real = _real(arg, root)
    if real.is_relative_to((root / "photos").resolve()):
        raise GenerateError(
            "--more-like takes a generated image from out/, never a photo from photos/"
        )
    if real.parent.parent != out_root:
        raise GenerateError(
            f"--more-like must name an image directly inside out/<run>/ (got {arg})"
        )
    run_dir, name = real.parent, real.name
    data, _ = load_base_run(f"out/{run_dir.name}", root)
    if data.get("status") not in PICK_STATUSES:
        raise GenerateError(
            f"out/{run_dir.name} did not finish (status "
            f"{data.get('status')!r}); pick from a finished run"
        )
    outputs = data.get("outputs")
    if not isinstance(outputs, list) or name not in outputs:
        raise GenerateError(f"{name} is not one of the images out/{run_dir.name} produced")
    hashes = data.get("output_sha256")
    if not isinstance(hashes, dict) or not hashes.get(name):
        raise GenerateError(
            f"out/{run_dir.name} predates pick verification (no output "
            "hashes); pick from a newer run, or re-run"
        )
    if from_arg is not None and _real(from_arg, root) != run_dir:
        raise GenerateError(
            "--from and --more-like name different runs; --more-like already "
            "implies --from its own run"
        )
    try:
        raw = real.read_bytes()  # read once: hash and upload the same bytes
    except OSError as exc:
        raise GenerateError(f"cannot read {arg}: {exc}") from exc
    sha = hashlib.sha256(raw).hexdigest()
    if sha != hashes[name]:
        raise GenerateError(
            f"{arg} changed since OpenAI returned it (sha256 differs from "
            "run.json); pick an unedited output"
        )

    ranking = read_ranking(run_dir)
    if ranking is None:
        raise GenerateError(
            f"out/{run_dir.name} has no ranking.csv: rank first (rank.py rank out/{run_dir.name})"
        )
    root_run = data.get("root_run") or run_dir.name
    if (
        not isinstance(root_run, str)
        or Path(root_run).name != root_run
        or root_run in ("", ".", "..")
    ):
        raise GenerateError(f"out/{run_dir.name}/run.json has an invalid root_run")
    root_ranking = ranking if root_run == run_dir.name else read_ranking(out_root / root_run)
    if root_ranking is None:
        raise GenerateError(
            f"root run out/{root_run} has no ranking.csv: rank it first "
            f"(rank.py rank out/{root_run})"
        )
    # Scores move with the holdout photos, so both rankings must be against today's set.
    try:
        current = imaging.holdout_set(root / "photos" / "holdout")
    except OSError as exc:
        raise GenerateError(f"cannot read photos/holdout: {exc}") from exc
    stale = [
        r
        for r, rk in ((run_dir.name, ranking), (root_run, root_ranking))
        if rk.holdout_set != current
    ]
    stale = list(dict.fromkeys(stale))
    if stale:
        raise GenerateError(
            "photos/holdout changed since "
            + " and ".join(f"out/{r}" for r in stale)
            + (" were" if len(stale) > 1 else " was")
            + " ranked (or ranked before rank.py recorded the holdout set); re-rank: "
            + "; ".join(f"rank.py rank out/{r}" for r in stale),
            stale_rankings=stale,
        )
    if name in ranking.multi_face:
        raise GenerateError(f"{name} has more than one large face, so it is unscored; pick another")
    score = ranking.scores.get(name)
    if score is None:
        raise GenerateError(
            f"{name} has no likeness score in out/{run_dir.name}/ranking.csv "
            "(no usable face, or ranked before it existed); pick another"
        )
    root_values = [v for v in root_ranking.scores.values() if v is not None]
    if not root_values:
        raise GenerateError(
            f"root run out/{root_run} has no scored outputs in its ranking.csv; "
            f"re-rank it (rank.py rank out/{root_run})"
        )
    root_median = statistics.median(root_values)
    if score < root_median - DRIFT_MARGIN:
        raise GenerateError(
            f"{name} scores {score:.3f}, more than {DRIFT_MARGIN} below the root run's median "
            f"{root_median:.3f}: its face has drifted. Resample instead: --from "
            f"out/{run_dir.name} with no pick (keeps that run's look)",
            pick_score=round(score, 4),
            root_median=round(root_median, 4),
            root_run=root_run,
        )
    try:
        upload = imaging.sanitize_for_upload(raw)
    except imaging.ImagingError as exc:
        raise GenerateError(f"{arg}: {exc}") from exc
    try:
        parent_depth = int(data.get("depth") or 0)
    except (TypeError, ValueError):
        parent_depth = 0
    return Pick(
        data,
        run_dir,
        name,
        sha,
        upload,
        hashlib.sha256(upload).hexdigest(),
        parent_depth + 1,
        root_run,
        score,
        root_median,
    )


def changed_fields(look: dict, parent_look: dict) -> list[str]:
    parent = {**LOOK_DEFAULTS, **parent_look}
    return [k for k in LOOK_KEYS if str(look.get(k, "")).strip() != str(parent.get(k, "")).strip()]


def check_round(changed: list[str]) -> None:
    """--more-like: scene fields and expression may change together; glasses
    alone; marks never."""
    if "marks" in changed:
        raise GenerateError(
            "--more-like cannot change marks; they come from your photos. "
            "Start a new run from look.toml instead",
            changed=changed,
        )
    solo = [f for f in changed if f in SOLO_FIELDS]
    if solo and len(changed) > 1:
        raise GenerateError(
            f"--more-like changes {solo[0]} only in a round of its own "
            f"(this round changes {', '.join(changed)})",
            changed=changed,
        )


def depth_warning(depth: int, pick_run: str | None) -> str | None:
    """Same resample recipe as the skill: --from the pick's own run, no pick."""
    if depth < DEPTH_WARN_AT:
        return None
    return (
        f"depth {depth}: a pick of a pick. The face still comes from your photos, but the "
        f"look may converge or drift. To resample instead: --from out/{pick_run} with no "
        "pick (keeps that run's look)"
    )


def _run(args, client, root: Path, result: dict) -> int:
    """Do the work; put the --json payload in `result` and return the exit code."""

    def say(*parts):
        print(*parts, file=sys.stderr if args.json else sys.stdout)

    check_path_args(args)
    pick = load_pick(args.more_like, root, args.from_run) if args.more_like is not None else None
    base_run, base_dir = (
        (pick.run, pick.run_dir)
        if pick
        else load_base_run(args.from_run, root)
        if args.from_run is not None
        else (None, None)
    )
    look = {**LOOK_DEFAULTS, **(base_run["look"] if base_run else load_look(root / "look.toml"))}
    for key in LOOK_KEYS:
        val = getattr(args, key)
        if val is not None:
            look[key] = val
    changed = changed_fields(look, base_run["look"]) if pick else None
    depth = pick.depth if pick else 0
    lineage = {
        "parent_run": base_dir.name if base_dir else None,
        "root_run": pick.root_run if pick else None,  # a run without a pick is its own root
        "depth": depth,
        "depth_warning": depth_warning(depth, pick.run_dir.name if pick else None),
        "more_like": None
        if pick is None
        else {
            "chosen": pick.rel,
            "changed": changed,
            "pick_score": round(pick.score, 4),
            "root_median": round(pick.root_median, 4),
        },
    }

    prev = (base_run or {}).get("params", {})
    prev = prev if isinstance(prev, dict) else {}
    model = args.model or (base_run or {}).get("model") or DEFAULT_MODEL
    rates(model)  # unknown pricing: refuse before anything else
    try:
        n = args.n if args.n is not None else int(prev.get("n", DEFAULT_N))
    except (TypeError, ValueError):
        raise GenerateError("that run.json has an invalid image count") from None
    quality = args.quality or prev.get("quality", DEFAULT_QUALITY)
    if quality not in QUALITIES:
        raise GenerateError(f"quality must be one of {', '.join(QUALITIES)} (got {quality!r})")
    if not 1 <= n <= MAX_N:
        raise GenerateError(f"-n must be between 1 and {MAX_N}")
    params = {"n": n, "size": SIZE, "quality": quality}

    errors = validate_look(look)
    ref_paths, refs = [], []
    try:
        ref_paths = select_refs(root / "photos" / "refs", root)
        refs = prepare_refs(ref_paths)
    except GenerateError as exc:
        errors["refs"] = str(exc)
    if errors:
        raise (
            look_error(errors)
            if set(errors) != {"refs"}
            else GenerateError(errors["refs"], errors=errors)
        )
    if pick:
        check_round(changed)

    ref_hashes = [hashlib.sha256(b).hexdigest() for b in refs]
    if base_run and base_run.get("refs") != {f"ref{i}": h for i, h in enumerate(ref_hashes, 1)}:
        raise GenerateError(
            "photos/refs no longer matches the photos used in that run "
            "(hashes or count differ); restore them or run without --from"
        )

    try:
        template = workspace.PROMPT_PATH.read_text()  # bundled with the skill, never the workspace
    except OSError as exc:
        raise GenerateError(f"cannot read prompt.txt: {exc}") from exc
    prompt = fill_prompt(template, look, len(refs), changed)
    fp = fingerprint(model, prompt, ref_hashes, params, pick.upload_sha256 if pick else None)
    dup = find_duplicate(root / "out", fp)

    # The pick is one more input image.
    lo, hi = estimate_cost(n, len(refs) + (1 if pick else 0), quality, model)
    chosen_note = f" + chosen.jpg (scene reference: {pick.rel})" if pick else ""
    summary = (
        f"model: {model}\nimages: n={n}, size={SIZE}, quality={quality}\n"
        f"references: {len(refs)} (sent as ref1..ref{len(refs)}.jpg){chosen_note}\n"
        f"estimated cost: ${lo:.2f} to ${hi:.2f} (ESTIMATE as of {ESTIMATE_DATE}; "
        f"OpenAI bills by tokens, the real cost is recorded in run.json)"
    )

    if args.dry_run:
        say("DRY RUN: no network call, nothing written.\n")
        say(prompt)
        ref_info = []
        for i, (p, data, h) in enumerate(zip(ref_paths, refs, ref_hashes), 1):
            with Image.open(io.BytesIO(data)) as im:
                dims = f"{im.width}x{im.height}"
            say(f"ref{i}: {p.name} -> {dims}, {len(data) // 1024} KB, sha256 {h[:12]}")
            ref_info.append({"ref": f"ref{i}", "file": p.name, "size": dims, "sha256": h})
        say(summary)
        if lineage["depth_warning"]:
            say(f"warning: {lineage['depth_warning']}")
        if dup:
            say(f"note: identical to earlier run {dup[0]}; a real run needs --again")
        result.update(
            {
                "ok": True,
                "exit_code": 0,
                "dry_run": True,
                "errors": {},
                "model": model,
                "params": params,
                "look": look,
                "prompt": prompt,
                "refs": ref_info,
                "estimate_usd": [round(lo, 4), round(hi, 4)],
                "duplicate_of": dup[0] if dup else None,
                # True: that run finished and its images exist (rank them instead).
                "duplicate_finished": (not dup[1]) if dup else None,
                **lineage,
            }
        )
        return 0

    if dup and not args.again:
        name, unsure = dup
        if unsure:
            raise GenerateError(
                f"an identical run (out/{name}) may already have been billed (it was "
                "interrupted, timed out or never finished). Check the OpenAI usage "
                "dashboard, then pass --again to repeat",
                duplicate_of=name,
            )
        raise GenerateError(
            f"identical run already exists (out/{name}); pass --again to repeat", duplicate_of=name
        )

    say(summary)
    if args.max_cost is None or not (hi <= args.max_cost):
        ceiling = (
            "no --max-cost given" if args.max_cost is None else f"--max-cost ${args.max_cost:.2f}"
        )
        raise NeedsApproval(
            f"spend approval needed: estimate upper bound ${hi:.2f} vs {ceiling}. "
            "Re-run with --max-cost USD (at least the upper bound) once the human approves",
            estimate_usd=[round(lo, 4), round(hi, 4)],
            max_cost=args.max_cost,
            **lineage,
        )

    if client is None:
        if not os.environ.get("OPENAI_API_KEY"):
            raise GenerateError("OPENAI_API_KEY is not set")
        client = make_client(timeout=request_timeout(n, quality))

    import openai

    run_dir = new_run_dir(root / "out")
    record = {
        "status": "pending",
        "timestamp": datetime.now(UTC).isoformat(),
        "model": model,
        "prompt": prompt,
        "look": look,
        "params": params,
        "refs": {f"ref{i}": h for i, h in enumerate(ref_hashes, 1)},
        "fingerprint": fp,
        "sdk_version": openai.__version__,
        "estimate_usd": [round(lo, 4), round(hi, 4)],
        "max_cost": args.max_cost,
        "parent_run": lineage["parent_run"],
        "root_run": pick.root_run if pick else run_dir.name,
        "depth": depth,
    }
    if pick:  # the pick itself is never copied into this run folder
        record.update(
            {
                "chosen": pick.rel,
                "chosen_sha256": pick.sha256,
                "chosen_upload_sha256": pick.upload_sha256,
                "changed_fields": changed,
            }
        )
    lineage["root_run"] = record["root_run"]
    meta_path = run_dir / "run.json"

    def save():
        meta_path.write_text(cli.dumps(record, indent=2) + "\n")

    save()
    print(
        f"run dir: out/{run_dir.name} (calling OpenAI; this can take several minutes)",
        file=sys.stderr,
    )
    files = [(f"ref{i}.jpg", data, "image/jpeg") for i, data in enumerate(refs, 1)]
    if pick:
        files.append(("chosen.jpg", pick.upload, "image/jpeg"))
    try:
        resp = client.images.edit(
            model=model, image=files, prompt=prompt, n=n, size=SIZE, quality=quality
        )
    except Exception as exc:
        # An HTTP error status means OpenAI answered and refused; anything else
        # (timeout, dropped connection, a bug) may have reached it and been billed.
        billed = not isinstance(exc, openai.APIStatusError)
        record["status"] = "error"
        record["error"] = type(exc).__name__
        record["possibly_billed"] = billed
        record["request_id"] = getattr(exc, "request_id", None)
        save()
        if isinstance(exc, openai.OpenAIError):
            msg = explain_api_error(exc)
        else:
            msg = (
                f"{cli.unexpected(exc)} during the OpenAI call. It may have been billed: "
                "check the OpenAI usage dashboard before running again"
            )
        raise ApiError(
            msg,
            request_id=record["request_id"],
            run_dir=f"out/{run_dir.name}",
            possibly_billed=billed,
        ) from exc
    except BaseException:  # Ctrl-C: the server may still finish and bill
        record["status"] = "interrupted"
        save()
        raise

    usage = getattr(resp, "usage", None)
    record["request_id"] = getattr(resp, "_request_id", None)
    record["created"] = getattr(resp, "created", None)
    record["usage"] = usage.model_dump() if usage is not None else None
    record["cost_usd"] = cost_from_usage(usage, model)
    record["over_ceiling"] = (
        None if record["cost_usd"] is None else record["cost_usd"] > args.max_cost
    )
    for key in ("size", "quality", "output_format"):
        record[f"returned_{key}"] = getattr(resp, key, None)
    save()  # usage and request id are on disk before any image is touched

    written, bad, hashes = [], [], {}
    for i, item in enumerate(resp.data or [], 1):
        b64 = getattr(item, "b64_json", None)
        if not b64:
            continue
        path = run_dir / f"{i:02d}.png"
        try:
            raw = base64.b64decode(b64, validate=True)
            path.write_bytes(raw)
            with Image.open(path) as im:
                im.load()
        except (binascii.Error, ValueError, OSError) as exc:
            print(f"warning: output {i:02d} is not a valid image: {exc}", file=sys.stderr)
            if path.exists():
                path = path.rename(path.with_suffix(".bad"))
            bad.append(path.name if path.exists() else f"{i:02d}")
            continue
        written.append(path.name)
        hashes[path.name] = hashlib.sha256(raw).hexdigest()
    record["outputs"] = written
    record["output_sha256"] = hashes  # --more-like accepts only these exact bytes
    if bad:
        record["bad_outputs"] = bad
    record["status"] = "error" if not written else ("partial" if bad else "ok")
    error = None
    if not written:
        record["error"] = "NoValidImage"
        record["possibly_billed"] = True
        cost = "" if record["cost_usd"] is None else f" (billed ${record['cost_usd']:.4f})"
        error = (
            f"OpenAI returned no valid image{cost}. The run was recorded as possibly "
            "billed; check the OpenAI usage dashboard before running again"
        )
    save()

    say(f"\nwrote {len(written)} image(s) to out/{run_dir.name}/")
    if record["cost_usd"] is not None:
        say(f"cost from usage: ${record['cost_usd']:.4f} (request id {record['request_id']})")
        if record["over_ceiling"]:
            say(f"warning: the real cost is above the approved ceiling of ${args.max_cost:.2f}")
    if error:
        print(f"error: {error}", file=sys.stderr)
    else:
        rank_py = Path(__file__).resolve().with_name("rank.py")
        say(
            f"next: uv run {shlex.quote(str(rank_py))} --workspace {shlex.quote(str(root))} "
            f"rank out/{run_dir.name}"
        )
    code = 0 if written else 4
    result.update(
        {
            "ok": bool(written),
            "exit_code": code,
            "status": record["status"],
            "run_dir": f"out/{run_dir.name}",
            "outputs": written,
            "bad_outputs": bad,
            "cost_usd": record["cost_usd"],
            "max_cost": args.max_cost,
            "over_ceiling": record["over_ceiling"],
            "request_id": record["request_id"],
            "estimate_usd": record["estimate_usd"],
            **lineage,
        }
    )
    if error:
        result["error"] = error
    return code


if __name__ == "__main__":
    sys.exit(main())
