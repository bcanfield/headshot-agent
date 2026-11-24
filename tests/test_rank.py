import csv
import json

import numpy as np
import pytest
from PIL import Image

import rank
from rank import Face


def vec(*xs):
    return np.array(xs, dtype=float)


def face(emb, size=300):
    return Face((0, 0, size, size), np.asarray(emb, dtype=float))


def test_analyze_faces_counts_large_only():
    big, small, tiny = face(vec(1, 0), 300), face(vec(0, 1), 100), face(vec(1, 1), 200)
    assert rank.analyze_faces("a", []).problems == ["no face found"]
    info = rank.analyze_faces("a", [small, big])
    assert info.main is big and info.n_large == 1 and not info.problems
    assert rank.analyze_faces("a", [big, tiny]).n_large == 2  # 200^2 > 25% of 300^2


def test_baseline():
    b = rank.baseline([vec(1, 0), vec(0, 1), vec(1, 1)])
    assert (
        b["pairs"] == 3
        and b["min"] == pytest.approx(0)
        and b["max"] == pytest.approx(0.7071, abs=1e-3)
    )
    assert rank.baseline([vec(1, 0)]) is None


def test_holdout_only_scoring_and_order():
    holdout = [vec(1, 0, 0), vec(0.9, 0.1, 0)]
    rank.baseline(holdout)
    refs = [vec(0, 1, 0)]  # refs deliberately far from holdout
    good = rank.analyze_faces("01.png", [face(vec(1, 0.05, 0))])
    bad = rank.analyze_faces("02.png", [face(vec(0, 1, 0))])  # identical to a ref
    nofac = rank.analyze_faces("03.png", [])
    rows = rank.score_outputs([bad, nofac, good], holdout, refs)
    assert [r["file"] for r in rows] == ["01.png", "02.png", "03.png"]
    assert rows[0]["holdout_median"] > 0.95 and not rows[0]["likely_copy"]
    assert rows[2]["holdout_median"] is None and "no face found" in rows[2]["flags"]


def test_copy_flag_is_per_output_margin():
    holdout = [vec(1, 0), vec(0.8, 0.6)]
    ref = vec(0, 1)
    copy = rank.analyze_faces("01.png", [face(vec(0, 1))])  # ref 1.0 vs holdout median ~0.4
    close = rank.analyze_faces(
        "02.png", [face(vec(0.3, 1))]
    )  # ref 0.96, holdout median ~0.6: margin 0.3? see below
    faithful = rank.analyze_faces("03.png", [face(vec(1, 0.9))])  # ref ~0.67, holdout median ~0.8
    rows = {r["file"]: r for r in rank.score_outputs([copy, close, faithful], holdout, [ref])}
    assert rows["01.png"]["likely_copy"]
    assert not rows["03.png"]["likely_copy"]
    for r in rows.values():
        assert r["likely_copy"] == (r["max_ref_sim"] - r["holdout_median"] > rank.COPY_MARGIN)


def test_copy_flag_not_fooled_by_low_baseline_max():
    # old rule (max_ref_sim > baseline max) flagged this good output; the margin rule must not.
    holdout = [vec(1, 0), vec(0.5, 0.87)]  # baseline max 0.5
    ref = vec(0.3, 0.95)
    out = rank.analyze_faces("01.png", [face(vec(0.8, 0.6))])
    [row] = rank.score_outputs([out], holdout, [ref])
    assert row["max_ref_sim"] > 0.5 and not row["likely_copy"]


