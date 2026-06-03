from __future__ import annotations

from pathlib import Path
from typing import Any

from .database import connect
from .ledger import create_memory
from .models import as_dict, clean, json_dumps, now, row_to_dict, stable_id


def create_sample(agent_root: Path, data: dict[str, Any]) -> dict[str, Any]:
    project_id = clean(data.get("project_id"))
    if not project_id:
        raise ValueError("project_id is required")
    sample_code = clean(data.get("sample_code") or data.get("id") or data.get("sample_id"))
    if not sample_code:
        raise ValueError("sample_code is required")
    sample_id = clean(data.get("id")) or stable_id(data.get("group_id", ""), data.get("project_id", ""), sample_code)
    row = {
        "id": sample_id,
        "group_id": clean(data.get("group_id")),
        "project_id": project_id,
        "sample_code": sample_code,
        "sample_type": clean(data.get("sample_type")),
        "name": clean(data.get("name")) or sample_code,
        "source": clean(data.get("source")),
        "batch": clean(data.get("batch")),
        "preparation_method": clean(data.get("preparation_method")),
        "storage_condition": clean(data.get("storage_condition")),
        "current_status": clean(data.get("current_status")) or "available",
        "metadata_json": json_dumps(as_dict(data.get("metadata"))),
        "created_at": now(),
        "updated_at": now(),
    }
    conn = connect(agent_root)
    conn.execute(
        """
        INSERT INTO samples(
            id, group_id, project_id, sample_code, sample_type, name, source, batch,
            preparation_method, storage_condition, current_status, metadata_json, created_at, updated_at
        )
        VALUES (
            :id, :group_id, :project_id, :sample_code, :sample_type, :name, :source, :batch,
            :preparation_method, :storage_condition, :current_status, :metadata_json, :created_at, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            sample_type=excluded.sample_type,
            name=excluded.name,
            source=excluded.source,
            batch=excluded.batch,
            preparation_method=excluded.preparation_method,
            storage_condition=excluded.storage_condition,
            current_status=excluded.current_status,
            metadata_json=excluded.metadata_json,
            updated_at=excluded.updated_at
        """,
        row,
    )
    conn.commit()
    saved = conn.execute("SELECT * FROM samples WHERE id=?", (sample_id,)).fetchone()
    conn.close()
    sample = row_to_dict(saved)
    create_memory(
        agent_root,
        {
            "user_id": data.get("user_id", "local_user"),
            "group_id": row["group_id"],
            "project_id": row["project_id"],
            "memory_type": "sample_memory",
            "subject": sample_code,
            "content": f"Sample {sample_code}: {row['sample_type']} batch {row['batch']} status {row['current_status']}.",
            "structured_content": sample,
            "entities": {"sample_id": sample_code, "batch": row["batch"]},
            "tags": ["sample", row["sample_type"], row["current_status"]],
            "related_sample_ids": [sample_id, sample_code],
            "confidence": data.get("confidence", 0.85),
        },
    )
    return sample


def update_sample(agent_root: Path, sample_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    project_id = clean(patch.get("project_id"))
    if not project_id:
        raise ValueError("project_id is required")
    allowed = {
        "group_id",
        "sample_code",
        "sample_type",
        "name",
        "source",
        "batch",
        "preparation_method",
        "storage_condition",
        "current_status",
        "metadata_json",
    }
    assignments = []
    values: list[Any] = []
    for key, value in patch.items():
        column = key if key in allowed else f"{key}_json" if f"{key}_json" in allowed else key
        if column not in allowed:
            continue
        assignments.append(f"{column}=?")
        values.append(json_dumps(value) if column.endswith("_json") else clean(value))
    if not assignments:
        raise ValueError("no supported sample fields to update")
    assignments.append("updated_at=?")
    values.extend([now(), sample_id, project_id])
    conn = connect(agent_root)
    conn.execute(f"UPDATE samples SET {', '.join(assignments)} WHERE id=? AND project_id=?", values)
    row = conn.execute("SELECT * FROM samples WHERE id=? AND project_id=?", (sample_id, project_id)).fetchone()
    if not row:
        conn.close()
        raise KeyError("sample not found")
    conn.commit()
    conn.close()
    return row_to_dict(row)
