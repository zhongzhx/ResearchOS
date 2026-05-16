from __future__ import annotations

from pathlib import Path
from typing import Any

from .database import connect
from .ledger import create_memory
from .models import as_list, clean, json_dumps, now, row_to_dict, stable_id


def create_experiment(agent_root: Path, data: dict[str, Any]) -> dict[str, Any]:
    project_id = clean(data.get("project_id"))
    title = clean(data.get("title")) or clean(data.get("experiment_title")) or "Untitled experiment"
    experiment_id = clean(data.get("id")) or stable_id(project_id, title, data.get("date", ""), data.get("operator", ""))
    row = {
        "id": experiment_id,
        "project_id": project_id,
        "title": title,
        "experiment_type": clean(data.get("experiment_type")),
        "date": clean(data.get("date")),
        "operator": clean(data.get("operator")),
        "purpose": clean(data.get("purpose")),
        "design_summary": clean(data.get("design_summary") or data.get("design")),
        "groups_json": json_dumps(data.get("groups") or {}),
        "sample_ids_json": json_dumps(as_list(data.get("sample_ids") or data.get("samples"))),
        "protocol_id": clean(data.get("protocol_id")),
        "raw_data_file_ids_json": json_dumps(as_list(data.get("raw_data_file_ids"))),
        "processed_data_file_ids_json": json_dumps(as_list(data.get("processed_data_file_ids"))),
        "result_summary": clean(data.get("result_summary") or data.get("results")),
        "conclusion": clean(data.get("conclusion")),
        "status": clean(data.get("status")) or "completed",
        "created_at": now(),
        "updated_at": now(),
    }
    conn = connect(agent_root)
    conn.execute(
        """
        INSERT INTO experiments(
            id, project_id, title, experiment_type, date, operator, purpose, design_summary, groups_json,
            sample_ids_json, protocol_id, raw_data_file_ids_json, processed_data_file_ids_json,
            result_summary, conclusion, status, created_at, updated_at
        )
        VALUES (
            :id, :project_id, :title, :experiment_type, :date, :operator, :purpose, :design_summary, :groups_json,
            :sample_ids_json, :protocol_id, :raw_data_file_ids_json, :processed_data_file_ids_json,
            :result_summary, :conclusion, :status, :created_at, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            experiment_type=excluded.experiment_type,
            date=excluded.date,
            operator=excluded.operator,
            purpose=excluded.purpose,
            design_summary=excluded.design_summary,
            groups_json=excluded.groups_json,
            sample_ids_json=excluded.sample_ids_json,
            protocol_id=excluded.protocol_id,
            raw_data_file_ids_json=excluded.raw_data_file_ids_json,
            processed_data_file_ids_json=excluded.processed_data_file_ids_json,
            result_summary=excluded.result_summary,
            conclusion=excluded.conclusion,
            status=excluded.status,
            updated_at=excluded.updated_at
        """,
        row,
    )
    conn.commit()
    saved = conn.execute("SELECT * FROM experiments WHERE id=?", (experiment_id,)).fetchone()
    conn.close()
    experiment = row_to_dict(saved)
    memory_type = "failure_memory" if row["status"] in {"failed", "negative", "invalidated"} else "experiment_memory"
    create_memory(
        agent_root,
        {
            "user_id": data.get("user_id", "local_user"),
            "group_id": data.get("group_id", ""),
            "project_id": project_id,
            "experiment_id": experiment_id,
            "memory_type": memory_type,
            "subject": title,
            "content": f"Experiment: {title}. Type: {row['experiment_type']}. Results: {row['result_summary']}. Conclusion: {row['conclusion']}.",
            "structured_content": experiment,
            "entities": {
                "sample_ids": experiment.get("sample_ids", []),
                "protocol_id": row["protocol_id"],
                "experiment_type": row["experiment_type"],
            },
            "tags": as_list(data.get("tags")) + ["experiment"],
            "related_file_ids": as_list(data.get("raw_data_file_ids")) + as_list(data.get("processed_data_file_ids")),
            "related_sample_ids": as_list(data.get("sample_ids") or data.get("samples")),
            "related_protocol_ids": [row["protocol_id"]] if row["protocol_id"] else [],
            "confidence": data.get("confidence", 0.82),
            "evidence_strength": data.get("evidence_strength", "raw_observation"),
        },
    )
    return experiment


def update_experiment(agent_root: Path, experiment_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "project_id",
        "title",
        "experiment_type",
        "date",
        "operator",
        "purpose",
        "design_summary",
        "groups_json",
        "sample_ids_json",
        "protocol_id",
        "raw_data_file_ids_json",
        "processed_data_file_ids_json",
        "result_summary",
        "conclusion",
        "status",
    }
    assignments = []
    values: list[Any] = []
    for key, value in patch.items():
        column = key if key in allowed else f"{key}_json" if f"{key}_json" in allowed else key
        if column not in allowed:
            continue
        assignments.append(f"{column}=?")
        if column.endswith("_json"):
            values.append(json_dumps(value if not column.endswith("ids_json") else as_list(value)))
        else:
            values.append(clean(value))
    if not assignments:
        raise ValueError("no supported experiment fields to update")
    assignments.append("updated_at=?")
    values.extend([now(), experiment_id])
    conn = connect(agent_root)
    conn.execute(f"UPDATE experiments SET {', '.join(assignments)} WHERE id=?", values)
    row = conn.execute("SELECT * FROM experiments WHERE id=?", (experiment_id,)).fetchone()
    if not row:
        conn.close()
        raise KeyError("experiment not found")
    conn.commit()
    conn.close()
    experiment = row_to_dict(row)
    create_memory(
        agent_root,
        {
            "user_id": patch.get("user_id", "local_user"),
            "project_id": experiment.get("project_id"),
            "experiment_id": experiment_id,
            "memory_type": "experiment_memory",
            "subject": experiment.get("title"),
            "content": f"Experiment updated: {experiment.get('title')}.",
            "structured_content": {"patch": patch, "experiment": experiment},
            "tags": ["experiment_update"],
            "confidence": patch.get("confidence", 0.8),
        },
    )
    return experiment


def list_project_experiments(agent_root: Path, project_id: str, status: str = "") -> list[dict[str, Any]]:
    conn = connect(agent_root)
    rows = conn.execute(
        "SELECT * FROM experiments WHERE project_id=? AND (?='' OR status=?) ORDER BY COALESCE(date, created_at) DESC",
        (project_id, status, status),
    ).fetchall()
    conn.close()
    return [row_to_dict(row) for row in rows]
