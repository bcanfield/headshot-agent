"""Shared --json plumbing for generate.py and rank.py. Must not import insightface."""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import sys


class UsageError(Exception):
    """A command-line usage error under --json (exit 2)."""


class JsonArgumentParser(argparse.ArgumentParser):
    """With json_mode set, a usage error raises UsageError instead of exiting,
    so main() can print it as one JSON object."""

    json_mode = False

    def error(self, message):
        if self.json_mode:
            raise UsageError(f"usage: {message}")
        super().error(message)


def parse_args(parser: argparse.ArgumentParser, argv) -> argparse.Namespace:
    """parse_args that turns usage errors into UsageError when --json is in argv."""
    argv = sys.argv[1:] if argv is None else list(argv)
    wants_json = "--json" in argv
    stack = [parser]
    while stack:
        p = stack.pop()
        p.json_mode = wants_json
        for action in p._actions:
            if isinstance(action, argparse._SubParsersAction):
                stack.extend(action.choices.values())
    return parser.parse_args(argv)


@contextlib.contextmanager
def stdout_to_stderr(enabled: bool = True):
    """Send everything written to stdout (Python and C level) to stderr, so that
    under --json stdout carries only the final JSON object."""
    if not enabled:
        yield
        return
    sys.stdout.flush()
    saved = None
    try:
        fd = sys.__stdout__.fileno()
        sys.__stdout__.flush()
        saved = os.dup(fd)
        os.dup2(sys.__stderr__.fileno(), fd)
    except (AttributeError, OSError, ValueError):
        saved = None
    try:
        with contextlib.redirect_stdout(sys.stderr):
            yield
    finally:
        sys.stderr.flush()
        if saved is not None:
            os.dup2(saved, sys.__stdout__.fileno())
            os.close(saved)


def unexpected(exc: BaseException) -> str:
    return f"unexpected {type(exc).__name__}: {exc}"


def _finite(obj):
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: _finite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_finite(v) for v in obj]
    return obj


def dumps(obj, **kwargs) -> str:
    """json.dumps that always yields strict JSON: NaN/inf become null and any
    non-JSON value becomes its str(), so the --json contract cannot break."""
    return json.dumps(_finite(obj), allow_nan=False, default=str, **kwargs)
