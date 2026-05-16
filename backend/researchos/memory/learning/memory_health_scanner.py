from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.researchos.memory.governance.conflict_resolver import detect_conflicts
from backend.researchos.memory.memory_config import ensure_memoryos_dirs, safe_project_id, utc_now_iso, write_json
from backend.researchos.memory.semantic.semantic_memory_store import list_semantic_memories


def find_unsupported_claims(project_id: str) -> list[dict[str, Any]]:
    return [item for item in list_semantic_memories(project_id, memory_type="claim", status="") if not item.get("source_ids") and not item.get("artifact_ids") and item.get("confidence") in {"medium", "high"}]


def find_stale_memories(project_id: str) -> list[dict[str, Any]]:
    return [item for item in list_semantic_memories(project_id, status="") if float(item.get("decay_score") or 0) > 0.6 or item.get("status") == "needs_review"]


def find_duplicate_memories(project_id: str) -> list[dict[str, Any]]:
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    duplicates = []
    for item in list_semantic_memories(project_id, status=""):
        key = (str(item.get("memory_type")), str(item.get("title")).strip().lower(), str(item.get("content")).strip().lower())
        if key in seen:
            duplicates.append({"first": seen[key], "duplicate": item})
        else:
            seen[key] = item
    return duplicates


def find_conflicting_claims(project_id: str) -> list[dict[str, Any]]:
    return detect_conflicts(project_id)


def find_context_bloat(project_id: str) -> dict[str, Any]:
    memories = list_semantic_memories(project_id, status="")
    total_chars = sum(len(str(item.get("content") or "")) for item in memories)
    return {"project_id": project_id, "estimated_context_items": len(memories), "estimated_context_chars": total_chars, "bloated": len(memories) > 100 or total_chars > 120000}


def scan_memory_health(project_id: str) -> dict[str, Any]:
    report = {
        "project_id": project_id,
        "unsupported_claims": find_unsupported_claims(project_id),
        "stale_memories": find_stale_memories(project_id),
        "duplicate_memories": find_duplicate_memories(project_id),
        "conflicting_claims": find_conflicting_claims(project_id),
        "context_bloat": find_context_bloat(project_id),
        "created_at": utc_now_iso(),
    }
    path = ensure_memoryos_dirs()["health_reports"] / safe_project_id(project_id) / "memory_health.json"
    write_json(path, report)
    return report

