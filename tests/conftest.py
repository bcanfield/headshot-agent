import base64
import csv
import hashlib
import io
import json
import shutil
import socket
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

import generate
import imaging
from rank import Face

PROJECT = Path(__file__).resolve().parent.parent

# A fixed look for tests, so an agent-written project look.toml never changes results.
FIXTURE_LOOK = """\
outfit = "a plain charcoal blazer over a white shirt"
background = "plain mid-grey"
marks = ""
glasses = "keep"
expression = "a natural closed-mouth smile"
lighting = "soft window light from the front-left with gentle fill"
"""


@pytest.fixture(autouse=True)
def no_network(monkeypatch, request):
    """No real key, no sockets. The opt-in slow test is exempt (model download)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    if request.node.get_closest_marker("slow"):
        return

    def blocked(*a, **k):
        raise AssertionError("network access attempted in a test")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


def png_bytes(color=(10, 20, 30), size=(16, 16)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def project(tmp_path):
    """A throwaway project root with synthetic (non-face) refs."""
    shutil.copy(PROJECT / "prompt.txt", tmp_path / "prompt.txt")
    (tmp_path / "look.toml").write_text(FIXTURE_LOOK)
    refs = tmp_path / "photos" / "refs"
    refs.mkdir(parents=True)
    (tmp_path / "photos" / "holdout").mkdir()
    for i, color in enumerate([(200, 30, 30), (30, 200, 30), (30, 30, 200)], 1):
        Image.new("RGB", (64, 48), color).save(refs / f"IMG_{i}.jpg")
    return tmp_path


# Shared test helpers

PALETTE = [
    (250, 10, 10),
    (10, 250, 10),
    (10, 10, 250),
    (250, 250, 10),
    (250, 10, 250),
    (10, 250, 250),
    (128, 128, 10),
    (10, 128, 128),
]


def png(color, size=(16, 16)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


DIM = 12


def dirs(project) -> set[Path]:
    out = project / "out"
    return set(out.iterdir()) if out.is_dir() else set()


def make_run(project, *argv, client=None, expect=0) -> Path:
    before = dirs(project)
    assert run(project, *OK, *argv, client=client or VariedClient()) == expect
    [new] = dirs(project) - before
    return new


def write_ranking(
    run_dir: Path,
    scores: dict[str, float | None],
    holdout_set=None,
    large_faces: dict[str, int] | None = None,
) -> None:
    """A ranking.csv with the columns generate reads (file, holdout_median,
    large_faces, holdout_set). holdout_set defaults to the project's current one."""
    if holdout_set is None:
        holdout_set = imaging.holdout_set(run_dir.parent.parent / "photos" / "holdout")
    with (run_dir / "ranking.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rank", "file", "holdout_median", "large_faces", "holdout_set"])
        for i, (name, s) in enumerate(scores.items(), 1):
            w.writerow(
                [
                    i,
                    f"out/{run_dir.name}/{name}",
                    "" if s is None else f"{s:.4f}",
                    (large_faces or {}).get(name, 1),
                    holdout_set,
                ]
            )


def ranked_parent(project, scores=None) -> Path:
    d = make_run(project)
    write_ranking(d, scores or {"01.png": 0.62, "02.png": 0.60, "03.png": 0.58, "04.png": 0.55})
    return d


def jrun(project, capsys, *argv, client=None):
    capsys.readouterr()  # drop output from earlier non-JSON runs
    code = run(project, "--json", *argv, client=client)
    return code, json.loads(capsys.readouterr().out)


def ident(i, a=0.8):
    """Same person: shared direction plus a per-image part (bigger a = less alike)."""
    v = np.ones(DIM) / np.sqrt(DIM) + a * np.eye(DIM)[i % DIM]
    return v


class ColourEmbed:
    """Solid-colour images; the colour picks the embedding. Unknown colour = no face."""

    def __init__(self):
        self.table = {}

    def add(self, path: Path, color, emb):
        Image.new("RGB", (64, 64), color).save(path, format="PNG")
        self.table[color] = emb

    def __call__(self, bgr):
        b, g, r = (round(float(bgr[:, :, c].mean())) for c in range(3))
        emb = self.table.get((r, g, b))
        return [] if emb is None else [Face((0, 0, 300, 300), np.asarray(emb, float))]


def rank_project(tmp_path):
    """photos/{refs,holdout}, a parent run (4 outputs) and a --more-like child (3)."""
    E = ColourEmbed()
    for sub, base in (("refs", 0), ("holdout", 3)):
        d = tmp_path / "photos" / sub
        d.mkdir(parents=True)
        for i in range(3):
            E.add(d / f"p{i}.png", (200, 10 + base * 10 + i * 10, 10), ident(base + i))
    parent = tmp_path / "out" / "parent"
    parent.mkdir(parents=True)
    hashes = {}
    for i in range(4):
        E.add(parent / f"{i + 1:02d}.png", (10, 200, 10 + i * 10), ident(6 + i, 0.9))
        hashes[f"{i + 1:02d}.png"] = hashlib.sha256(
            (parent / f"{i + 1:02d}.png").read_bytes()
        ).hexdigest()
    (parent / "run.json").write_text(
        json.dumps(
            {
                "status": "ok",
                "outputs": list(hashes),
                "output_sha256": hashes,
                "root_run": "parent",
                "depth": 0,
            }
        )
    )
    child = tmp_path / "out" / "child"
    child.mkdir()
    for i in range(3):
        E.add(child / f"{i + 1:02d}.png", (10, 10, 200 - i * 10), ident(9 + i, 0.9))
    (child / "run.json").write_text(
        json.dumps(
            {
                "status": "ok",
                "outputs": ["01.png", "02.png", "03.png"],
                "chosen": "out/parent/02.png",
                "chosen_sha256": hashes["02.png"],
                "root_run": "parent",
                "parent_run": "parent",
                "depth": 1,
            }
        )
    )
    return tmp_path, E


OK = ("--max-cost", "10")


TEMPLATE = (PROJECT / "prompt.txt").read_text()


class FakeClient:
    def __init__(self, n_images=4, fail=None):
        self.calls = []
        self.images = SimpleNamespace(edit=self.edit)
        self.n_images, self.fail = n_images, fail

    def edit(self, **kw):
        self.calls.append(kw)
        if self.fail:
            raise self.fail
        b64 = base64.b64encode(png_bytes()).decode()
        return SimpleNamespace(
            data=[SimpleNamespace(b64_json=b64) for _ in range(self.n_images)],
            usage=SimpleNamespace(
                input_tokens=2000,
                output_tokens=5000,
                total_tokens=7000,
                input_tokens_details=SimpleNamespace(image_tokens=1500, text_tokens=500),
                model_dump=lambda: {"input_tokens": 2000, "output_tokens": 5000},
            ),
            created=123,
            size="1024x1024",
            quality="high",
            output_format="png",
            _request_id="req_abc",
        )


def run(project, *argv, client=None):
    return generate.main(list(argv), client=client, root=project)


def mock_client(handler):
    httpx2 = pytest.importorskip("httpx2")
    http = httpx2.Client(transport=httpx2.MockTransport(handler))
    return generate.make_client(http_client=http), httpx2


class VariedClient(FakeClient):
    """Distinct bytes per output, so outputs have distinct hashes."""

    def edit(self, **kw):
        resp = super().edit(**kw)
        resp.data = [
            SimpleNamespace(b64_json=base64.b64encode(png(PALETTE[i])).decode())
            for i in range(self.n_images)
        ]
        return resp
