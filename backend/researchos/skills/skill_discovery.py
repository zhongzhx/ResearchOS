from __future__ import annotations

import re
from typing import Any

from backend.researchos.skills.pipeline_registry import list_pipelines
from backend.researchos.skills.skill_catalog_loader import get_skill_by_id, list_active_skills


QUERY_SYNONYMS = {
    "分析": ["analyze", "analysis", "parse", "data", "scientific", "experiment", "results"],
    "数据": ["data", "dataset", "scientific"],
    "结果": ["result", "results", "narrative", "analysis"],
    "生成": ["generate", "generation", "create", "draft"],
    "方法": ["method", "protocol"],
    "实验": ["experiment", "protocol"],
    "文献": ["literature", "paper", "reference"],
    "审稿": ["review", "peer", "critique"],
    "失败": ["failure", "bottleneck", "diagnose"],
    "周报": ["weekly", "report", "digest"],
    "实体": ["entity", "entities", "extract"],
    "路线": ["route", "planning", "plan"],
    "csv": ["csv", "data", "table"],
    "sop": ["sop", "protocol", "standard operating procedure"],
}


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").casefold().replace("_", " ").replace("-", " ").split())


def _terms(query: str) -> set[str]:
    normalized = _normalize(query)
    terms = set(re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{1,4}", normalized))
    for key, values in QUERY_SYNONYMS.items():
        if key in normalized:
            terms.update(values)
    return {term for term in terms if term}


def _catalog_summary(row: dict[str, Any]) -> dict[str, Any]:
    searchable_fields = [
        row.get("skill_id"),
        row.get("display_name"),
        row.get("category"),
        row.get("canonical_path"),
        " ".join(row.get("legacy_paths") or []),
        " ".join(row.get("input_types") or []),
        " ".join(row.get("output_types") or []),
        " ".join(row.get("promotion_targets") or []),
        row.get("notes"),
    ]
    return {
        "skill_id": row.get("skill_id"),
        "display_name": row.get("display_name") or row.get("skill_id"),
        "category": row.get("category"),
        "canonical_path": row.get("canonical_path"),
        "status": row.get("status"),
        "risk_level": row.get("risk_level"),
        "requires_user_authorization": bool(row.get("requires_user_authorization")),
        "allowed_auto_call": bool(row.get("allowed_auto_call")),
        "input_types": list(row.get("input_types") or []),
        "output_types": list(row.get("output_types") or []),
        "promotion_targets": list(row.get("promotion_targets") or []),
        "notes": row.get("notes") or "",
        "summary": " ".join(str(field or "") for field in searchable_fields),
    }


def get_skill_summary(skill_id: str) -> dict[str, Any]:
    return _catalog_summary(get_skill_by_id(skill_id))


def find_candidate_skills_for_query(user_query: str) -> list[dict[str, Any]]:
    query_terms = _terms(user_query)
    candidates = []
    for row in list_active_skills():
        summary = _catalog_summary(row)
        haystack = _normalize(summary["summary"])
        if any(term in haystack for term in query_terms):
            candidates.append(summary)
    return candidates


def _intent_skill_ids(intent: str | None) -> set[str]:
    if not intent:
        return set()
    for pipeline in list_pipelines():
        if intent in {pipeline.get("intent"), pipeline.get("pipeline_name")}:
            return set(pipeline.get("execution_skills") or [])
    return set()


def rank_skill_candidates(candidates: list[dict[str, Any]], user_query: str, intent: str | None = None) -> list[dict[str, Any]]:
    query_terms = _terms(user_query)
    intent_skills = _intent_skill_ids(intent)
    ranked = []
    for candidate in candidates:
        haystack = _normalize(candidate.get("summary"))
        skill_id = str(candidate.get("skill_id") or "")
        score = 0
        for term in query_terms:
            if not term:
                continue
            if term in _normalize(skill_id):
                score += 8
            if term in haystack:
                score += 3
            if term in {_normalize(item) for item in candidate.get("input_types", [])}:
                score += 12
            if term in {_normalize(item) for item in candidate.get("output_types", [])}:
                score += 8
        if skill_id in intent_skills:
            score += 25
        if score > 0:
            ranked.append({**candidate, "score": score})
    return sorted(ranked, key=lambda item: (-int(item.get("score") or 0), str(item.get("skill_id") or "")))


def search_skills(query: str, intent: str | None = None, top_k: int = 5) -> list[dict[str, Any]]:
    candidates = find_candidate_skills_for_query(query)
    return rank_skill_candidates(candidates, query, intent=intent)[:top_k]
