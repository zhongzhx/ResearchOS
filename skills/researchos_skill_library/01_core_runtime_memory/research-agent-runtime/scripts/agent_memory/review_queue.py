from __future__ import annotations

from pathlib import Path
from typing import Any

from .database import connect
from .models import clean, json_dumps, now, row_to_dict, stable_id


def enqueue_review(agent_root: Path, data: dict[str, Any]) -> dict[str, Any]:
    candidate = data.get("candidate") or data.get("candidate_json") or {}
    confidence = float(data.get("confidence") if data.get("confidence") is not None else candidate.get("confidence", 0.4) if isinstance(candidate, dict) else 0.4)
    row = {
        "id": clean(data.get("id")) or stable_id(data.get("user_id", "local_user"), data.get("group_id", ""), json_dumps(candidate), now()),
        "user_id": clean(data.get("user_id")) or "local_user",
        "group_id": clean(data.get("group_id")),
        "candidate_json": json_dumps(candidate),
        "reason": clean(data.get("reason")) or "low confidence or important memory candidate",
        "confidence": confidence,
        "status": clean(data.get("status")) or "pending",
        "created_at": now(),
        "updated_at": now(),
    }
    conn = connect(agent_root)
    conn.execute(
        """
        INSERT INTO memory_review_queue(id, user_id, group_id, candidate_json, reason, confidence, status, created_at, updated_at)
        VALUES (:id, :user_id, :group_id, :candidate_json, :reason, :confidence, :status, :created_at, :updated_at)
        """,
        row,
    )
    conn.commit()
    saved = conn.execute("SELECT * FROM memory_review_queue WHERE id=?", (row["id"],)).fetchone()
    conn.close()
    return row_to_dict(saved)


def list_review_queue(agent_root: Path, user_id: str = "", group_id: str = "", status: str = "pending") -> list[dict[str, Any]]:
    conn = connect(agent_root)
    rows = conn.execute(
        """
        SELECT * FROM memory_review_queue
        WHERE (?='' OR user_id=?) AND (?='' OR group_id=?) AND (?='' OR status=?)
        ORDER BY created_at DESC
        """,
        (user_id, user_id, group_id, group_id, status, status),
    ).fetchall()
    conn.close()
    return [row_to_dict(row) for row in rows]


def update_review_status(agent_root: Path, review_id: str, status: str) -> dict[str, Any]:
    conn = connect(agent_root)
    conn.execute("UPDATE memory_review_queue SET status=?, updated_at=? WHERE id=?", (status, now(), review_id))
    row = conn.execute("SELECT * FROM memory_review_queue WHERE id=?", (review_id,)).fetchone()
    if not row:
        conn.close()
        raise KeyError("review item not found")
    conn.commit()
    conn.close()
    return row_to_dict(row)
