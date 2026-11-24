"""The skill folder as an installable unit: metadata, layout and the workspace seam."""

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from conftest import PROJECT, SCRIPTS, SKILL_DIR, TEMPLATE, ColourEmbed, ident, jrun, run

import generate
import rank
import workspace

RANK_ONLY = {"insightface", "onnxruntime", "scikit-image"}


def script_metadata(path: Path) -> dict:
    """The PEP 723 `# /// script` block, parsed with tomllib."""
    m = re.search(r"(?m)^# /// script$\s(?P<body>(^#(| .*)$\s)+)^# ///$", path.read_text())
    assert m, f"{path.name} has no PEP 723 block"
    body = "".join(line[2:] + "\n" for line in m.group("body").splitlines())
    return tomllib.loads(body)


def dep_name(spec: str) -> str:
    return re.split(r"[<>=!~ \[;]", spec, maxsplit=1)[0].lower()


def frontmatter() -> tuple[dict, dict]:
    """Top-level keys and the metadata map of SKILL.md (flat YAML, one nested map)."""
    text = (SKILL_DIR / "SKILL.md").read_text()
    m = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "SKILL.md has no frontmatter"
    top, meta, section = {}, {}, None
    for line in m.group(1).splitlines():
        key, _, value = line.strip().partition(":")
        value = value.strip().strip('"')
        if line.startswith("  ") and section == "metadata":
            meta[key] = value
        else:
            section = key
            top[key] = value
    return top, meta


def marketplace() -> dict:
    return json.loads((PROJECT / ".claude-plugin" / "marketplace.json").read_text())


# ------------------------------------------------------------ metadata


def test_pep723_blocks_match_pyproject():
    project = tomllib.loads((PROJECT / "pyproject.toml").read_text())["project"]
    gen, rnk = script_metadata(SCRIPTS / "generate.py"), script_metadata(SCRIPTS / "rank.py")
    assert set(rnk["dependencies"]) == set(project["dependencies"])
    assert set(gen["dependencies"]) < set(rnk["dependencies"])
    assert {dep_name(d) for d in set(rnk["dependencies"]) - set(gen["dependencies"])} == RANK_ONLY
    assert gen["requires-python"] == rnk["requires-python"] == project["requires-python"]
    for name in ("generate.py", "rank.py"):
        assert (SCRIPTS / f"{name}.lock").is_file(), f"run `uv lock --script` on {name}"


