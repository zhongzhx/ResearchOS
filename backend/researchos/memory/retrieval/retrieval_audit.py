from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.researchos.memory.memory_config import append_jsonl, ensure_memoryos_dirs, redact_payload, safe_project_id, utc_now_iso


def context_hash(payload: Any) -> str:
    text = json.dumps(redact_payload(payload), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _path(project_id: str) -> Path:
    return ensure_memoryos_dirs()["retrieval_audits"] / safe_project_id(project_id) / "audits.jsonl"


def write_retrieval_audit(project_id: str, context_hash: str, selected_sources: list[dict[str, Any]]) -> dict[str, Any]:
    audit = {
        "audit_id": f"audit_{context_hash}",
        "project_id": project_id,
        "context_hash": context_hash,
        "selected_sources": redact_payload(selected_sources, max_chars=2000),
        "created_at": utc_now_iso(),
    }
    append_jsonl(_path(project_id), audit)
    return audit

