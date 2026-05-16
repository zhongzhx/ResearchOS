from __future__ import annotations

from typing import Any

from backend.researchos.memory.semantic.semantic_memory_store import load_semantic_memory, update_semantic_memory


def assign_initial_confidence(item: dict[str, Any]) -> str:
    if item.get("memory_type") == "hypothesis":
        return "low"
    if item.get("source_ids") or item.get("task_ids") or item.get("skillrun_ids") or item.get("artifact_ids"):
        return str(item.get("confidence") or "medium")
    return "low" if item.get("memory_type") == "claim" else str(item.get("confidence") or "medium")


def promote_confidence(memory_id: str, reason: str, source_ids: list[str]) -> dict[str, Any]:
    if not source_ids:
        raise ValueError("confidence promotion requires source_ids")
    item = load_semantic_memory(memory_id)
    next_conf = "high" if item.get("confidence") == "medium" else "medium"
    existing = list(item.get("source_ids") or [])
    return update_semantic_memory(memory_id, {"confidence": next_conf, "source_ids": sorted(set(existing + source_ids)), "provenance_append": {"confidence_promotion_reason": reason}})


def downgrade_confidence(memory_id: str, reason: str, source_ids: list[str]) -> dict[str, Any]:
    item = load_semantic_memory(memory_id)
    next_conf = "low" if item.get("confidence") in {"medium", "low"} else "medium"
    existing = list(item.get("source_ids") or [])
    return update_semantic_memory(memory_id, {"confidence": next_conf, "source_ids": sorted(set(existing + list(source_ids or []))), "provenance_append": {"confidence_downgrade_reason": reason}})

