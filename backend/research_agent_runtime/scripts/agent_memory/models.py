from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any


MEMORY_TYPES = {
    "user_profile_memory",
    "group_profile_memory",
    "project_memory",
    "experiment_memory",
    "sample_memory",
    "protocol_memory",
    "dataset_memory",
    "analysis_memory",
    "decision_memory",
    "conclusion_memory",
    "failure_memory",
    "writing_memory",
    "task_memory",
    "literature_memory",
    "preference_memory",
}

MEMORY_ACTIONS = {
    "ignore",
    "append_memory",
    "update_view",
    "supersede_old_memory",
    "create_project",
    "update_project",
    "create_experiment",
    "update_experiment",
    "create_sample",
    "update_sample",
    "create_protocol",
    "update_protocol",
    "create_dataset",
    "update_dataset",
    "delete_or_archive_memory",
}

EVIDENCE_STRENGTHS = {
    "raw_observation",
    "preliminary",
    "replicated",
    "statistically_supported",
    "mechanism_supported",
    "publication_ready",
    "contradicted",
    "invalidated",
}

ACTIVE_STATUSES = {"active", "current", "pending", "completed", "needs_review"}
INACTIVE_STATUSES = {"archived", "superseded", "deleted", "inactive"}


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def stable_id(*parts: Any, length: int = 24) -> str:
    joined = "|".join(clean(part) for part in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:length]


def json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else None, ensure_ascii=False, sort_keys=True)


def json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return default


def as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            parsed = json_loads(stripped, [])
            return parsed if isinstance(parsed, list) else [parsed]
        return [item.strip() for item in re.split(r"[,;，；\n]+", stripped) if item.strip()]
    return [value]


def as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    parsed = json_loads(value, {})
    return parsed if isinstance(parsed, dict) else {}


def row_to_dict(row: Any) -> dict[str, Any]:
    item = dict(row)
    for key in list(item.keys()):
        if key.endswith("_json"):
            parsed_key = key[:-5]
            item[parsed_key] = json_loads(item.pop(key), [] if key.endswith("ids_json") or key in {"tags_json", "entities_json"} else {})
    return item


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z0-9_.+-]{2,}|[\u4e00-\u9fa5]{2,}", text or "")]


def evidence_weight(value: str) -> float:
    weights = {
        "raw_observation": 0.55,
        "preliminary": 0.6,
        "replicated": 0.78,
        "statistically_supported": 0.85,
        "mechanism_supported": 0.9,
        "publication_ready": 0.95,
        "contradicted": 0.35,
        "invalidated": 0.2,
    }
    return weights.get(clean(value), 0.5)


def truncate(text: str, limit: int) -> str:
    text = clean(text)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."
