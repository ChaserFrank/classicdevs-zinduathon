"""Tiny helpers for reading typed settings from environment variables.

Why not django-environ: these four functions are all we need, and keeping them here means one less
dependency to explain. Every setting in the project is read through these, so `.env.example` is the
single list of knobs.
"""

import os


def env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value not in (None, "") else default


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]