def test_c2m1_scoring_uses_holdout_only_not_refs():
    """Scoring against holdout+refs would reverse this order."""
    holdout = [vec(1, 0, 0), vec(0.9, 0.2, 0), vec(0.8, 0, 0.3)]
    refs = [vec(0, 1, 0), vec(0, 0.9, 0.1), vec(0.1, 1, 0)]
    a_matches_refs = rank.analyze_faces("01.png", [face(vec(0, 1, 0))])
    b_matches_holdout = rank.analyze_faces("02.png", [face(vec(1, 0.1, 0.05))])
    rows = rank.score_outputs([a_matches_refs, b_matches_holdout], holdout, refs)
    assert [r["file"] for r in rows] == ["02.png", "01.png"]
    row_a = next(r for r in rows if r["file"] == "01.png")
    assert row_a["holdout_median"] == pytest.approx(
        float(np.median([rank.cosine(vec(0, 1, 0), h) for h in holdout]))
    )
    # the refs would have made A the winner
    both = [*holdout, *refs]
    assert np.median([rank.cosine(vec(0, 1, 0), h) for h in both]) > np.median(
        [rank.cosine(vec(1, 0.1, 0.05), h) for h in both]
    )


def test_near_duplicates():
    d = rank.near_duplicates([("a", vec(1, 0)), ("b", vec(1, 0.01)), ("c", vec(0, 1))])
    assert [(x[0], x[1]) for x in d] == [("a", "b")]


# --------------------------------------------------------- CLI with a fake embedder


def make_project(tmp_path, n_refs=3, n_hold=3, n_out=3):
    for sub, n in (("refs", n_refs), ("holdout", n_hold)):
        d = tmp_path / "photos" / sub
        d.mkdir(parents=True)
        for i in range(n):
            Image.new(
                "RGB", (400, 400), (i * 20 + 10 + (100 if sub == "holdout" else 0), 0, 0)
            ).save(d / f"p{i}.png")
    out = tmp_path / "out" / "run1"
    out.mkdir(parents=True)
    for i in range(n_out):
        Image.new("RGB", (400, 400), (0, i * 20 + 10, 0)).save(out / f"{i + 1:02d}.png")
    return tmp_path


def fake_embed(bgr):
    """Embed by the red-ish channel so each fake photo is distinguishable.
    Photos in out/ have green set, photos in photos/ have red set."""
    _b, g, r = (float(bgr[:, :, c].mean()) for c in range(3))
    theta = r / 255.0 * np.pi
    emb = np.array([np.cos(theta), np.sin(theta), 3 * g / 255.0])
    return [Face((0, 0, 300, 300), emb)]


def test_check_ok_and_problems(tmp_path, capsys):
    root = make_project(tmp_path)
    assert rank.main(["check"], embed=fake_embed, root=root) == 0
    assert "baseline" in capsys.readouterr().out

    root2 = make_project(tmp_path / "b", n_hold=1)
    assert rank.main(["check"], embed=fake_embed, root=root2) == 2

    root3 = make_project(tmp_path / "c")
    assert rank.main(["check"], embed=lambda bgr: [], root=root3) == 2


def test_rank_writes_csv_with_relative_paths(tmp_path, capsys):
    root = make_project(tmp_path)
    assert rank.main(["rank", "out/run1"], embed=fake_embed, root=root) == 0
    text = capsys.readouterr().out
    assert "noise" in text and "baseline" in text
    rows = list(csv.DictReader((root / "out" / "run1" / "ranking.csv").open()))
    assert len(rows) == 3
    assert rows[0]["file"].startswith("out/run1/") and str(tmp_path) not in rows[0]["file"]


def test_rank_needs_holdout(tmp_path):
    root = make_project(tmp_path, n_hold=1)
    assert rank.main(["rank", "out/run1"], embed=fake_embed, root=root) == 2


def test_embedder_receives_bgr(tmp_path):
    seen = []
    red = tmp_path / "red.heic"
    import pillow_heif  # noqa: F401

    Image.new("RGB", (64, 64), (255, 0, 0)).save(red, "HEIF")

    def spy(bgr):
        seen.append(bgr)
        return []

    rank.embed_path(red, spy)
    b, _g, r = seen[0][32, 32]
    assert r > 200 and b < 60


# ----------------------------------------------------- json, check, split, rank


