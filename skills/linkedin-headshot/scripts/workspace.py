"""Where the human's data lives. Must not import insightface.

The skill folder holds only read-only bundled files (scripts, assets/prompt.txt).
Photos, outputs and look.toml live in a separate workspace folder, chosen by
--workspace, then $HEADSHOT_WORKSPACE, then the current directory.
"""

from __future__ import annotations

import os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
PROMPT_PATH = SKILL_DIR / "assets" / "prompt.txt"
ENV_VAR = "HEADSHOT_WORKSPACE"
IGNORE_ALL = "*\n"


class WorkspaceError(Exception):
    """The workspace cannot be used (exit 2)."""


def resolve(arg: str | None, *, env=None, cwd: Path | None = None) -> Path:
    """The absolute workspace: --workspace, then $HEADSHOT_WORKSPACE, then cwd."""
    env = os.environ if env is None else env
    raw = arg if arg is not None else env.get(ENV_VAR) or None
    if raw is not None and not raw.strip():
        raise WorkspaceError("--workspace needs a path (got an empty value)")
    base = Path.cwd() if cwd is None else cwd
    try:
        path = (base / Path(raw).expanduser()).resolve() if raw is not None else base.resolve()
    except (OSError, ValueError, RuntimeError) as exc:
        raise WorkspaceError(f"cannot resolve workspace {raw!r}: {exc}") from exc
    return validate(path)


def validate(path: Path) -> Path:
    """Refuse the skill folder (and anything inside it), / and $HOME itself."""
    path = Path(path).resolve()
    if path == SKILL_DIR or path.is_relative_to(SKILL_DIR):
        raise WorkspaceError(
            f"workspace {path} is inside the skill folder; pass --workspace with a "
            "folder of its own (for example ~/Headshots)"
        )
    if path == Path(path.anchor):
        raise WorkspaceError("the filesystem root cannot be the workspace; pass --workspace")
    home = Path.home().resolve()
    if path == home:
        raise WorkspaceError(
            "your home folder cannot be the workspace; pass --workspace with a "
            "folder of its own (for example ~/Headshots)"
        )
    if not path.is_dir():
        raise WorkspaceError(f"workspace {path} is not an existing folder; create it first")
    return path


def protect(folder: Path) -> None:
    """Give a data folder a .gitignore of '*', so a workspace inside a git repo
    never commits faces or outputs. An existing .gitignore is left alone."""
    marker = folder / ".gitignore"
    if not marker.exists():
        marker.write_text(IGNORE_ALL)
