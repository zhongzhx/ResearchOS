from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{4,}"),
    re.compile(r"(?i)\b(api[_ -]?key|token|password|secret|cookie)\b\s*[:=]\s*['\"]?[^'\"\s,;}]+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]+=*"),
]
SECRET_KEYS = {"api_key", "apikey", "token", "password", "secret", "cookie", "authorization"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def memoryos_root() -> Path:
    configured = os.environ.get("MEMORYOS_ROOT") or os.environ.get("RESEARCHOS_MEMORYOS_DIR")
    agent_data_dir = os.environ.get("RESEARCHOS_AGENT_DATA_DIR")
    return Path(configured or (Path(agent_data_dir) / "memoryos" if agent_data_dir else Path.cwd() / "data" / "memoryos"))


def ensure_memoryos_dirs() -> dict[str, Path]:
    root = memoryos_root()
    dirs = {
        "events": root / "events",
        "working": root / "working",
        "episodic": root / "episodic",
        "semantic": root / "semantic",
        "retrieval_audits": root / "retrieval_audits",
        "health_reports": root / "health_reports",
        "archives": root / "archives",
        "learning": root / "learning",
        "conflicts": root / "conflicts",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def safe_project_id(project_id: str | None) -> str:
    value = str(project_id or "global").strip() or "global"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def json_safe(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def contains_secret(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in SECRET_KEYS and str(item) != "[REDACTED]":
                return True
            if contains_secret(item):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(contains_secret(item) for item in value)
    text = str(value or "")
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def redact_text(text: Any, max_chars: int | None = None) -> str:
    value = str(text or "")
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    if max_chars is not None and len(value) > max_chars:
        value = value[:max_chars] + "...[truncated]"
    return value


def redact_payload(value: Any, max_chars: int | None = None) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SECRET_KEYS:
                cleaned[str(key)] = "[REDACTED]"
            else:
                cleaned[str(key)] = redact_payload(item, max_chars=max_chars)
        return cleaned
    if isinstance(value, list):
        return [redact_payload(item, max_chars=max_chars) for item in value]
    if isinstance(value, tuple):
        return [redact_payload(item, max_chars=max_chars) for item in value]
    if isinstance(value, str):
        return redact_text(value, max_chars=max_chars)
    return value


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(json_safe(payload), ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(json_safe(row), ensure_ascii=False, sort_keys=True) + "\n")
