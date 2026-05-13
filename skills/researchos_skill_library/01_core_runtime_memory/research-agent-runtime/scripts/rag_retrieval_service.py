from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from pathlib import Path
from typing import Any


VECTOR_SIZE = 128
NORMALIZED_SOURCE_TYPES = {"reference_chunk", "kb_entry", "browser_learning", "brain_note", "agent_memory", "task_status"}


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    item = dict(row)
    for key in list(item.keys()):
        if key.endswith("_json"):
            item[key[:-5]] = json_loads(item.pop(key), [] if key.endswith("s_json") else {})
    return item


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in rows]


def connect_existing(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()
    return {clean(row["name"]) for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def tokens_for_vector(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", clean(text))]


def expanded_query_text(text: str) -> str:
    base = clean(text)
    lower = base.lower()
    extras: list[str] = []
    if "周报" in base or "digest" in lower or "weekly" in lower:
        extras.extend(["weekly", "digest", "weekly_digest", "研究周报"])
    if "刚才" in base or "上次" in base or "previous" in lower or "last" in lower:
        extras.extend(["recent", "previous", "last"])
    return " ".join([base, *extras])


def embed(text: str) -> list[float]:
    vec = [0.0] * VECTOR_SIZE
    for token in tokens_for_vector(text):
        idx = int(hashlib.sha1(token.encode("utf-8")).hexdigest(), 16) % VECTOR_SIZE
        vec[idx] += 1.0
    norm = math.sqrt(sum(value * value for value in vec)) or 1.0
    return [value / norm for value in vec]


def cosine(a: list[float], b: list[float]) -> float:
    size = min(len(a), len(b))
    if size == 0:
        return 0.0
    return sum(a[index] * b[index] for index in range(size))


def _safe_vector(value: Any, fallback_text: str) -> list[float]:
    parsed = json_loads(value, [])
    if isinstance(parsed, list) and parsed and all(isinstance(item, (int, float)) for item in parsed):
        return [float(item) for item in parsed]
    return embed(fallback_text)


def _main_db(agent_root: Path) -> Path:
    return Path(agent_root) / "research_group_os.sqlite"


def _lab_db(agent_root: Path) -> Path:
    return Path(agent_root) / "lab_agent_mvp.sqlite"


def _project_labels(conn: sqlite3.Connection | None, project_id: str) -> set[str]:
    labels = {project_id} if project_id else set()
    if conn is None or not project_id or not table_exists(conn, "projects"):
        return {item for item in labels if item}
    row = row_to_dict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())
    for key in ["id", "project_id", "project_name", "display_name", "title"]:
        if clean(row.get(key)):
            labels.add(clean(row.get(key)))
    return {item for item in labels if item}


def _active_project_filter(conn: sqlite3.Connection, requested_project_id: str, alias: str = "") -> tuple[str, list[Any]]:
    prefix = f"{alias}." if alias else ""
    if not table_exists(conn, "projects"):
        return f"{prefix}project_id=?", [requested_project_id]
    return (
        f"{prefix}project_id IN (SELECT id FROM projects WHERE COALESCE(status,'active') NOT IN ('archived','purged'))",
        [],
    )


def _project_filter(conn: sqlite3.Connection, project_id: str, retrieval_scope: str, alias: str = "") -> tuple[str, list[Any]]:
    if retrieval_scope == "cross_project":
        return _active_project_filter(conn, project_id, alias)
    prefix = f"{alias}." if alias else ""
    return f"{prefix}project_id=?", [project_id]


def _is_browser_learning(source_provider: Any, source_type: Any, evidence_level: Any, text: str = "") -> bool:
    haystack = " ".join(clean(item).lower() for item in [source_provider, source_type, evidence_level, text])
    return "browser" in haystack or "web learning" in haystack


def _peer_reviewed_allowed(source_type: str, source_provider: Any = "", evidence_level: Any = "") -> bool:
    if source_type in {"browser_learning", "kb_entry", "brain_note", "agent_memory", "task_status"}:
        return False
    provider = clean(source_provider).lower()
    level = clean(evidence_level).lower()
    if any(term in provider for term in ["mock", "manual", "browser"]):
        return False
    if any(term in level for term in ["mock", "browser", "not_evidence", "not evidence"]):
        return False
    return source_type == "reference_chunk"


def _citation_key(item: dict[str, Any]) -> str:
    reference_id = clean(item.get("reference_id"))
    if reference_id:
        return f"reference:{reference_id}"
    return f"{clean(item.get('source_type'))}:{clean(item.get('source_id'))}"


def _base_item(
    *,
    source_type: str,
    source_id: str,
    project_id: str,
    title: str,
    text: str,
    source_db: str,
    source_table: str,
    reference_id: str = "",
    chunk_id: str = "",
    source_provider: str = "",
    evidence_level: str = "",
    evidence_role: str = "",
    created_at: str = "",
    updated_at: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_type = clean(source_type)
    if source_type not in NORMALIZED_SOURCE_TYPES:
        source_type = "agent_memory"
    role = clean(evidence_role) or source_type
    item = {
        "source_type": source_type,
        "source_id": clean(source_id),
        "project_id": clean(project_id),
        "reference_id": clean(reference_id),
        "chunk_id": clean(chunk_id),
        "title": clean(title)[:220],
        "text": clean(text),
        "excerpt": clean(text)[:700],
        "source_db": source_db,
        "source_table": source_table,
        "source_provider": clean(source_provider),
        "evidence_level": clean(evidence_level),
        "evidence_role": role,
        "created_at": clean(created_at),
        "updated_at": clean(updated_at or created_at),
        "metadata": metadata or {},
    }
    item["citation_key"] = _citation_key(item)
    item["can_support_peer_reviewed_evidence"] = _peer_reviewed_allowed(source_type, source_provider, evidence_level)
    item["is_peer_reviewed_evidence"] = bool(item["can_support_peer_reviewed_evidence"])
    return item


def _reference_chunk_items(conn: sqlite3.Connection, project_id: str, retrieval_scope: str) -> list[dict[str, Any]]:
    if not table_exists(conn, "reference_chunks") or not table_exists(conn, "references"):
        return []
    ref_columns = table_columns(conn, "references")
    select_fields = ["c.*", "r.title AS reference_title"]
    for column in ["doi", "url", "source_provider", "source_type", "evidence_level", "year", "journal"]:
        if column in ref_columns:
            select_fields.append(f"r.{column} AS reference_{column}")
    where_sql, params = _project_filter(conn, project_id, retrieval_scope, "c")
    rows = rows_to_dicts(
        conn.execute(
            f"""
            SELECT {", ".join(select_fields)}
            FROM reference_chunks c
            JOIN "references" r ON r.id=c.reference_id
            WHERE {where_sql}
            """,
            params,
        ).fetchall()
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        text = clean(row.get("chunk_text") or row.get("text"))
        source_provider = clean(row.get("reference_source_provider"))
        raw_source_type = clean(row.get("reference_source_type"))
        evidence_level = clean(row.get("reference_evidence_level"))
        source_type = "browser_learning" if _is_browser_learning(source_provider, raw_source_type, evidence_level, text) else "reference_chunk"
        items.append(
            _base_item(
                source_type=source_type,
                source_id=row.get("id"),
                project_id=row.get("project_id"),
                reference_id=row.get("reference_id"),
                chunk_id=row.get("id"),
                title=row.get("reference_title") or row.get("citation_id") or row.get("reference_id"),
                text=text,
                source_db="research_group_os.sqlite",
                source_table="reference_chunks",
                source_provider=source_provider or raw_source_type,
                evidence_level=evidence_level,
                evidence_role="browser_learning" if source_type == "browser_learning" else "original_reference_chunk",
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
                metadata={"chunk_index": row.get("chunk_index"), "doi": row.get("reference_doi"), "url": row.get("reference_url")},
            )
        )
    return items


def _kb_items(conn: sqlite3.Connection, project_id: str, retrieval_scope: str) -> list[dict[str, Any]]:
    if not table_exists(conn, "knowledge_base_entries"):
        return []
    where_sql, params = _project_filter(conn, project_id, retrieval_scope)
    rows = rows_to_dicts(conn.execute(f"SELECT * FROM knowledge_base_entries WHERE {where_sql}", params).fetchall())
    return [
        _base_item(
            source_type="kb_entry",
            source_id=row.get("id"),
            project_id=row.get("project_id"),
            reference_id=row.get("source_reference_id"),
            chunk_id=row.get("source_chunk_id") or row.get("id"),
            title=row.get("title") or row.get("entry_type") or "Knowledge base summary",
            text=clean(row.get("content") or row.get("summary")),
            source_db="research_group_os.sqlite",
            source_table="knowledge_base_entries",
            evidence_role="knowledge_base_summary",
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            metadata={"entry_type": row.get("entry_type"), "source_chunk_id": row.get("source_chunk_id")},
        )
        for row in rows
        if clean(row.get("content") or row.get("summary"))
    ]


def _rag_query_items(conn: sqlite3.Connection, project_id: str, retrieval_scope: str) -> list[dict[str, Any]]:
    if not table_exists(conn, "rag_queries"):
        return []
    where_sql, params = _project_filter(conn, project_id, retrieval_scope)
    rows = rows_to_dicts(conn.execute(f"SELECT * FROM rag_queries WHERE {where_sql}", params).fetchall())
    return [
        _base_item(
            source_type="agent_memory",
            source_id=row.get("id"),
            project_id=row.get("project_id"),
            title=clean(row.get("question"))[:160] or "Prior RAG answer",
            text=" ".join([clean(row.get("question")), clean(row.get("answer"))]),
            source_db="research_group_os.sqlite",
            source_table="rag_queries",
            evidence_role="prior_rag_answer",
            created_at=row.get("created_at"),
            updated_at=row.get("created_at"),
            metadata={"mode": row.get("mode"), "limitations": row.get("limitations") or []},
        )
        for row in rows
        if clean(row.get("answer") or row.get("question"))
    ]


def _agent_memory_items(conn: sqlite3.Connection, project_id: str, retrieval_scope: str) -> list[dict[str, Any]]:
    if not table_exists(conn, "agent_memory_entries"):
        return []
    where_sql, params = _project_filter(conn, project_id, retrieval_scope)
    rows = rows_to_dicts(
        conn.execute(
            f"SELECT * FROM agent_memory_entries WHERE {where_sql} AND memory_scope='project' AND COALESCE(status,'active')='active'",
            params,
        ).fetchall()
    )
    return [
        _base_item(
            source_type="agent_memory",
            source_id=row.get("id"),
            project_id=row.get("project_id"),
            title=row.get("title") or row.get("memory_type") or "Project memory",
            text=" ".join([clean(row.get("title")), clean(row.get("content"))]),
            source_db="research_group_os.sqlite",
            source_table="agent_memory_entries",
            source_provider=row.get("source_type"),
            evidence_level=row.get("trust_level"),
            evidence_role="agent_memory",
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            metadata={"memory_type": row.get("memory_type"), "trust_level": row.get("trust_level")},
        )
        for row in rows
        if clean(row.get("title") or row.get("content"))
    ]


def _task_items(conn: sqlite3.Connection, project_id: str, retrieval_scope: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for table, title_fields, text_fields in [
        ("skill_runs", ["skill_name", "skill_id"], ["status", "logs", "output_payload"]),
        ("execution_memory", ["task_title", "skill_id"], ["status", "error_message", "reusable_lesson"]),
        ("literature_search_tasks", ["query", "provider"], ["status", "notes"]),
    ]:
        if not table_exists(conn, table):
            continue
        where_sql, params = _project_filter(conn, project_id, retrieval_scope)
        for row in rows_to_dicts(conn.execute(f'SELECT * FROM "{table}" WHERE {where_sql}', params).fetchall()):
            title = next((clean(row.get(field)) for field in title_fields if clean(row.get(field))), table)
            text = " ".join(clean(row.get(field)) for field in text_fields if clean(row.get(field)))
            if not text and title:
                text = title
            if not text:
                continue
            items.append(
                _base_item(
                    source_type="task_status",
                    source_id=row.get("id") or row.get("task_id"),
                    project_id=row.get("project_id"),
                    title=title,
                    text=text,
                    source_db="research_group_os.sqlite",
                    source_table=table,
                    evidence_role="task_status",
                    created_at=row.get("created_at"),
                    updated_at=row.get("updated_at"),
                    metadata={"status": row.get("status"), "skill_id": row.get("skill_id")},
                )
            )
    return items


def _lab_items(agent_root: Path, labels: set[str], retrieval_scope: str) -> list[dict[str, Any]]:
    conn = connect_existing(_lab_db(agent_root))
    if conn is None:
        return []
    try:
        if not table_exists(conn, "document_chunks"):
            return []
        has_documents = table_exists(conn, "documents")
        if has_documents and retrieval_scope != "cross_project" and labels:
            placeholders = ",".join("?" for _ in labels)
            rows = rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT c.*, d.project_name, d.source_path
                    FROM document_chunks c
                    LEFT JOIN documents d ON d.file_id=c.file_id
                    WHERE d.project_name IN ({placeholders})
                    """,
                    sorted(labels),
                ).fetchall()
            )
        elif has_documents:
            rows = rows_to_dicts(
                conn.execute(
                    """
                    SELECT c.*, d.project_name, d.source_path
                    FROM document_chunks c
                    LEFT JOIN documents d ON d.file_id=c.file_id
                    """
                ).fetchall()
            )
        else:
            if retrieval_scope != "cross_project":
                return []
            rows = rows_to_dicts(conn.execute("SELECT * FROM document_chunks").fetchall())
    finally:
        conn.close()
    items: list[dict[str, Any]] = []
    for row in rows:
        text = clean(row.get("chunk_text"))
        if not text:
            continue
        source_type = "browser_learning" if _is_browser_learning("", row.get("source_type"), "", text) else "agent_memory"
        items.append(
            _base_item(
                source_type=source_type,
                source_id=row.get("id"),
                project_id=clean(row.get("project_name")),
                title=row.get("file_name") or "Lab RAG document",
                text=text,
                source_db="lab_agent_mvp.sqlite",
                source_table="document_chunks",
                source_provider=row.get("source_type"),
                evidence_role="browser_learning" if source_type == "browser_learning" else "lab_document_chunk",
                created_at=row.get("created_at"),
                updated_at=row.get("created_at"),
                metadata={"file_name": row.get("file_name"), "page_number": (row.get("metadata") or {}).get("page_number") if isinstance(row.get("metadata"), dict) else None},
            )
        )
    return items


def _brain_items(project_id: str, query: str, limit: int) -> list[dict[str, Any]]:
    try:
        from backend.researchos.brain.hybrid_retrieval import hybrid_search
    except Exception:
        return []
    try:
        results = hybrid_search(query, project_id=project_id, top_k=max(limit, 10))
    except Exception:
        return []
    items: list[dict[str, Any]] = []
    for row in results:
        text = clean(row.get("compiled_truth"))
        if not text:
            continue
        items.append(
            _base_item(
                source_type="brain_note",
                source_id=row.get("page_slug") or row.get("source_id"),
                project_id=row.get("project_id") or project_id,
                title=row.get("title") or row.get("page_slug") or "Brain note",
                text=text,
                source_db="backend/researchos/brain",
                source_table="brain_pages",
                source_provider=row.get("evidence_type"),
                evidence_level=row.get("confidence"),
                evidence_role="brain_note",
                metadata={"page_slug": row.get("page_slug"), "confidence": row.get("confidence"), "hybrid_score": row.get("score")},
            )
        )
    return items


def _score_item(item: dict[str, Any], query: str, qvec: list[float], qtokens: set[str]) -> dict[str, Any] | None:
    text = " ".join([clean(item.get("title")), clean(item.get("text"))])
    if not text:
        return None
    tokens = set(tokens_for_vector(text))
    overlap = len(qtokens.intersection(tokens))
    keyword_score = overlap / max(1, len(qtokens))
    vector_score = cosine(qvec, _safe_vector((item.get("metadata") or {}).get("embedding_json"), text))
    exact_boost = 0.08 if clean(query).lower() and clean(query).lower() in text.lower() else 0.0
    source_boost = {
        "reference_chunk": 0.16,
        "kb_entry": 0.10,
        "brain_note": 0.06,
        "agent_memory": 0.04,
        "task_status": 0.03,
        "browser_learning": 0.0,
    }.get(clean(item.get("source_type")), 0.0)
    score = keyword_score * 0.58 + vector_score * 0.34 + exact_boost + source_boost
    if overlap == 0 and exact_boost <= 0:
        return None
    if clean(item.get("source_type")) == "agent_memory" and clean((item.get("metadata") or {}).get("memory_type")) == "weekly_digest":
        score += 0.12
    scored = dict(item)
    scored["score"] = round(score, 6)
    scored["keyword_score"] = round(keyword_score, 6)
    scored["embedding_score"] = round(vector_score, 6)
    return scored


def _assign_citations(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citation_ids: dict[str, str] = {}
    for item in results:
        key = clean(item.get("citation_key")) or _citation_key(item)
        if key not in citation_ids:
            citation_ids[key] = f"[{len(citation_ids) + 1}]"
        item["citation_key"] = key
        item["citation_id"] = citation_ids[key]
    return results


def _citation_objects(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    citations: list[dict[str, Any]] = []
    for item in results:
        key = clean(item.get("citation_key"))
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            {
                "citation_id": item.get("citation_id"),
                "source_type": item.get("source_type"),
                "reference_id": item.get("reference_id"),
                "chunk_id": item.get("chunk_id"),
                "display_title": item.get("title"),
                "excerpt": item.get("excerpt"),
                "can_support_peer_reviewed_evidence": item.get("can_support_peer_reviewed_evidence"),
                "evidence_role": item.get("evidence_role"),
            }
        )
    return citations


def _allowed_source_types_for_mode(mode: str) -> set[str]:
    mode = clean(mode) or "literature_only"
    if mode == "literature_only":
        return {"reference_chunk", "kb_entry", "browser_learning"}
    if mode == "project_memory_only":
        return {"agent_memory", "brain_note"}
    if mode == "weekly_digest":
        return {"reference_chunk", "kb_entry", "browser_learning", "brain_note", "agent_memory"}
    if mode == "experiment_logs_only":
        return {"task_status", "agent_memory", "brain_note"}
    return set(NORMALIZED_SOURCE_TYPES)


def unified_rag_query(agent_root: Path | str, payload: dict[str, Any]) -> dict[str, Any]:
    agent_root = Path(agent_root)
    project_id = clean(payload.get("project_id"))
    question = clean(payload.get("question") or payload.get("query") or payload.get("user_message"))
    mode = clean(payload.get("mode")) or "literature_only"
    if not project_id:
        raise ValueError("project_id is required")
    if not question:
        raise ValueError("question is required")
    limit = max(int(payload.get("limit") or 8), 1)
    retrieval_scope = clean(payload.get("retrieval_scope") or payload.get("scope"))
    if payload.get("cross_project") is True:
        retrieval_scope = "cross_project"
    if retrieval_scope != "cross_project":
        retrieval_scope = "current_project"

    main_conn = connect_existing(_main_db(agent_root))
    labels: set[str] = {project_id}
    candidates: list[dict[str, Any]] = []
    if main_conn is not None:
        try:
            labels = _project_labels(main_conn, project_id)
            candidates.extend(_reference_chunk_items(main_conn, project_id, retrieval_scope))
            candidates.extend(_kb_items(main_conn, project_id, retrieval_scope))
            candidates.extend(_rag_query_items(main_conn, project_id, retrieval_scope))
            candidates.extend(_agent_memory_items(main_conn, project_id, retrieval_scope))
            candidates.extend(_task_items(main_conn, project_id, retrieval_scope))
        finally:
            main_conn.close()
    candidates.extend(_lab_items(agent_root, labels, retrieval_scope))
    candidates.extend(_brain_items(project_id, question, limit))
    allowed_source_types = _allowed_source_types_for_mode(mode)
    candidates = [item for item in candidates if clean(item.get("source_type")) in allowed_source_types]

    expanded_query = expanded_query_text(question)
    qvec = embed(expanded_query)
    qtokens = set(tokens_for_vector(expanded_query))
    scored = [item for item in (_score_item(candidate, question, qvec, qtokens) for candidate in candidates) if item]
    scored.sort(
        key=lambda item: (
            -float(item.get("score") or 0),
            clean(item.get("source_type")),
            clean(item.get("updated_at")),
            clean(item.get("source_id")),
        )
    )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in scored:
        key = (clean(item.get("source_type")), clean(item.get("source_id")), clean(item.get("excerpt"))[:80])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    results = _assign_citations(deduped)
    return {
        "retrieval_service": "unified_rag_query",
        "project_id": project_id,
        "question": question,
        "mode": mode,
        "retrieval_scope": retrieval_scope,
        "results": results,
        "citations": _citation_objects(results),
        "source_breakdown": {source_type: sum(1 for item in results if item.get("source_type") == source_type) for source_type in sorted({item.get("source_type") for item in results})},
        "retrieval_steps": ["keyword_or_fts_prefilter", "embedding_or_hybrid_recall", "rerank", "source_type_normalization", "citation_normalization"],
    }
