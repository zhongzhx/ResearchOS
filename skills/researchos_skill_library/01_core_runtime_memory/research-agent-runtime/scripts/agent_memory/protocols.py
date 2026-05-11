from __future__ import annotations

from pathlib import Path
from typing import Any

from .database import connect
from .ledger import create_memory
from .models import as_list, clean, json_dumps, now, row_to_dict, stable_id


def create_protocol(agent_root: Path, data: dict[str, Any]) -> dict[str, Any]:
    name = clean(data.get("name")) or clean(data.get("protocol_name"))
    if not name:
        raise ValueError("protocol name is required")
    version = clean(data.get("version")) or "v1"
    protocol_id = clean(data.get("id")) or stable_id(data.get("group_id", ""), name, version)
    row = {
        "id": protocol_id,
        "group_id": clean(data.get("group_id")),
        "name": name,
        "version": version,
        "purpose": clean(data.get("purpose")),
        "materials_json": json_dumps(data.get("materials") or []),
        "steps_json": json_dumps(data.get("steps") or []),
        "parameters_json": json_dumps(data.get("parameters") or {}),
        "critical_notes": clean(data.get("critical_notes")),
        "troubleshooting": clean(data.get("troubleshooting")),
        "related_experiment_types_json": json_dumps(as_list(data.get("related_experiment_types"))),
        "created_at": now(),
        "updated_at": now(),
    }
    conn = connect(agent_root)
    conn.execute(
        """
        INSERT INTO protocols(
            id, group_id, name, version, purpose, materials_json, steps_json, parameters_json,
            critical_notes, troubleshooting, related_experiment_types_json, created_at, updated_at
        )
        VALUES (
            :id, :group_id, :name, :version, :purpose, :materials_json, :steps_json, :parameters_json,
            :critical_notes, :troubleshooting, :related_experiment_types_json, :created_at, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            purpose=excluded.purpose,
            materials_json=excluded.materials_json,
            steps_json=excluded.steps_json,
            parameters_json=excluded.parameters_json,
            critical_notes=excluded.critical_notes,
            troubleshooting=excluded.troubleshooting,
            related_experiment_types_json=excluded.related_experiment_types_json,
            updated_at=excluded.updated_at
        """,
        row,
    )
    conn.commit()
    saved = conn.execute("SELECT * FROM protocols WHERE id=?", (protocol_id,)).fetchone()
    conn.close()
    protocol = row_to_dict(saved)
    create_memory(
        agent_root,
        {
            "user_id": data.get("user_id", "local_user"),
            "group_id": row["group_id"],
            "memory_type": "protocol_memory",
            "subject": f"{name} {version}",
            "content": f"Protocol {name} {version}: {row['purpose']}. Critical notes: {row['critical_notes']}.",
            "structured_content": protocol,
            "tags": ["protocol", name, version],
            "related_protocol_ids": [protocol_id],
            "confidence": data.get("confidence", 0.86),
        },
    )
    return protocol


def update_protocol(agent_root: Path, protocol_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "group_id",
        "name",
        "version",
        "purpose",
        "materials_json",
        "steps_json",
        "parameters_json",
        "critical_notes",
        "troubleshooting",
        "related_experiment_types_json",
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
        raise ValueError("no supported protocol fields to update")
    assignments.append("updated_at=?")
    values.extend([now(), protocol_id])
    conn = connect(agent_root)
    conn.execute(f"UPDATE protocols SET {', '.join(assignments)} WHERE id=?", values)
    row = conn.execute("SELECT * FROM protocols WHERE id=?", (protocol_id,)).fetchone()
    if not row:
        conn.close()
        raise KeyError("protocol not found")
    conn.commit()
    conn.close()
    return row_to_dict(row)


def latest_protocol(agent_root: Path, name: str, group_id: str = "") -> dict[str, Any] | None:
    conn = connect(agent_root)
    row = conn.execute(
        """
        SELECT * FROM protocols
        WHERE name=? AND (?='' OR group_id=?)
        ORDER BY updated_at DESC, version DESC
        LIMIT 1
        """,
        (name, group_id, group_id),
    ).fetchone()
    conn.close()
    return row_to_dict(row) if row else None
