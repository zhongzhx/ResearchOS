from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .database import connect
from .embeddings import cosine, create_embedding
from .models import as_list, evidence_weight, json_loads, row_to_dict, tokenize


def infer_memory_types_for_query(query: str) -> list[str]:
    lower = query.lower()
    if any(term in lower for term in ["manuscript", "paper", "write", "figure", "论文", "写作", "投稿"]):
        return ["project_memory", "experiment_memory", "conclusion_memory", "dataset_memory", "writing_memory", "preference_memory", "failure_memory"]
    if any(term in lower for term in ["troubleshoot", "fail", "negative", "avoid", "失败", "排错", "避免"]):
        return ["failure_memory", "experiment_memory", "protocol_memory", "decision_memory"]
    if any(term in lower for term in ["data", "analysis", "file", "统计", "数据", "文件"]):
        return ["dataset_memory", "analysis_memory", "experiment_memory"]
    if any(term in lower for term in ["next", "plan", "decision", "下一步", "计划", "决定"]):
        return ["project_memory", "task_memory", "decision_memory", "failure_memory", "conclusion_memory", "experiment_memory"]
    return []


def _days_old(timestamp: str) -> float:
    try:
        dt = datetime.fromisoformat(timestamp)
    except ValueError:
        return 365.0
    return max(0.0, (datetime.now() - dt).total_seconds() / 86400)


def _json_contains(value: Any, needles: list[str]) -> bool:
    haystack = json.dumps(value, ensure_ascii=False).lower()
    return any(needle.lower() in haystack for needle in needles)


def retrieve_memory(
    agent_root: Path,
    user_id: str,
    group_id: str | None = None,
    query: str | None = None,
    project_id: str | None = None,
    experiment_id: str | None = None,
    memory_types: list[str] | None = None,
    entities: list[str] | None = None,
    tags: list[str] | None = None,
    time_range: dict[str, str] | None = None,
    include_archived: bool = False,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    query = query or ""
    memory_types = memory_types or infer_memory_types_for_query(query)
    entities = entities or []
    tags = tags or []
    qtokens = set(tokenize(query))
    qvec = create_embedding(query) if query else []

    sql = [
        """
        SELECT l.*, e.vector_json AS embedding_vector_json
        FROM memory_ledger l
        LEFT JOIN memory_embeddings e ON e.id=l.embedding_id
        WHERE (?='' OR l.user_id=?)
          AND (?='' OR COALESCE(l.group_id,'')=?)
          AND (?='' OR COALESCE(l.project_id,'')=?)
          AND (?='' OR COALESCE(l.experiment_id,'')=?)
        """
    ]
    params: list[Any] = [
        user_id or "",
        user_id or "",
        group_id or "",
        group_id or "",
        project_id or "",
        project_id or "",
        experiment_id or "",
        experiment_id or "",
    ]
    if not include_archived:
        sql.append("AND l.status NOT IN ('archived', 'deleted', 'superseded')")
    if memory_types:
        placeholders = ",".join("?" for _ in memory_types)
        sql.append(f"AND l.memory_type IN ({placeholders})")
        params.extend(memory_types)
    if time_range:
        if time_range.get("from"):
            sql.append("AND l.timestamp >= ?")
            params.append(time_range["from"])
        if time_range.get("until"):
            sql.append("AND l.timestamp <= ?")
            params.append(time_range["until"])
    sql.append("ORDER BY l.timestamp DESC LIMIT 500")

    conn = connect(agent_root)
    rows = conn.execute("\n".join(sql), params).fetchall()
    conn.close()

    results = []
    for row in rows:
        item = row_to_dict(row)
        item.pop("embedding_vector", None)
        text = " ".join([str(item.get("subject", "")), str(item.get("content", "")), json.dumps(item.get("structured_content", {}), ensure_ascii=False)])
        tokens = set(tokenize(text))
        keyword_score = len(qtokens & tokens) / max(1, len(qtokens)) if qtokens else 0.0
        metadata_score = 0.0
        if project_id and item.get("project_id") == project_id:
            metadata_score += 0.25
        if experiment_id and item.get("experiment_id") == experiment_id:
            metadata_score += 0.25
        if entities and _json_contains(item.get("entities", {}), entities):
            metadata_score += 0.35
        if tags and _json_contains(item.get("tags", []), tags):
            metadata_score += 0.25
        semantic_score = 0.0
        vector_json = row["embedding_vector_json"]
        if qvec and vector_json:
            try:
                semantic_score = cosine(qvec, json.loads(vector_json))
            except json.JSONDecodeError:
                semantic_score = 0.0
        recency_score = max(0.0, 0.2 - min(_days_old(item.get("timestamp") or item.get("created_at") or ""), 365) / 365 * 0.2)
        confidence_score = min(1.0, float(item.get("confidence") or 0.5)) * 0.15
        evidence_score = evidence_weight(str(item.get("evidence_strength") or "")) * 0.1
        active_score = 0.1 if item.get("status") not in {"archived", "deleted", "superseded"} else -0.2
        score = keyword_score * 0.45 + semantic_score * 0.3 + metadata_score + recency_score + confidence_score + evidence_score + active_score
        if not query and not entities and not tags:
            score += 0.1
        if score > 0 or not query:
            item["score"] = round(score, 4)
            results.append(item)

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:max_results]


def list_project_memory(agent_root: Path, project_id: str, include_archived: bool = False) -> list[dict[str, Any]]:
    return retrieve_memory(agent_root, user_id="", project_id=project_id, include_archived=include_archived, max_results=200)


def list_experiment_memory(agent_root: Path, experiment_id: str, include_archived: bool = False) -> list[dict[str, Any]]:
    return retrieve_memory(agent_root, user_id="", experiment_id=experiment_id, include_archived=include_archived, max_results=200)
