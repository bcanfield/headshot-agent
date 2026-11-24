import ast
import base64
import json
import re
from types import SimpleNamespace

import pytest
from conftest import OK, SCRIPTS, TEMPLATE, FakeClient, mock_client, png_bytes, run, runs

import generate

LOOK = {"outfit": "a blazer", "background": "grey", "marks": "", "glasses": "none"}


# ---------------------------------------------------------------- prompt


def test_prompt_roles_for_3_and_4_refs():
    assert "Images 1, 2 and 3 are" in generate.image_roles(3)
    assert "images 2-3" in generate.image_roles(3)
    assert "Images 1, 2, 3 and 4 are" in generate.image_roles(4)
    assert "images 2-4" in generate.image_roles(4)
    assert "4" not in generate.image_roles(3)


def test_fill_prompt_clean_and_marks_clause():
    p = generate.fill_prompt(TEMPLATE, LOOK, 3)
    assert not re.search(r"[{}<>]", p)
    assert "distinctive marks from images 1-3" in p
    p2 = generate.fill_prompt(TEMPLATE, {**LOOK, "marks": "a mole", "glasses": "keep"}, 4)
    assert "distinctive marks (a mole)" in p2 and "Keep any glasses" in p2


@pytest.mark.parametrize("bad", ["<outfit>", "{oops}"])
def test_placeholder_refused(bad):
    with pytest.raises(generate.GenerateError):
        generate.fill_prompt(TEMPLATE, {**LOOK, "outfit": bad}, 3)
    with pytest.raises(generate.GenerateError):
        generate.fill_prompt(TEMPLATE + " {leftover}", LOOK, 3)


def test_placeholder_refused_in_dry_run(project):
    assert run(project, "--dry-run", "--outfit", "<plain blazer>") == 2


def test_empty_outfit_refused():
    with pytest.raises(generate.GenerateError):
        generate.fill_prompt(TEMPLATE, {**LOOK, "outfit": " "}, 3)


# ---------------------------------------------------------------- refs


def test_ref_count_enforced(project):
    (project / "photos" / "refs" / "IMG_3.jpg").unlink()
    assert run(project, "--dry-run") == 2


def test_refs_under_out_rejected(project):
    out = project / "out" / "x"
    out.mkdir(parents=True)
    (out / "01.png").write_bytes(png_bytes())
    refs = project / "photos" / "refs"
    (refs / "IMG_3.jpg").unlink()
    (refs / "IMG_3.png").symlink_to(out / "01.png")
    with pytest.raises(generate.GenerateError, match="out/"):
        generate.select_refs(refs, project)


# ----------------------------------------------------------- cost guard


def test_n_cap(project):
    for bad in ("0", "9", "40"):
        assert run(project, "-n", bad, *OK, client=FakeClient()) == 2


def test_max_cost_required_and_gates(project, capsys):
    c = FakeClient()
    assert run(project, client=c) == 3
    _lo, hi = generate.estimate_cost(4, 3, "high")
    assert run(project, "--max-cost", str(hi - 0.01), client=c) == 3
    assert c.calls == []
    assert run(project, "--max-cost", f"{hi:.4f}1", client=c) == 0
    assert len(c.calls) == 1


def test_json_exit_codes_and_shapes(project, capsys):
    import json as _json

    c = FakeClient()
    assert run(project, "--json", client=c) == 3
    out = capsys.readouterr()
    payload = _json.loads(out.out)  # exactly one JSON object on stdout
    assert (
        payload["ok"] is False and payload["exit_code"] == 3 and len(payload["estimate_usd"]) == 2
    )
    assert "estimated cost" in out.err
    assert run(project, "--json", "--background", "<x>", client=c) == 2
    assert _json.loads(capsys.readouterr().out)["errors"]["background"]
    assert run(project, "--json", *OK, client=c) == 0
    ok = _json.loads(capsys.readouterr().out)
    assert ok["ok"] and ok["status"] == "ok" and ok["outputs"][0] == "01.png"
    import openai

    assert (
        run(project, "--json", *OK, "--again", client=FakeClient(fail=openai.OpenAIError("x"))) == 4
    )
    err = _json.loads(capsys.readouterr().out)
    assert err["ok"] is False and err["exit_code"] == 4


