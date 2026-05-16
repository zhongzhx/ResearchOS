from __future__ import annotations

from typing import Any

from backend.researchos.memory.events.event_store import append_event
from backend.researchos.memory.governance.archive_policy import archive_memory
from backend.researchos.memory.governance.conflict_resolver import detect_conflicts, mark_conflict
from backend.researchos.memory.governance.decay_policy import apply_forgetting_curve, mark_for_archive_if_cold
from backend.researchos.memory.governance.merge_policy import merge_memory_items, should_merge
from backend.researchos.memory.memory_event import create_memory_event
from backend.researchos.memory.memory_item import MemoryItem, memory_item_to_dict
from backend.researchos.memory.semantic.semantic_memory_store import create_semantic_memory_item, list_semantic_memories, update_semantic_memory


def ingest_memory_item(item: MemoryItem | dict[str, Any]) -> dict[str, Any]:
    created = create_semantic_memory_item(item)
    append_event(create_memory_event("claim_created" if created.get("memory_type") == "claim" else "evidence_promoted", project_id=created.get("project_id"), source_id=created.get("memory_id"), source_type="brain_page", payload={"memory_id": created.get("memory_id"), "memory_type": created.get("memory_type")}))
    return created


def update_memory_item(memory_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    return update_semantic_memory(memory_id, patch)


def merge_similar_memories(project_id: str, memory_type: str | None = None) -> dict[str, Any]:
    rows = list_semantic_memories(project_id, memory_type=memory_type, status="")
    merged = []
    used = set()
    for index, a in enumerate(rows):
        if a["memory_id"] in used:
            continue
        for b in rows[index + 1 :]:
            if b["memory_id"] in used:
                continue
            if should_merge(a, b):
                result = merge_memory_items(a, b)
                if result.get("merged"):
                    used.add(b["memory_id"])
                    merged.append(result)
    return {"project_id": project_id, "merged": merged}


def resolve_memory_conflicts(project_id: str) -> dict[str, Any]:
    detected = detect_conflicts(project_id)
    marked = [mark_conflict(item["memory_a"], item["memory_b"], item["reason"]) for item in detected]
    return {"project_id": project_id, "conflicts": marked}


def archive_stale_memories(project_id: str) -> dict[str, Any]:
    archived = []
    for item in list_semantic_memories(project_id, status=""):
        candidate = mark_for_archive_if_cold(item["memory_id"])
        if candidate.get("status") == "needs_review" and candidate.get("decay_score", 0) > 0.75:
            archived.append(archive_memory(item["memory_id"], "cold low-confidence memory"))
    return {"project_id": project_id, "archived": archived}


def reinforce_memory(memory_id: str, reason: str) -> dict[str, Any]:
    updated = update_semantic_memory(memory_id, {"importance_delta": 0.08, "provenance_append": {"reinforced_reason": reason}})
    append_event(create_memory_event("memory_reinforced", project_id=updated.get("project_id"), source_id=memory_id, source_type="brain_page", payload={"reason": reason}))
    return updated


def run_memory_maintenance(project_id: str) -> dict[str, Any]:
    decay = apply_forgetting_curve(project_id)
    merge = merge_similar_memories(project_id)
    conflicts = resolve_memory_conflicts(project_id)
    archive = archive_stale_memories(project_id)
    return {"project_id": project_id, "decay": decay, "merge": merge, "conflicts": conflicts, "archive": archive}