def test_check_json_one_object_and_exit_codes(tmp_path, capsys):
    root = make_project(tmp_path)
    assert rank.main(["check", "--json"], embed=fake_embed, root=root) == 0
    cap = capsys.readouterr()
    d = json.loads(cap.out)
    assert d["ok"] and d["exit_code"] == 0 and len(d["refs"]) == 3 and d["baseline"]
    assert "baseline" in cap.err
    assert (
        rank.main(["check", "--json"], embed=lambda bgr: [], root=make_project(tmp_path / "x")) == 2
    )
    d = json.loads(capsys.readouterr().out)
    assert not d["ok"] and d["exit_code"] == 2 and d["problems"]


def test_check_fails_on_ref_holdout_duplicate(tmp_path, capsys):
    root = make_project(tmp_path)
    # same image (and so the same fake embedding) in refs and holdout
    Image.new("RGB", (400, 400), (10, 0, 0)).save(root / "photos" / "holdout" / "p0.png")
    assert rank.main(["check", "--json"], embed=fake_embed, root=root) == 2
    d = json.loads(capsys.readouterr().out)
    assert any(x["cross_group"] for x in d["near_duplicates"])


def test_rank_json_and_unreadable_output(tmp_path, capsys):
    root = make_project(tmp_path)
    (root / "out" / "run1" / "02.png").write_bytes(b"garbage")
    assert rank.main(["rank", "out/run1", "--json"], embed=fake_embed, root=root) == 0
    d = json.loads(capsys.readouterr().out)
    flags = {r["file"]: r["flags"] for r in d["rows"]}
    assert flags["out/run1/02.png"] == ["could not read"]
    assert d["rows"][-1]["file"] == "out/run1/02.png"
    assert rank.main(["rank", "out/nope", "--json"], embed=fake_embed, root=root) == 2
    assert not json.loads(capsys.readouterr().out)["ok"]


def test_c1m4_rank_drops_multi_face_holdout(tmp_path, capsys):
    root = make_project(tmp_path, n_hold=3)

    def embed(bgr):
        faces = fake_embed(bgr)
        # the first holdout photo (red 10) also has a bigger stranger
        if abs(bgr[:, :, 2].mean() - 110) < 1:
            faces.append(Face((0, 0, 400, 400), np.array([-1.0, 0, 5.0])))
        return faces

    assert rank.main(["rank", "out/run1", "--json"], embed=embed, root=root) == 0
    d = json.loads(capsys.readouterr().out)
    assert any("holdout/p0.png" in w and "left out" in w for w in d["warnings"])
    assert d["baseline"]["pairs"] == 1  # 2 usable holdout photos remain

    root2 = make_project(tmp_path / "b", n_hold=2)
    assert rank.main(["rank", "out/run1", "--json"], embed=embed, root=root2) == 2  # only 1 left


def test_c2l3_rank_warns_when_refs_changed(tmp_path, capsys):
    from generate import fingerprint  # noqa: F401  (generate must import cleanly here)

    root = make_project(tmp_path)
    hashes = rank.current_ref_hashes(root / "photos" / "refs")
    (root / "out" / "run1" / "run.json").write_text(json.dumps({"refs": hashes}))
    assert rank.main(["rank", "out/run1", "--json"], embed=fake_embed, root=root) == 0
    assert json.loads(capsys.readouterr().out)["warnings"] == []
    Image.new("RGB", (400, 400), (99, 0, 0)).save(root / "photos" / "refs" / "p0.png")
    assert rank.main(["rank", "out/run1", "--json"], embed=fake_embed, root=root) == 0
    assert any("differs" in w for w in json.loads(capsys.readouterr().out)["warnings"])


def make_inbox(root, specs):
    """specs: name -> (embedding, yaw, sharpness, width) or 'none'/'two'."""
    inbox = root / "photos" / "inbox"
    inbox.mkdir(parents=True)
    table = {}
    for i, (name, spec) in enumerate(specs.items()):
        Image.new("RGB", (64, 64), (i * 20 + 10, 0, 0)).save(inbox / name, format="PNG")
        table[i * 20 + 10] = spec

    def detector(bgr):
        spec = table[round(bgr[:, :, 2].mean())]
        if spec == "none":
            return []
        if spec == "two":
            return [Face((0, 0, 300, 300), vec(1, 0, 0)), Face((0, 0, 290, 290), vec(0, 1, 0))]
        emb, yaw, sharp, width = spec
        return [Face((0, 0, width, width), np.asarray(emb, float), yaw, sharp)]

    return detector