def test_dry_run_json_is_the_look_validator(project, capsys):
    import json as _json

    assert run(project, "--dry-run", "--json") == 0
    d = _json.loads(capsys.readouterr().out)
    assert d["errors"] == {} and "charcoal blazer" in d["prompt"] and d["estimate_usd"][0] > 0
    assert (
        run(
            project,
            "--dry-run",
            "--json",
            "--outfit",
            "",
            "--glasses",
            "keep",
            "--lighting",
            "{sun}",
        )
        == 2
    )
    e = _json.loads(capsys.readouterr().out)["errors"]
    assert set(e) == {"outfit", "lighting"}


def test_new_look_fields_in_prompt():
    p = generate.fill_prompt(
        TEMPLATE, {**LOOK, "expression": "a broad smile", "lighting": "overcast daylight"}, 3
    )
    assert "looking at the camera with a broad smile" in p and "Lighting: overcast daylight." in p
    default = generate.fill_prompt(TEMPLATE, LOOK, 3)  # defaults when the keys are absent
    # the default is rung 3 of the skill's expression ladder
    assert "with a natural closed-mouth smile." in default and "front-left" in default


def test_glasses_default_is_keep():
    assert generate.LOOK_DEFAULTS["glasses"] == "keep"
    assert (
        "glasses"
        in generate.fill_prompt(
            TEMPLATE, {k: v for k, v in LOOK.items() if k != "glasses"}, 3
        ).lower()
    )
    assert "Keep any glasses" in generate.fill_prompt(
        TEMPLATE, {k: v for k, v in LOOK.items() if k != "glasses"}, 3
    )


def test_xhigh_and_max_quality_rejected(project):
    for q in ("xhigh", "max"):
        with pytest.raises(SystemExit):
            run(project, "--quality", q, *OK, client=FakeClient())


def test_duplicate_run_refused_unless_again(project):
    c = FakeClient()
    assert run(project, *OK, client=c) == 0
    assert run(project, *OK, client=c) == 2
    assert len(c.calls) == 1
    assert run(project, *OK, "--again", client=c) == 0
    assert len(c.calls) == 2
    # a changed look is a different run
    assert run(project, *OK, "--background", "blue", client=c) == 0


def test_estimate_varies_by_quality():
    lows = {q: generate.estimate_cost(4, 3, q) for q in generate.QUALITIES}
    assert lows["low"][1] < lows["medium"][1] < lows["high"][1]
    assert lows["low"][0] < lows["high"][0]


def test_cost_from_usage_splits_text_and_image_output():
    usage = SimpleNamespace(
        output_tokens=5000,
        input_tokens=2000,
        input_tokens_details=SimpleNamespace(image_tokens=1500, text_tokens=500),
        output_tokens_details=SimpleNamespace(image_tokens=4000, text_tokens=1000),
    )
    P = generate.PRICE_PER_M[generate.DEFAULT_MODEL]
    assert generate.cost_from_usage(usage) == pytest.approx(
        (1500 * P["image_in"] + 500 * P["text_in"] + 4000 * P["image_out"] + 1000 * P["text_out"])
        / 1e6
    )
    plain = SimpleNamespace(
        output_tokens=5000,
        input_tokens=2000,
        input_tokens_details=SimpleNamespace(image_tokens=1500, text_tokens=500),
    )
    assert generate.cost_from_usage(plain) == pytest.approx((1500 * 8 + 500 * 5 + 5000 * 30) / 1e6)


def test_dry_run_no_client_no_writes(project, capsys):
    assert run(project, "--dry-run") == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "ESTIMATE" in out and "ref3" in out
    assert not (project / "out").exists()


# ----------------------------------------------------- run + run.json


