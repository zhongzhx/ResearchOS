from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.researchos.memory.memory_config import utc_now_iso
from backend.researchos.memory.semantic.semantic_memory_store import list_semantic_memories, load_semantic_memory, update_semantic_memory


def _parse_time(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def compute_decay_score(memory_item: dict[str, Any], now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    updated = _parse_time(str(memory_item.get("last_accessed_at") or memory_item.get("updated_at") or memory_item.get("created_at") or ""))
    age_days = max(0.0, (now - updated).total_seconds() / 86400)
    confidence_factor = {"high": 0.5, "medium": 0.8, "low": 1.0}.get(str(memory_item.get("confidence")), 1.0)
    importance = float(memory_item.get("importance_score") or 0.0)
    retrievals = int(memory_item.get("retrieval_count") or 0)
    score = (age_days / 90.0) * confidence_factor * (1.0 - min(0.8, importance)) / (1 + retrievals)
    return round(max(0.0, min(1.0, score)), 6)


def apply_forgetting_curve(project_id: str) -> dict[str, Any]:
    updated = []
    for item in list_semantic_memories(project_id, status=""):
        score = compute_decay_score(item)
        updated.append(update_semantic_memory(item["memory_id"], {"decay_score": score}))
    return {"project_id": project_id, "updated": len(updated)}


def reinforce_on_retrieval(memory_id: str) -> dict[str, Any]:
    item = load_semantic_memory(memory_id)
    return update_semantic_memory(memory_id, {"retrieval_count_delta": 1, "last_accessed_at": utc_now_iso(), "importance_delta": 0.03, "decay_score": max(0.0, float(item.get("decay_score") or 0) - 0.1)})


def mark_for_archive_if_cold(memory_id: str) -> dict[str, Any]:
    item = load_semantic_memory(memory_id)
    score = compute_decay_score(item)
    if score > 0.75 and float(item.get("importance_score") or 0) < 0.3 and item.get("confidence") == "low":
        return update_semantic_memory(memory_id, {"status": "needs_review", "decay_score": score, "provenance_append": {"archive_candidate": True}})
    return update_semantic_memory(memory_id, {"decay_score": score})

