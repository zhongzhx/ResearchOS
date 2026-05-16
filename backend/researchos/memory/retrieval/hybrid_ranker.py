from __future__ import annotations

import json
import math
from typing import Any


def _terms(query: str) -> list[str]:
    return [term.lower() for term in str(query or "").split() if term.strip()]


def _keyword_score(item: dict[str, Any], query: str) -> float:
    terms = _terms(query)
    if not terms:
        return 0.0
    text = json.dumps({"title": item.get("title"), "content": item.get("content"), "tags": item.get("tags")}, ensure_ascii=False).lower()
    return sum(1 for term in terms if term in text) / len(terms)


def compute_memory_score(memory_item: dict[str, Any], query: str, intent: str | None = None) -> float:
    keyword_match_score = _keyword_score(memory_item, query)
    semantic_similarity_score = float(memory_item.get("semantic_similarity_score") or 0.0)
    graph_proximity_score = float(memory_item.get("graph_proximity_score") or 0.0)
    confidence_score = {"low": 0.1, "medium": 0.3, "high": 0.5}.get(str(memory_item.get("confidence")), 0.2)
    importance_score = float(memory_item.get("importance_score") or 0.0)
    recency_score = 0.15 if memory_item.get("updated_at") else 0.0
    retrieval_frequency_score = min(0.2, math.log1p(int(memory_item.get("retrieval_count") or 0)) / 10)
    project_relevance_score = 0.2 if memory_item.get("project_id") else 0.0
    decay_penalty = float(memory_item.get("decay_score") or 0.0) * 0.2
    contradiction_penalty = 0.3 if memory_item.get("status") == "needs_review" else 0.0
    score = (
        keyword_match_score
        + semantic_similarity_score
        + graph_proximity_score
        + confidence_score
        + importance_score
        + recency_score
        + retrieval_frequency_score
        + project_relevance_score
        - decay_penalty
        - contradiction_penalty
    )
    if intent and intent in (memory_item.get("tags") or []):
        score += 0.15
    return round(max(0.0, score), 6)


def rank_memory_candidates(candidates: list[dict[str, Any]], query: str, intent: str | None = None) -> list[dict[str, Any]]:
    ranked = []
    for item in candidates:
        score = compute_memory_score(item, query, intent=intent)
        if score <= 0:
            continue
        row = dict(item)
        row["score"] = score
        row["match_reason"] = "keyword/confidence/importance rank"
        ranked.append(row)
    return sorted(ranked, key=lambda item: item.get("score", 0), reverse=True)