def test_successful_run_writes_outputs_and_run_json(project):
    c = FakeClient()
    assert run(project, *OK, client=c) == 0
    [call] = c.calls
    assert call["model"] == "gpt-image-2.6-sunburst"
    assert call["n"] == 4 and call["size"] == "1024x1024" and call["quality"] == "high"
    assert "input_fidelity" not in call and "response_format" not in call
    assert [f[0] for f in call["image"]] == ["ref1.jpg", "ref2.jpg", "ref3.jpg"]
    assert all(f[2] == "image/jpeg" for f in call["image"])

    [run_dir] = runs(project)
    assert sorted(p.name for p in run_dir.iterdir()) == [
        "01.png",
        "02.png",
        "03.png",
        "04.png",
        "run.json",
    ]
    text = (run_dir / "run.json").read_text()
    meta = json.loads(text)
    assert meta["status"] == "ok" and meta["request_id"] == "req_abc"
    assert meta["cost_usd"] == pytest.approx((1500 * 8 + 500 * 5 + 5000 * 30) / 1e6)
    assert set(meta["refs"]) == {"ref1", "ref2", "ref3"}
    assert str(project) not in text and "IMG_" not in text and "b64" not in text
    assert "sk-" not in text


def test_from_reuses_look_and_overrides(project):
    c = FakeClient()
    assert run(project, *OK, client=c) == 0
    [first] = runs(project)
    assert (
        run(project, *OK, "--from", f"out/{first.name}", "--background", "light blue", client=c)
        == 0
    )
    assert "light blue background" in c.calls[1]["prompt"]
    assert "a plain charcoal blazer" in c.calls[1]["prompt"]


def test_from_refuses_changed_refs(project):
    c = FakeClient()
    assert run(project, *OK, client=c) == 0
    [first] = runs(project)
    from PIL import Image

    Image.new("RGB", (64, 48), (1, 2, 3)).save(project / "photos" / "refs" / "IMG_1.jpg")
    assert run(project, *OK, "--from", f"out/{first.name}", client=c) == 2


def status_error(code=500):
    import openai

    httpx2 = pytest.importorskip("httpx2")
    req = httpx2.Request("POST", "http://x")
    return openai.InternalServerError(
        "boom", response=httpx2.Response(code, request=req), body=None
    )


def test_error_run_recorded_and_not_duplicate(project):
    c = FakeClient(fail=status_error())
    assert run(project, *OK, client=c) == 4
    [run_dir] = runs(project)
    meta = json.loads((run_dir / "run.json").read_text())
    assert meta["status"] == "error" and meta["possibly_billed"] is False
    assert run(project, *OK, client=FakeClient()) == 0  # an HTTP refusal does not block


# ------------------------------------- real client against a mock transport


