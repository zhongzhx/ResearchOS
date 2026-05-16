from __future__ import annotations

from typing import Any

from backend.researchos.memory.memory_item import update_access_stats
from backend.researchos.memory.retrieval.hybrid_ranker import rank_memory_candidates
from backend.researchos.memory.semantic.semantic_memory_store import list_semantic_memories


def retrieve_memories(project_id: str, query: str, memory_types: list[str] | None = None, top_k: int = 20) -> list[dict[str, Any]]:
    candidates = []
    for item in list_semantic_memories(project_id, status=""):
        if item.get("status") not in {"active", "needs_review"}:
            continue
        if memory_types and item.get("memory_type") not in memory_types:
            continue
        candidates.append(item)
    ranked = rank_memory_candidates(candidates, query)[:top_k]
    results = []
    for item in ranked:
        try:
            update_access_stats(str(item["memory_id"]))
        except Exception:
            pass
        results.append(
            {
                "source_id": (item.get("source_ids") or [item.get("memory_id")])[0],
                "memory_id": item.get("memory_id"),
                "title": item.get("title"),
                "memory_type": item.get("memory_type"),
                "confidence": item.get("confidence"),
                "score": item.get("score"),
                "match_reason": item.get("match_reason"),
                "summary": str(item.get("content") or "")[:700],
            }
        )
    return results

