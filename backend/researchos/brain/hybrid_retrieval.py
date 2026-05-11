from __future__ import annotations

from typing import Any

from .brain_page import brain_root, read_brain_page
from .research_graph import graph_neighbors


def _page_result(page: dict[str, Any], score: float, evidence_type: str) -> dict[str, Any]:
    fm = page["frontmatter"]
    return {"source_id": (fm.get("source_ids") or [fm.get("slug")])[0], "page_slug": fm.get("slug"), "title": fm.get("title"), "project_id": fm.get("project_id"), "confidence": fm.get("confidence"), "evidence_type": evidence_type, "score": score, "compiled_truth": page.get("compiled_truth", "")[:500]}


def keyword_search(query: str, project_id: str | None = None, filters: dict[str, Any] | None = None, top_k: int = 20) -> list[dict[str, Any]]:
    terms = [term.lower() for term in str(query or "").split() if term.strip()]
    results = []
    for path in brain_root().rglob("*.md"):
        page = read_brain_page(path.stem)
        if project_id and page["frontmatter"].get("project_id") != project_id:
            continue
        text = (page["compiled_truth"] + " " + str(page["frontmatter"].get("title"))).lower()
        score = sum(1 for term in terms if term in text)
        if score:
            results.append(_page_result(page, float(score), page["frontmatter"].get("type", "page")))
    return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]


def vector_search(query: str, project_id: str | None = None, filters: dict[str, Any] | None = None, top_k: int = 20) -> list[dict[str, Any]]:
    return []


def graph_search(query: str, project_id: str | None = None, filters: dict[str, Any] | None = None, top_k: int = 20) -> list[dict[str, Any]]:
    seed_results = keyword_search(query, project_id, filters, top_k=5)
    results = []
    for seed in seed_results:
        for edge in graph_neighbors(seed["page_slug"], depth=1):
            results.append({"source_id": edge.get("target_slug"), "page_slug": edge.get("target_slug"), "confidence": edge.get("confidence", "medium"), "evidence_type": "graph_edge", "score": 1.0, "relation_type": edge.get("relation_type")})
    return results[:top_k]


def rrf_fuse(result_groups: list[list[dict[str, Any]]], k: int = 60) -> list[dict[str, Any]]:
    scores: dict[str, dict[str, Any]] = {}
    for group in result_groups:
        for rank, item in enumerate(group):
            key = str(item.get("source_id") or item.get("page_slug"))
            if key not in scores:
                scores[key] = dict(item)
                scores[key]["score"] = 0.0
            scores[key]["score"] += 1.0 / (k + rank + 1)
    return sorted(scores.values(), key=lambda item: item.get("score", 0), reverse=True)


def source_aware_dedup(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduped = []
    for item in results:
        key = item.get("source_id") or item.get("page_slug")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def compiled_truth_boost(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for item in results:
        if item.get("compiled_truth"):
            item["score"] = item.get("score", 0) + 0.05
    return sorted(results, key=lambda item: item.get("score", 0), reverse=True)


def project_evidence_boost(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for item in results:
        if item.get("evidence_type") in {"experiment", "dataset", "claim"}:
            item["score"] = item.get("score", 0) + 0.05
    return sorted(results, key=lambda item: item.get("score", 0), reverse=True)


def claim_confidence_boost(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {"high": 0.08, "medium": 0.04, "low": 0.0}
    for item in results:
        item["score"] = item.get("score", 0) + order.get(str(item.get("confidence")), 0.0)
    return sorted(results, key=lambda item: item.get("score", 0), reverse=True)


def hybrid_search(query: str, project_id: str | None = None, filters: dict[str, Any] | None = None, top_k: int = 10) -> list[dict[str, Any]]:
    groups = [keyword_search(query, project_id, filters), vector_search(query, project_id, filters), graph_search(query, project_id, filters)]
    fused = rrf_fuse(groups)
    return claim_confidence_boost(project_evidence_boost(compiled_truth_boost(source_aware_dedup(fused))))[:top_k]