def test_client_has_no_retries(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-dummy")
    c = generate.make_client()
    assert c.max_retries == 0 and c.timeout == generate.TIMEOUT_FLOOR_S
    assert generate.make_client(timeout=500).timeout == 500
    assert generate.request_timeout(1, "low") == 300


def test_real_client_multipart_shape(project, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-dummy")
    seen = {}

    def handler(req):
        body = req.read()
        seen["parts"] = re.findall(
            rb'name="([^"]+)"(?:; filename="([^"]*)")?\r\n(?:Content-Type: ([^\r]*))?', body
        )
        seen["body"] = body
        return httpx2.Response(
            200,
            headers={"x-request-id": "req_mock"},
            json={
                "created": 1,
                "data": [{"b64_json": base64.b64encode(png_bytes()).decode()}],
                "usage": {
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "total_tokens": 2,
                    "input_tokens_details": {"image_tokens": 1, "text_tokens": 0},
                },
            },
        )

    client, httpx2 = mock_client(handler)
    assert run(project, *OK, "-n", "1", client=client) == 0
    names = [(p[0].decode(), p[1].decode(), p[2].decode()) for p in seen["parts"]]
    imgs = [n for n in names if n[0].startswith("image")]
    assert imgs == [("image[]", f"ref{i}.jpg", "image/jpeg") for i in (1, 2, 3)]
    assert not any(n[0] in ("input_fidelity", "response_format") for n in names)
    assert b"IMG_" not in seen["body"]
    [run_dir] = runs(project)
    assert json.loads((run_dir / "run.json").read_text())["request_id"] == "req_mock"


@pytest.mark.parametrize(
    "status,code,needle",
    [
        (400, "moderation_blocked", "moderation"),
        (401, "invalid_api_key", "authentication"),
        (429, "rate_limit_exceeded", "rate limit"),
        (403, None, "Verification"),
    ],
)
def test_error_mapping(project, monkeypatch, capsys, status, code, needle):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-dummy")

    def handler(req):
        return httpx2.Response(
            status,
            headers={"x-request-id": "req_err"},
            json={"error": {"message": "nope", "code": code, "type": "x"}},
        )

    client, httpx2 = mock_client(handler)
    assert run(project, *OK, client=client) == 4
    err = capsys.readouterr().err
    assert needle.lower() in err.lower() and "req_err" in err


def test_no_insightface_import_in_generate_or_imaging():
    for name in ("generate.py", "imaging.py"):
        tree = ast.parse((SCRIPTS / name).read_text())
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module or ""]
            assert not any("insightface" in m for m in mods), name


# ------------------------------------------------ regressions: core behaviour


def run_dirs(project):
    return sorted(runs(project))


def test_c1m1_interrupted_pending_and_timeout_block_identical_rerun(project):
    import openai

    httpx2 = pytest.importorskip("httpx2")

    class Boom(FakeClient):
        def edit(self, **kw):
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run(project, *OK, client=Boom())
    [d] = run_dirs(project)
    assert json.loads((d / "run.json").read_text())["status"] == "interrupted"
    c = FakeClient()
    assert run(project, *OK, client=c) == 2 and c.calls == []
    assert run(project, *OK, "--again", client=c) == 0

    # a timeout is recorded as error but may have been billed
    import shutil

    shutil.rmtree(project / "out")
    req = httpx2.Request("POST", "http://x")
    assert run(project, *OK, client=FakeClient(fail=openai.APITimeoutError(request=req))) == 4
    c2 = FakeClient()
    assert run(project, *OK, client=c2) == 2 and c2.calls == []


def test_c1m2_partial_response_keeps_usage_and_good_images(project):
    class Partial(FakeClient):
        def edit(self, **kw):
            resp = super().edit(**kw)
            good = base64.b64encode(png_bytes()).decode()
            resp.data = [
                SimpleNamespace(b64_json=good),
                SimpleNamespace(b64_json="!!not b64!!"),
                SimpleNamespace(b64_json=good),
                SimpleNamespace(b64_json=None),
            ]
            return resp

    assert run(project, *OK, client=Partial()) == 0
    [d] = run_dirs(project)
    meta = json.loads((d / "run.json").read_text())
    assert meta["status"] == "partial" and meta["outputs"] == ["01.png", "03.png"]
    assert meta["request_id"] == "req_abc" and meta["cost_usd"] > 0
    assert (d / "03.png").exists()


def test_c1m2_data_null_and_usage_saved_before_images(project):
    class NullData(FakeClient):
        def edit(self, **kw):
            resp = super().edit(**kw)
            resp.data = None
            return resp

    assert run(project, *OK, client=NullData()) == 4
    [d] = run_dirs(project)
    meta = json.loads((d / "run.json").read_text())
    assert meta["status"] == "error" and meta["request_id"] == "req_abc"


def test_c1m2_undecodable_image_not_listed_as_output(project):
    class Garbage(FakeClient):
        def edit(self, **kw):
            resp = super().edit(**kw)
            resp.data[0] = SimpleNamespace(b64_json=base64.b64encode(b"nope").decode())
            return resp

    assert run(project, *OK, client=Garbage()) == 0
    [d] = run_dirs(project)
    meta = json.loads((d / "run.json").read_text())
    assert "01.png" not in meta["outputs"] and meta["bad_outputs"] == ["01.bad"]
    assert (d / "01.bad").exists() and not (d / "01.png").exists()


def test_c2m2_from_refuses_when_a_ref_was_removed(project):
    from PIL import Image

    Image.new("RGB", (64, 48), (9, 9, 9)).save(project / "photos" / "refs" / "IMG_4.jpg")
    c = FakeClient()
    assert run(project, *OK, client=c) == 0
    [first] = run_dirs(project)
    (project / "photos" / "refs" / "IMG_4.jpg").unlink()
    assert run(project, *OK, "--from", f"out/{first.name}", "--background", "blue", client=c) == 2
    assert len(c.calls) == 1


def test_c2l2_refs_sent_in_filename_order(project):
    import hashlib

    import imaging

    c = FakeClient()
    assert run(project, *OK, client=c) == 0
    [call] = c.calls
    refs = project / "photos" / "refs"
    expected = [imaging.sanitize_for_upload(refs / f"IMG_{i}.jpg") for i in (1, 2, 3)]
    assert [f[1] for f in call["image"]] == expected
    [d] = run_dirs(project)
    meta = json.loads((d / "run.json").read_text())
    assert [meta["refs"][f"ref{i}"] for i in (1, 2, 3)] == [
        hashlib.sha256(b).hexdigest() for b in expected
    ]
    assert "Image 1 is the clearest" in call["prompt"]


def test_c1l6_malformed_run_json_does_not_crash(project):
    bad = project / "out" / "bad"
    bad.mkdir(parents=True)
    (bad / "run.json").write_text("[1]")
    (project / "out" / "bad2").mkdir()
    (project / "out" / "bad2" / "run.json").write_text("{")
    assert run(project, "--dry-run") == 0
    assert run(project, "--dry-run", "--from", "out/bad2") == 2
    assert run(project, "--dry-run", "--from", "out/bad") == 2
    (bad / "run.json").write_text(
        json.dumps({"look": {"outfit": "x", "background": "y"}, "params": {"n": "4x"}})
    )
    assert run(project, "--dry-run", "--from", "out/bad") == 2


# ------------------------------------------------ regressions: input handling


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf", "0", "-1", "10.01", "abc"])
def test_v1h1_max_cost_must_be_finite_positive_and_capped(project, capsys, bad):
    c = FakeClient()
    assert run(project, "--json", "--max-cost", bad, client=c) == 2
    d = json.loads(capsys.readouterr().out)
    assert d == {"ok": False, "exit_code": 2, "error": d["error"]} and "max-cost" in d["error"]
    assert c.calls == [] and not (project / "out").exists()


def test_v1h1_gate_compares_with_not_le(project):
    src = (SCRIPTS / "generate.py").read_text()
    assert "not (hi <= args.max_cost)" in src
    c = FakeClient()
    assert run(project, "--max-cost", "10", client=c) == 0 and len(c.calls) == 1


def test_v1h2_request_timeout_stays_under_bash_limit():
    for q in generate.QUALITIES:
        for n in range(1, generate.MAX_N + 1):
            assert generate.request_timeout(n, q) <= 540
    assert generate.request_timeout(8, "high") == 540


def test_v1h3_argparse_error_is_json(project, capsys):
    assert run(project, "--json", "-n", "x") == 2
    d = json.loads(capsys.readouterr().out)
    assert d["exit_code"] == 2 and "usage" in d["error"]


def test_v1l1_unexpected_client_exception_is_json_and_blocks_rerun(project, capsys):
    assert run(project, "--json", *OK, client=FakeClient(fail=RuntimeError("boom"))) == 4
    d = json.loads(capsys.readouterr().out)
    assert d["exit_code"] == 4 and "RuntimeError" in d["error"] and d["possibly_billed"]
    c = FakeClient()
    assert run(project, *OK, client=c) == 2 and c.calls == []


def test_v1h3_stray_stdout_goes_to_stderr_under_json(project, capsys):
    class Noisy(FakeClient):
        def edit(self, **kw):
            print("library chatter on stdout")
            return super().edit(**kw)

    assert run(project, "--json", *OK, client=Noisy()) == 0
    cap = capsys.readouterr()
    assert json.loads(cap.out)["ok"] and "library chatter" in cap.err


def test_v1m2_high_quality_bound_and_over_ceiling(project, capsys):
    assert generate.EST_IMAGE_OUT_TOKENS_PER_IMAGE["high"][1] >= 8000

    class Pricey(FakeClient):
        def edit(self, **kw):
            resp = super().edit(**kw)
            resp.usage.output_tokens = 400_000  # $12 of output, above the $10 ceiling
            return resp

    assert run(project, "--json", *OK, client=Pricey()) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["over_ceiling"] is True and d["cost_usd"] > d["max_cost"] == 10.0
    [run_dir] = run_dirs(project)
    assert json.loads((run_dir / "run.json").read_text())["over_ceiling"] is True
    assert run(project, "--json", *OK, "--again", client=FakeClient()) == 0
    assert json.loads(capsys.readouterr().out)["over_ceiling"] is False


def test_v1m4_no_valid_image_has_error_and_blocks_rerun(project, capsys):
    class AllBad(FakeClient):
        def edit(self, **kw):
            resp = super().edit(**kw)
            resp.data = [SimpleNamespace(b64_json="!!not b64!!")]
            return resp

    assert run(project, "--json", *OK, client=AllBad()) == 4
    d = json.loads(capsys.readouterr().out)
    assert d["exit_code"] == 4 and "no valid image" in d["error"]
    [run_dir] = run_dirs(project)
    meta = json.loads((run_dir / "run.json").read_text())
    assert meta["error"] == "NoValidImage" and meta["possibly_billed"] is True
    c = FakeClient()
    assert run(project, *OK, client=c) == 2 and c.calls == []
    assert run(project, *OK, "--again", client=c) == 0


def test_v1l3_cost_counts_unbroken_tokens_at_image_rate():
    P = generate.PRICE_PER_M[generate.DEFAULT_MODEL]
    usage = SimpleNamespace(
        input_tokens=3000,
        output_tokens=8000,
        input_tokens_details=SimpleNamespace(image_tokens=0, text_tokens=0),
        output_tokens_details=SimpleNamespace(image_tokens=7000, text_tokens=0),
    )
    assert generate.cost_from_usage(usage) == pytest.approx(
        (3000 * P["image_in"] + 8000 * P["image_out"]) / 1e6
    )


def test_v1l5_unknown_model_pricing_refused(project, capsys):
    c = FakeClient()
    assert run(project, "--json", "--dry-run", "--model", "gpt-image-9") == 2
    assert "no pricing" in json.loads(capsys.readouterr().out)["error"]
    assert run(project, *OK, "--model", "gpt-image-9", client=c) == 2 and c.calls == []
    assert run(project, "--dry-run", "--model", "gpt-image-2.6-flare") == 0


def test_v2m4_check_key_reports_presence_only(monkeypatch, capsys, tmp_path):
    assert generate.main(["--check-key", "--json"], root=tmp_path) == 2
    d = json.loads(capsys.readouterr().out)
    assert d["key_present"] is False and d["exit_code"] == 2
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value-123")
    assert generate.main(["--check-key", "--json"], root=tmp_path) == 0
    cap = capsys.readouterr()
    assert json.loads(cap.out) == {"ok": True, "exit_code": 0, "key_present": True}
    assert "sk-secret" not in cap.out + cap.err


def test_v2l2_dry_run_says_whether_duplicate_finished(project, capsys):
    assert run(project, *OK, client=FakeClient()) == 0
    capsys.readouterr()
    assert run(project, "--dry-run", "--json") == 0
    d = json.loads(capsys.readouterr().out)
    assert d["duplicate_of"] and d["duplicate_finished"] is True


def test_v2l4_fixture_look_is_not_the_project_file(project):
    from conftest import FIXTURE_LOOK

    assert (project / "look.toml").read_text() == FIXTURE_LOOK
