"""Minimal stdlib .env loader.

Reads KEY=VALUE lines from a .env file (project root by default) into
`os.environ`, leaving already-set variables untouched.
"""

from __future__ import annotations

import os
from pathlib import Path


def _find_env() -> Path | None:
    # Walk up from this file and from cwd; first .env wins. Handles both the
    # dev layout (src/lib/env.py with .env at repo root) and the Pi layout
    # (lib/env.py with .env at ~/frame/.env).
    for start in (Path(__file__).resolve().parent, Path.cwd().resolve()):
        for d in (start, *start.parents):
            candidate = d / ".env"
            if candidate.is_file():
                return candidate
    return None


def load_env(path: Path | None = None) -> None:
    env_path = path or _find_env()
    if env_path is None or not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def require(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"missing required env var: {key} (set it in .env or the environment)")
    return value