GOOD = {"yaw": 0.02, "sharp": 200.0, "width": 400}
DIM = 16


def me(i, jitter=0.0):
    """Photo i of the same person: a shared identity direction plus a per-photo
    part, so different photos score about 0.6 (same person, not duplicates)."""
    v = np.ones(DIM) / np.sqrt(DIM) + 0.8 * np.eye(DIM)[i]
    v[(i + 1) % DIM] += jitter
    return v


def stranger(i):
    """A different person: orthogonal to the shared identity direction."""
    v = np.zeros(DIM)
    v[i] = 1.0
    v[(i + 1) % DIM] = -1.0
    return v


def spec(emb, yaw=0.02, sharp=200.0, width=400):
    return (emb, yaw, sharp, width)


def test_split_assigns_refs_holdout_and_rejects(tmp_path, capsys):
    root = tmp_path
    det = make_inbox(
        root,
        {
            "a.jpg": spec(me(0), yaw=0.20),
            "b.jpg": spec(me(1), yaw=0.01),
            "c.jpg": spec(me(2), yaw=0.10),
            "d.jpg": spec(me(3), yaw=0.05),
            "e.jpg": spec(me(4), yaw=0.60),  # turned away
            "f.jpg": spec(me(5), sharp=5.0),  # blurry
            "g.jpg": spec(me(6), width=100),  # small face
            "h.jpg": "none",
            "i.jpg": "two",
            "j.jpg": spec(me(1, jitter=0.01), yaw=0.0),  # duplicate of b, equally good
        },
    )
    (root / "photos" / "inbox" / "clip.mov").write_bytes(b"x")
    assert rank.main(["split", "--json"], embed=det, root=root) == 0
    d = json.loads(capsys.readouterr().out)
    # best frontal first: b (0.01), d (0.05), c (0.10), a (0.20)
    assert [r["as"] for r in d["refs"]] == ["01_b.jpg", "02_d.jpg", "03_c.jpg", "04_a.jpg"]
    assert sorted(h["file"] for h in d["holdout"]) == ["e.jpg", "f.jpg", "g.jpg"]
    reasons = {r["file"]: r["reason"] for r in d["rejected"]}
    assert "no face" in reasons["h.jpg"] and "2 large faces" in reasons["i.jpg"]
    assert "near-duplicate of b.jpg" in reasons["j.jpg"] and "unsupported" in reasons["clip.mov"]
    assert sorted(p.name for p in (root / "photos" / "refs").iterdir()) == [
        r["as"] for r in d["refs"]
    ]
    assert sorted(p.name for p in (root / "photos" / "holdout").iterdir()) == [
        "e.jpg",
        "f.jpg",
        "g.jpg",
    ]
    assert len(list((root / "photos" / "inbox").iterdir())) == 11  # copied, never moved
    # idempotent
    assert rank.main(["split", "--json"], embed=det, root=root) == 0
    assert json.loads(capsys.readouterr().out)["refs"] == d["refs"]


def test_split_fails_clearly(tmp_path, capsys):
    det = make_inbox(tmp_path, {f"{i}.jpg": spec(me(i)) for i in range(4)})
    assert rank.main(["split", "--json"], embed=det, root=tmp_path) == 2
    d = json.loads(capsys.readouterr().out)
    assert not d["ok"] and "need at least 5" in d["error"]
    assert not (tmp_path / "photos" / "refs").exists()  # nothing cleared or created on failure

    root = tmp_path / "b"
    det = make_inbox(
        root,
        {
            "a.jpg": spec(me(0)),
            "b.jpg": spec(me(1)),
            "c.jpg": spec(me(2), yaw=0.9),
            "d.jpg": spec(me(3), yaw=0.9),
            "e.jpg": spec(me(4), yaw=0.9),
        },
    )
    assert rank.main(["split", "--json"], embed=det, root=root) == 2
    assert "add 1 more" in json.loads(capsys.readouterr().out)["error"]

    assert rank.main(["split", "--json"], embed=det, root=tmp_path / "empty") == 2


