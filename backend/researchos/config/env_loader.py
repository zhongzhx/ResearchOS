from __future__ import annotations

import os
from pathlib import Path
from typing import Any


SECRET_NAME_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "COOKIE", "AUTHORIZATION")
TRUE_VALUES = {"1", "true", "yes", "on", "y"}
FALSE_VALUES = {"0", "false", "no", "off", "n"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return (key, value) if key else None


def load_env_file(env_path: str | Path | None = None) -> dict[str, str]:
    """Load a dotenv-style file into os.environ without overriding existing values."""

    path = Path(env_path) if env_path else _repo_root() / ".env"
    if not path.exists():
        return {}
    loaded: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parsed = _parse_env_line(raw_line)
        if not parsed:
            continue
        key, value = parsed
        loaded[key] = value
        os.environ.setdefault(key, value)
    return loaded


def get_env(name: str, default: Any = None, required: bool = False) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        if required:
            raise RuntimeError(f"missing required environment variable: {name}")
        return default
    return value


def get_bool_env(name: str, default: bool = False) -> bool:
    value = get_env(name)
    if value is None:
        return default
    lowered = str(value).strip().lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    return default


def get_int_env(name: str, default: int = 0) -> int:
    value = get_env(name)
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except ValueError:
        return default


def redact_env_value(name: str, value: str | None) -> str:
    text = str(value or "")
    if not text:
        return ""
    if any(marker in name.upper() for marker in SECRET_NAME_MARKERS):
        return f"****{text[-4:]}" if len(text) > 4 else "****"
    return text