def test_skill_version_matches_marketplace():
    _, meta = frontmatter()
    [entry] = marketplace()["plugins"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", meta["version"])
    assert meta["version"] == entry["version"]


def test_frontmatter_fits_every_registry():
    top, _ = frontmatter()
    assert top["name"] == SKILL_DIR.name
    assert len(top["name"]) <= 64 and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", top["name"])
    assert 0 < len(top["description"]) <= 1024
    assert not re.search(r"anthropic|claude", top["name"])
    assert "<" not in top["description"] and 0 < len(top["compatibility"]) <= 500


def test_marketplace_points_at_the_skill_folder():
    data = marketplace()
    [entry] = data["plugins"]
    assert entry["name"] == SKILL_DIR.name
    assert entry["source"] == "./skills/linkedin-headshot"
    assert (PROJECT / entry["source"]).resolve() == SKILL_DIR
    # A plugin.json inside the skill would make an `npx skills` install load as a plugin.
    assert not (SKILL_DIR / ".claude-plugin").exists()


def test_dev_symlink_loads_the_same_skill():
    link = PROJECT / ".claude" / "skills" / "linkedin-headshot"
    assert link.is_symlink() and link.resolve() == SKILL_DIR
    assert not Path(link.readlink()).is_absolute()


# ------------------------------------------------------------ layout


def test_skill_folder_ships_no_state_or_personal_data():
    banned = {".venv", "uv.lock", "photos", "out", "look.toml", "pyproject.toml"}
    for p in SKILL_DIR.rglob("*"):
        if "__pycache__" in p.parts:  # pytest imports the scripts here; installers drop it
            continue
        assert p.name not in banned, p


def test_skill_files_reference_only_what_ships():
    """An installed skill has only its own folder: no root CLAUDE.md, README or PRIVACY.md."""
    for md in SKILL_DIR.rglob("*.md"):
        text = md.read_text()
        for name in ("CLAUDE.md", "README", "PRIVACY.md", "--extra rank"):
            assert name not in text, f"{md.name} mentions {name}"
        for ref in re.findall(r"`((?:references|scripts|assets)/[\w./-]+)`", text):
            assert (SKILL_DIR / ref).exists(), f"{md.name} names missing {ref}"


def test_scripts_switch_off_bytecode_before_sibling_imports():
    for name in ("generate.py", "rank.py"):
        src = (SCRIPTS / name).read_text()
        switch = src.index("sys.dont_write_bytecode = True")
        for mod in ("cli", "imaging", "workspace"):
            assert switch < src.index(f"\nimport {mod}"), (name, mod)


# ------------------------------------------------------------ workspace


def test_prompt_comes_from_the_skill_not_the_workspace(project, capsys):
    (project / "prompt.txt").write_text("{image_roles} a planted prompt\n")
    code, out = jrun(project, capsys, "--dry-run")
    assert code == 0 and "planted" not in out["prompt"]
    assert out["prompt"] == generate.fill_prompt(TEMPLATE, out["look"], 3)
    assert workspace.PROMPT_PATH == SKILL_DIR / "assets" / "prompt.txt"


def test_json_results_echo_the_workspace(project, capsys):
    code, out = jrun(project, capsys, "--dry-run")
    assert code == 0 and out["workspace"] == str(project)
    code, out = jrun(project, capsys, "--from", "out/nope")
    assert code == 2 and out["workspace"] == str(project)


@pytest.mark.parametrize("where", ["skill", "inside", "home", "root"])
def test_bad_workspaces_are_refused(where, capsys):
    path = {
        "skill": SKILL_DIR,
        "inside": SCRIPTS,
        "home": Path.home(),
        "root": Path("/"),
    }[where]
    assert generate.main(["--json", "--dry-run", "--workspace", str(path)]) == 2
    assert "workspace" in json.loads(capsys.readouterr().out)["error"]
    assert rank.main(["--workspace", str(path), "check", "--json"], embed=lambda b: []) == 2
    assert "workspace" in json.loads(capsys.readouterr().out)["error"]


def test_missing_workspace_is_refused(tmp_path, capsys):
    assert generate.main(["--json", "--dry-run", "--workspace", str(tmp_path / "nope")]) == 2
    assert "create it first" in json.loads(capsys.readouterr().out)["error"]


def test_workspace_precedence_flag_then_env_then_cwd(tmp_path, monkeypatch):
    flag, env, cwd = (tmp_path / n for n in ("flag", "env", "cwd"))
    for d in (flag, env, cwd):
        d.mkdir()
    monkeypatch.chdir(cwd)
    assert workspace.resolve(None) == cwd.resolve()
    monkeypatch.setenv(workspace.ENV_VAR, str(env))
    assert workspace.resolve(None) == env.resolve()
    assert workspace.resolve(str(flag)) == flag.resolve()
    assert workspace.resolve("../flag") == flag.resolve()  # relative to the cwd
    with pytest.raises(workspace.WorkspaceError):
        workspace.resolve("  ")


def test_cli_uses_the_flag_over_the_env(project, tmp_path, monkeypatch, capsys):
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setenv(workspace.ENV_VAR, str(other))
    assert generate.main(["--json", "--dry-run", "--workspace", str(project)]) == 0
    assert json.loads(capsys.readouterr().out)["workspace"] == str(project.resolve())
    assert generate.main(["--json", "--dry-run"]) == 2  # $HEADSHOT_WORKSPACE has no photos
    assert json.loads(capsys.readouterr().out)["workspace"] == str(other.resolve())


def test_rank_takes_the_workspace_before_or_after_the_command(tmp_path, capsys):
    E = ColourEmbed()
    for sub, base in (("refs", 0), ("holdout", 3)):
        d = tmp_path / "photos" / sub
        d.mkdir(parents=True)
        for i in range(3):
            E.add(d / f"p{i}.png", (200, 10 + base * 10 + i * 10, 10), ident(base + i))
    for argv in (
        ["--workspace", str(tmp_path), "check", "--json"],
        ["check", "--json", "--workspace", str(tmp_path)],
    ):
        assert rank.main(argv, embed=E) == 0
        assert json.loads(capsys.readouterr().out)["workspace"] == str(tmp_path.resolve())


def test_data_folders_get_a_gitignore(project):
    from conftest import OK, VariedClient

    assert run(project, *OK, client=VariedClient()) == 0
    assert (project / "out" / ".gitignore").read_text() == "*\n"
    (project / "out" / ".gitignore").write_text("mine\n")
    assert run(project, *OK, "--again", client=VariedClient()) == 0
    assert (project / "out" / ".gitignore").read_text() == "mine\n"  # never overwritten


def test_split_gives_photos_a_gitignore(tmp_path):
    E = ColourEmbed()
    inbox = tmp_path / "photos" / "inbox"
    inbox.mkdir(parents=True)
    for i in range(6):
        E.add(inbox / f"p{i}.png", (100 + i * 10, 50, 50), ident(i, 0.5))
    assert rank.main(["split", "--json"], embed=E, root=tmp_path) == 0
    assert (tmp_path / "photos" / ".gitignore").read_text() == "*\n"


def test_dry_run_writes_nothing(project):
    before = sorted(p for p in project.rglob("*"))
    assert run(project, "--dry-run") == 0
    assert sorted(p for p in project.rglob("*")) == before


def test_script_help_runs_from_another_folder(tmp_path):
    """Sibling imports resolve from the script's own folder, whatever the cwd."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "generate.py"), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0 and "--workspace" in proc.stdout
