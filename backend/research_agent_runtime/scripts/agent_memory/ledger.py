from __future__ import annotations

from pathlib import Path
from typing import Any

from .database import connect
from .embeddings import store_embedding
from .models import MEMORY_TYPES, as_list, clean, json_dumps, now, row_to_dict, stable_id


JSON_FIELDS = {
    "structured_content_json",
    "entities_json",
    "tags_json",
    "related_file_ids_json",
    "related_sample_ids_json",
    "related_protocol_ids_json",
    "related_memory_ids_json",
    "supersedes_json",
}


def _json_value(event: dict[str, Any], field: str, default: Any) -> str:
    plain = field[:-5] if field.endswith("_json") else field
    if field in event:
        value = event[field]
    else:
        value = event.get(plain, default)
    if field in {
        "tags_json",
        "related_file_ids_json",
        "related_sample_ids_json",
        "related_protocol_ids_json",
        "related_memory_ids_json",
        "supersedes_json",
    }:
        value = as_list(value)
    return json_dumps(value if value is not None else default)


def _memory_text(event: dict[str, Any]) -> str:
    return "\n".join(
        [
            clean(event.get("memory_type")),
            clean(event.get("subject")),
            clean(event.get("content")),
            json_dumps(event.get("structured_content") or event.get("structured_content_json") or {}),
            " ".join(map(str, as_list(event.get("tags")))),
        ]
    )


