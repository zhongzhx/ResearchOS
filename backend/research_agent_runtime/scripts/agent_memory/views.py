from __future__ import annotations

from pathlib import Path
from typing import Any

from .database import connect
from .models import clean, json_dumps, now, row_to_dict, stable_id


def upsert_memory_view(
    agent_root: Path,
    *,
    user_id: str = "local_user",
    group_id: str = "",
    project_id: str = "",
    view_type: str,
    subject: str,
    summary: str,
    structured_summary: dict[str, Any],
    evidence_memory_ids: list[str],
    confidence: float = 0.75,
) -> dict[str, Any]:
    view_id = stable_id(user_id, group_id, project_id, view_type, subject)
    row = {
        "id": view_id,
        "user_id": clean(user_id) or "local_user",
        "group_id": clean(group_id),
        "project_id": clean(project_id),
        "view_type": clean(view_type),
        "subject": clean(subject),
        "summary": clean(summary),
        "structured_summary_json": json_dumps(structured_summary),
        "evidence_memory_ids_json": json_dumps(evidence_memory_ids),
        "confidence": confidence,
        "last_consolidated_at": now(),
        "created_at": now(),
        "updated_at": now(),
    }
    conn = connect(agent_root)
    conn.execute(
        """
        INSERT INTO memory_views(
            id, user_id, group_id, project_id, view_type, subject, summary, structured_summary_json,
            evidence_memory_ids_json, confidence, last_consolidated_at, created_at, updated_at
        )
        VALUES (
            :id, :user_id, :group_id, :project_id, :view_type, :subject, :summary, :structured_summary_json,
            :evidence_memory_ids_json, :confidence, :last_consolidated_at, :created_at, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            summary=excluded.summary,
            structured_summary_json=excluded.structured_summary_json,
            evidence_memory_ids_json=excluded.evidence_memory_ids_json,
            confidence=excluded.confidence,
            last_consolidated_at=excluded.last_consolidated_at,
            updated_at=excluded.updated_at
        """,
        row,
    )
    conn.commit()
    saved = conn.execute("SELECT * FROM memory_views WHERE id=?", (view_id,)).fetchone()
    conn.close()
    return row_to_dict(saved)


def get_current_project_view(agent_root: Path, project_id: str) -> dict[str, Any] | None:
    conn = connect(agent_root)
    row = conn.execute(
        """
        SELECT * FROM memory_views
        WHERE project_id=? AND view_type='project_current_state'
        ORDER BY last_consolidated_at DESC
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    conn.close()
    return row_to_dict(row) if row else None


def get_views(agent_root: Path, project_id: str = "", user_id: str = "", group_id: str = "") -> list[dict[str, Any]]:
    conn = connect(agent_root)
    rows = conn.execute(
        """
        SELECT * FROM memory_views
        WHERE (?='' OR project_id=?)
          AND (?='' OR user_id=?)
          AND (?='' OR group_id=?)
        ORDER BY last_consolidated_at DESC
        """,
        (project_id, project_id, user_id, user_id, group_id, group_id),
    ).fetchall()
    conn.close()
    return [row_to_dict(row) for row in rows]