# ----------------------------------------------------- regressions: split and rank


def good_inbox(root, n=6):
    return make_inbox(root, {f"p{i}.jpg": spec(me(i), yaw=0.01 * i) for i in range(n)})


def tree(root):
    return sorted(str(p.relative_to(root)) for p in (root / "photos").rglob("*"))


def test_v1h4_split_refuses_unknown_files_and_changes_nothing(tmp_path, capsys):
    det = good_inbox(tmp_path)
    for sub in ("refs", "holdout"):
        (tmp_path / "photos" / sub).mkdir(parents=True)
    (tmp_path / "photos" / "refs" / "MY_ONLY_COPY.jpg").write_bytes(b"precious")
    (tmp_path / "photos" / "holdout" / "notes.txt").write_text("notes")
    before = tree(tmp_path)
    assert rank.main(["split", "--json"], embed=det, root=tmp_path) == 2
    d = json.loads(capsys.readouterr().out)
    assert d["unknown_files"] == ["refs/MY_ONLY_COPY.jpg", "holdout/notes.txt"]
    assert tree(tmp_path) == before
    assert (tmp_path / "photos" / "refs" / "MY_ONLY_COPY.jpg").read_bytes() == b"precious"


def test_v1h4_split_replaces_only_its_own_files(tmp_path, capsys):
    det = good_inbox(tmp_path)
    assert rank.main(["split", "--json"], embed=det, root=tmp_path) == 0
    manifest = json.loads((tmp_path / "photos" / rank.SPLIT_MANIFEST).read_text())["files"]
    assert len(manifest) == 6
    (tmp_path / "photos" / "refs" / ".DS_Store").write_bytes(b"finder")  # ignored, kept
    assert rank.main(["split", "--json"], embed=det, root=tmp_path) == 0
    assert (tmp_path / "photos" / "refs" / ".DS_Store").exists()
    # a split-written file the human overwrote is no longer split's to delete
    (tmp_path / "photos" / "holdout" / "p5.jpg").write_bytes(b"edited by hand")
    assert rank.main(["split", "--json"], embed=det, root=tmp_path) == 2
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["unknown_files"] == [
        "holdout/p5.jpg"
    ]


def test_v1h4_split_refuses_symlinked_folder(tmp_path, capsys):
    det = good_inbox(tmp_path)
    (tmp_path / "photos" / "refs").symlink_to(tmp_path / "photos" / "inbox")
    assert rank.main(["split", "--json"], embed=det, root=tmp_path) == 2
    assert len(list((tmp_path / "photos" / "inbox").iterdir())) == 6


def test_v2h1_split_rejects_a_different_person(tmp_path, capsys):
    specs = {f"p{i}.jpg": spec(me(i), yaw=0.01 * i) for i in range(5)}
    specs["partner.jpg"] = spec(stranger(8))
    det = make_inbox(tmp_path, specs)
    assert rank.main(["split", "--json"], embed=det, root=tmp_path) == 0
    d = json.loads(capsys.readouterr().out)
    reasons = {r["file"]: r["reason"] for r in d["rejected"]}
    assert "different person" in reasons["partner.jpg"]
    placed = [r["file"] for r in d["refs"]] + [h["file"] for h in d["holdout"]]
    assert "partner.jpg" not in placed and len(placed) == 5
    assert d["identity_baseline"]["mean"] > 0 and d["same_person_threshold"] == 0.30


def test_v2h1_split_fails_on_six_different_people(tmp_path, capsys):
    det = make_inbox(tmp_path, {f"p{i}.jpg": spec(stranger(2 * i)) for i in range(6)})
    assert rank.main(["split", "--json"], embed=det, root=tmp_path) == 2
    d = json.loads(capsys.readouterr().out)
    assert "different person" in d["error"] and d["identity_baseline"]["mean"] < 0.30
    assert not (tmp_path / "photos" / "refs").exists()