def _existing_duplicate(conn: Any, row: dict[str, Any]) -> dict[str, Any] | None:
    existing = conn.execute(
        """
        SELECT * FROM memory_ledger
        WHERE user_id=? AND COALESCE(group_id,'')=COALESCE(?, '')
          AND COALESCE(project_id,'')=COALESCE(?, '')
          AND COALESCE(experiment_id,'')=COALESCE(?, '')
          AND memory_type=? AND subject=? AND content=?
          AND status NOT IN ('archived', 'deleted', 'superseded')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (
            row["user_id"],
            row["group_id"],
            row["project_id"],
            row["experiment_id"],
            row["memory_type"],
            row["subject"],
            row["content"],
        ),
    ).fetchone()
    return row_to_dict(existing) if existing else None


def create_memory(agent_root: Path, event: dict[str, Any]) -> dict[str, Any]:
    project_id = clean(event.get("project_id"))
    if not project_id:
        raise ValueError("project_id is required")
    memory_type = clean(event.get("memory_type")) or "project_memory"
    if memory_type not in MEMORY_TYPES:
        raise ValueError(f"unsupported memory_type: {memory_type}")

    timestamp = clean(event.get("timestamp")) or now()
    row = {
        "id": clean(event.get("id")) or stable_id(
            event.get("user_id", "local_user"),
            event.get("group_id", ""),
            event.get("project_id", ""),
            event.get("experiment_id", ""),
            memory_type,
            event.get("subject", ""),
            event.get("content", ""),
            timestamp,
        ),
        "user_id": clean(event.get("user_id")) or "local_user",
        "group_id": clean(event.get("group_id")),
        "project_id": project_id,
        "experiment_id": clean(event.get("experiment_id")),
        "timestamp": timestamp,
        "source_type": clean(event.get("source_type")) or "manual",
        "source_id": clean(event.get("source_id")),
        "memory_type": memory_type,
        "subject": clean(event.get("subject")) or memory_type,
        "content": clean(event.get("content")) or json_dumps(event.get("structured_content") or {}),
        "structured_content_json": _json_value(event, "structured_content_json", {}),
        "entities_json": _json_value(event, "entities_json", {}),
        "tags_json": _json_value(event, "tags_json", []),
        "related_file_ids_json": _json_value(event, "related_file_ids_json", []),
        "related_sample_ids_json": _json_value(event, "related_sample_ids_json", []),
        "related_protocol_ids_json": _json_value(event, "related_protocol_ids_json", []),
        "related_memory_ids_json": _json_value(event, "related_memory_ids_json", []),
        "confidence": float(event.get("confidence") if event.get("confidence") is not None else 0.75),
        "evidence_strength": clean(event.get("evidence_strength")) or "raw_observation",
        "stability": clean(event.get("stability")) or "working",
        "valid_from": clean(event.get("valid_from")) or timestamp,
        "valid_until": clean(event.get("valid_until")),
        "status": clean(event.get("status")) or "active",
        "supersedes_json": _json_value(event, "supersedes_json", []),
        "superseded_by": clean(event.get("superseded_by")),
        "privacy_level": clean(event.get("privacy_level")) or "private",
        "embedding_id": "",
        "created_at": now(),
        "updated_at": now(),
    }

    conn = connect(agent_root)
    duplicate = _existing_duplicate(conn, row)
    if duplicate and not event.get("allow_duplicate"):
        conn.close()
        duplicate["duplicate_ignored"] = True
        return duplicate

    row["embedding_id"] = store_embedding(conn, row["id"], _memory_text(event) or row["content"])
    conn.execute(
        """
        INSERT INTO memory_ledger(
            id, user_id, group_id, project_id, experiment_id, timestamp, source_type, source_id,
            memory_type, subject, content, structured_content_json, entities_json, tags_json,
            related_file_ids_json, related_sample_ids_json, related_protocol_ids_json, related_memory_ids_json,
            confidence, evidence_strength, stability, valid_from, valid_until, status, supersedes_json,
            superseded_by, privacy_level, embedding_id, created_at, updated_at
        )
        VALUES (
            :id, :user_id, :group_id, :project_id, :experiment_id, :timestamp, :source_type, :source_id,
            :memory_type, :subject, :content, :structured_content_json, :entities_json, :tags_json,
            :related_file_ids_json, :related_sample_ids_json, :related_protocol_ids_json, :related_memory_ids_json,
            :confidence, :evidence_strength, :stability, :valid_from, :valid_until, :status, :supersedes_json,
            :superseded_by, :privacy_level, :embedding_id, :created_at, :updated_at
        )
        """,
        row,
    )
    for old_id in as_list(event.get("supersedes") or event.get("supersedes_json")):
        conn.execute(
            "UPDATE memory_ledger SET status='superseded', superseded_by=?, updated_at=? WHERE id=?",
            (row["id"], now(), str(old_id)),
        )
    conn.commit()
    saved = conn.execute("SELECT * FROM memory_ledger WHERE id=?", (row["id"],)).fetchone()
    conn.close()
    return row_to_dict(saved)


def update_memory(agent_root: Path, memory_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    project_id = clean(patch.get("project_id"))
    if not project_id:
        raise ValueError("project_id is required")
    allowed = {
        "subject",
        "content",
        "structured_content_json",
        "entities_json",
        "tags_json",
        "related_file_ids_json",
        "related_sample_ids_json",
        "related_protocol_ids_json",
        "related_memory_ids_json",
        "confidence",
        "evidence_strength",
        "stability",
        "valid_from",
        "valid_until",
        "status",
        "privacy_level",
    }
    assignments = []
    values: list[Any] = []
    for key, value in patch.items():
        column = key if key.endswith("_json") else f"{key}_json" if f"{key}_json" in allowed else key
        if column not in allowed:
            continue
        assignments.append(f"{column}=?")
        values.append(json_dumps(value) if column in JSON_FIELDS else value)
    if not assignments:
        raise ValueError("no supported fields to update")
    assignments.append("updated_at=?")
    values.extend([now(), memory_id, project_id])
    conn = connect(agent_root)
    conn.execute(f"UPDATE memory_ledger SET {', '.join(assignments)} WHERE id=? AND project_id=?", values)
    row = conn.execute("SELECT * FROM memory_ledger WHERE id=? AND project_id=?", (memory_id, project_id)).fetchone()
    if not row:
        conn.close()
        raise KeyError("memory not found")
    conn.commit()
    conn.close()
    return row_to_dict(row)


def get_memory(agent_root: Path, memory_id: str) -> dict[str, Any] | None:
    conn = connect(agent_root)
    row = conn.execute("SELECT * FROM memory_ledger WHERE id=?", (memory_id,)).fetchone()
    conn.close()
    return row_to_dict(row) if row else None


def archive_memory(agent_root: Path, memory_id: str, project_id: str) -> dict[str, Any]:
    return update_memory(agent_root, memory_id, {"project_id": project_id, "status": "archived"})


def delete_memory(agent_root: Path, memory_id: str, project_id: str) -> dict[str, Any]:
    project_id = clean(project_id)
    if not project_id:
        raise ValueError("project_id is required")
    conn = connect(agent_root)
    row = conn.execute("SELECT id FROM memory_ledger WHERE id=? AND project_id=?", (memory_id, project_id)).fetchone()
    if not row:
        conn.close()
        raise KeyError("memory not found")
    conn.execute("DELETE FROM memory_embeddings WHERE memory_id=?", (memory_id,))
    cur = conn.execute("DELETE FROM memory_ledger WHERE id=? AND project_id=?", (memory_id, project_id))
    conn.commit()
    conn.close()
    return {"deleted": cur.rowcount > 0, "id": memory_id}
