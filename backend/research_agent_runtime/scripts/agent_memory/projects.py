from __future__ import annotations

from pathlib import Path
from typing import Any

from .database import connect
from .ledger import create_memory
from .models import as_list, clean, json_dumps, now, row_to_dict, stable_id


def create_group(agent_root: Path, data: dict[str, Any]) -> dict[str, Any]:
    name = clean(data.get("name")) or clean(data.get("group_name")) or "local_research_group"
    group_id = clean(data.get("id")) or stable_id(name)
    row = {
        "id": group_id,
        "name": name,
        "description": clean(data.get("description")),
        "created_at": now(),
        "updated_at": now(),
    }
    conn = connect(agent_root)
    conn.execute(
        """
        INSERT INTO research_groups(id, name, description, created_at, updated_at)
        VALUES (:id, :name, :description, :created_at, :updated_at)
        ON CONFLICT(id) DO UPDATE SET name=excluded.name, description=excluded.description, updated_at=excluded.updated_at
        """,
        row,
    )
    conn.commit()
    conn.close()
    return row


def create_project(agent_root: Path, data: dict[str, Any]) -> dict[str, Any]:
    title = clean(data.get("title")) or clean(data.get("project_title"))
    if not title:
        raise ValueError("project title is required")
    group_id = clean(data.get("group_id"))
    project_id = clean(data.get("id")) or stable_id(group_id, title)
    row = {
        "id": project_id,
        "group_id": group_id,
        "title": title,
        "short_name": clean(data.get("short_name")) or title[:40],
        "research_question": clean(data.get("research_question")),
        "hypothesis": clean(data.get("hypothesis")),
        "status": clean(data.get("status")) or "active",
        "stage": clean(data.get("stage")) or "planning",
        "target_output": clean(data.get("target_output")),
        "target_journals_json": json_dumps(as_list(data.get("target_journals"))),
        "created_at": now(),
        "updated_at": now(),
    }
    conn = connect(agent_root)
    conn.execute(
        """
        INSERT INTO projects(
            id, group_id, title, short_name, research_question, hypothesis, status, stage,
            target_output, target_journals_json, created_at, updated_at
        )
        VALUES (
            :id, :group_id, :title, :short_name, :research_question, :hypothesis, :status, :stage,
            :target_output, :target_journals_json, :created_at, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            short_name=excluded.short_name,
            research_question=excluded.research_question,
            hypothesis=excluded.hypothesis,
            status=excluded.status,
            stage=excluded.stage,
            target_output=excluded.target_output,
            target_journals_json=excluded.target_journals_json,
            updated_at=excluded.updated_at
        """,
        row,
    )
    conn.commit()
    saved = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    project = row_to_dict(saved)
    create_memory(
        agent_root,
        {
            "user_id": data.get("user_id", "local_user"),
            "group_id": group_id,
            "project_id": project_id,
            "memory_type": "project_memory",
            "subject": title,
            "content": f"Project created or updated: {title}. Question: {row['research_question']}. Hypothesis: {row['hypothesis']}.",
            "structured_content": project,
            "tags": ["project"],
            "confidence": data.get("confidence", 0.9),
        },
    )
    return project


def update_project(agent_root: Path, project_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "group_id",
        "title",
        "short_name",
        "research_question",
        "hypothesis",
        "status",
        "stage",
        "target_output",
        "target_journals_json",
    }
    assignments = []
    values: list[Any] = []
    for key, value in patch.items():
        column = key if key in allowed else f"{key}_json" if f"{key}_json" in allowed else key
        if column not in allowed:
            continue
        assignments.append(f"{column}=?")
        values.append(json_dumps(as_list(value)) if column.endswith("_json") else clean(value))
    if not assignments:
        raise ValueError("no supported project fields to update")
    assignments.append("updated_at=?")
    values.extend([now(), project_id])
    conn = connect(agent_root)
    conn.execute(f"UPDATE projects SET {', '.join(assignments)} WHERE id=?", values)
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        conn.close()
        raise KeyError("project not found")
    conn.commit()
    conn.close()
    project = row_to_dict(row)
    create_memory(
        agent_root,
        {
            "user_id": patch.get("user_id", "local_user"),
            "group_id": project.get("group_id"),
            "project_id": project_id,
            "memory_type": "project_memory",
            "subject": project.get("title"),
            "content": f"Project updated: {', '.join(assignments)}.",
            "structured_content": {"patch": patch, "project": project},
            "tags": ["project_update"],
            "confidence": patch.get("confidence", 0.85),
        },
    )
    return project


def get_project(agent_root: Path, project_id: str) -> dict[str, Any] | None:
    conn = connect(agent_root)
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    return row_to_dict(row) if row else None
