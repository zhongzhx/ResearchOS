from __future__ import annotations

from typing import Any

from backend.researchos.memory.semantic.semantic_memory_store import find_semantic_duplicates, update_semantic_memory


def find_similar_memories(project_id: str, item: dict[str, Any]) -> list[dict[str, Any]]:
    return find_semantic_duplicates(project_id, item)


def should_merge(item_a: dict[str, Any], item_b: dict[str, Any]) -> bool:
    if item_a.get("memory_type") != item_b.get("memory_type"):
        return False
    if item_a.get("status") == "archived" or item_b.get("status") == "archived":
        return False
    if item_a.get("confidence") == "high" or item_b.get("confidence") == "high":
        return False
    return str(item_a.get("title", "")).strip().lower() == str(item_b.get("title", "")).strip().lower() or str(item_a.get("content", "")).strip().lower() == str(item_b.get("content", "")).strip().lower()


def merge_memory_items(item_a: dict[str, Any], item_b: dict[str, Any]) -> dict[str, Any]:
    if not should_merge(item_a, item_b):
        return {"merged": False, "reason": "merge policy rejected"}
    merged_sources = sorted(set(list(item_a.get("source_ids") or []) + list(item_b.get("source_ids") or [])))
    merged = update_semantic_memory(str(item_a["memory_id"]), {"source_ids": merged_sources, "provenance_append": {"merged_from": item_b.get("memory_id")}})
    update_semantic_memory(str(item_b["memory_id"]), {"status": "superseded", "superseded_by": item_a["memory_id"]})
    return {"merged": True, "memory": merged, "superseded": item_b["memory_id"]}