def test_v1m1_yaw_ignores_roll():
    def kps(yaw_px, roll_deg):
        # eyes 60 px apart, nose offset sideways by yaw_px, then the whole face rolled
        pts = np.array([[-30, 0], [30, 0], [yaw_px, 35], [-20, 60], [20, 60]], float)
        t = np.radians(roll_deg)
        rot = np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
        return pts @ rot.T + 500

    for roll in (0, 10, 20, -20):
        assert abs(rank.yaw_from_kps(kps(0, roll))) < 1e-9  # frontal stays frontal
        assert rank.yaw_from_kps(kps(-26, roll)) == pytest.approx(-26 / 60)  # turned stays turned


def test_v1m3_near_duplicate_keeps_the_sharper_photo(tmp_path, capsys):
    specs = {
        "a.jpg": spec(me(0, jitter=0.01), sharp=5.0),  # soft copy of b, sorts first
        "b.jpg": spec(me(0), yaw=0.0, sharp=200.0),
    }
    specs.update({f"p{i}.jpg": spec(me(i), yaw=0.01 * i) for i in range(1, 5)})
    det = make_inbox(tmp_path, specs)
    assert rank.main(["split", "--json"], embed=det, root=tmp_path) == 0
    d = json.loads(capsys.readouterr().out)
    assert {r["file"]: r["reason"] for r in d["rejected"]}["a.jpg"].startswith(
        "near-duplicate of b.jpg"
    )
    assert d["refs"][0]["file"] == "b.jpg"


def test_v1l4_sharpness_is_noise_robust():
    rng = np.random.default_rng(0)
    flat = np.full((256, 256, 3), 128.0)
    noisy = np.clip(flat + rng.normal(0, 8, (256, 256, 1)), 0, 255).astype(np.uint8)
    assert rank.face_sharpness(noisy, (0, 0, 256, 256)) < rank.MIN_SHARPNESS


def test_v1m5_rank_drops_holdout_photo_uploaded_in_that_run(tmp_path, capsys):
    root = make_project(tmp_path, n_hold=3)
    uploaded = rank.upload_hash(root / "photos" / "holdout" / "p0.png")
    refs = rank.current_ref_hashes(root / "photos" / "refs")
    (root / "out" / "run1" / "run.json").write_text(
        json.dumps(
            {"refs": {**refs, "ref4": uploaded}, "status": "partial", "bad_outputs": ["04.bad"]}
        )
    )
    assert rank.main(["rank", "out/run1", "--json"], embed=fake_embed, root=root) == 0
    d = json.loads(capsys.readouterr().out)
    assert any("holdout/p0.png" in w and "uploaded as a reference" in w for w in d["warnings"])
    assert d["baseline"]["pairs"] == 1
    assert d["partial"] is True and d["bad_outputs"] == ["04.bad"]


def test_v1h3_rank_stdout_is_only_json(tmp_path, capsys):
    root = make_project(tmp_path)

    def chatty(bgr):
        print("download_path: /somewhere")  # what insightface prints on first run
        return fake_embed(bgr)

    assert rank.main(["check", "--json"], embed=chatty, root=root) == 0
    cap = capsys.readouterr()
    assert json.loads(cap.out)["ok"] and "download_path" in cap.err

    def broken(bgr):
        raise RuntimeError("Failed downloading url")

    assert rank.main(["split", "--json"], embed=broken, root=good_inbox_root(tmp_path)) == 4
    d = json.loads(capsys.readouterr().out)
    assert d["exit_code"] == 4 and "Failed downloading" in d["error"]

    assert rank.main(["rank", "--json"], embed=fake_embed, root=root) == 2
    assert "usage" in json.loads(capsys.readouterr().out)["error"]


def good_inbox_root(tmp_path):
    root = tmp_path / "inboxroot"
    good_inbox(root)
    return root
