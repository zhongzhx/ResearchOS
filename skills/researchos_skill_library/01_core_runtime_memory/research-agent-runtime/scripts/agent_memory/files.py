from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .database import connect
from .ledger import create_memory
from .models import as_list, clean, json_dumps, now, row_to_dict, stable_id


def file_checksum(path_value: str) -> str:
    path = Path(path_value)
    if not path.is_file():
        return ""
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def register_data_file(agent_root: Path, data: dict[str, Any]) -> dict[str, Any]:
    path_value = clean(data.get("path") or data.get("file_path"))
    filename = clean(data.get("filename")) or (Path(path_value).name if path_value else "unnamed_file")
    checksum = clean(data.get("checksum")) or file_checksum(path_value)
    file_id = clean(data.get("id")) or stable_id(data.get("project_id", ""), data.get("experiment_id", ""), filename, checksum or path_value)
    row = {
        "id": file_id,
        "user_id": clean(data.get("user_id")) or "local_user",
        "group_id": clean(data.get("group_id")),
        "project_id": clean(data.get("project_id")),
        "experiment_id": clean(data.get("experiment_id")),
        "filename": filename,
        "file_type": clean(data.get("file_type")) or Path(filename).suffix.lower().lstrip("."),
        "path": path_value,
        "checksum": checksum,
        "upload_time": clean(data.get("upload_time")) or now(),
        "description": clean(data.get("description")),
        "parsed_summary": clean(data.get("parsed_summary")),
        "columns_json": json_dumps(as_list(data.get("columns"))),
        "sample_mapping_json": json_dumps(data.get("sample_mapping") or {}),
        "analysis_status": clean(data.get("analysis_status")) or "registered",
        "related_memory_ids_json": json_dumps(as_list(data.get("related_memory_ids"))),
        "created_at": now(),
        "updated_at": now(),
    }
    conn = connect(agent_root)
    conn.execute(
        """
        INSERT INTO data_files(
            id, user_id, group_id, project_id, experiment_id, filename, file_type, path, checksum,
            upload_time, description, parsed_summary, columns_json, sample_mapping_json, analysis_status,
            related_memory_ids_json, created_at, updated_at
        )
        VALUES (
            :id, :user_id, :group_id, :project_id, :experiment_id, :filename, :file_type, :path, :checksum,
            :upload_time, :description, :parsed_summary, :columns_json, :sample_mapping_json, :analysis_status,
            :related_memory_ids_json, :created_at, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            project_id=excluded.project_id,
            experiment_id=excluded.experiment_id,
            description=excluded.description,
            parsed_summary=excluded.parsed_summary,
            columns_json=excluded.columns_json,
            sample_mapping_json=excluded.sample_mapping_json,
            analysis_status=excluded.analysis_status,
            related_memory_ids_json=excluded.related_memory_ids_json,
            updated_at=excluded.updated_at
        """,
        row,
    )
    conn.commit()
    saved = conn.execute("SELECT * FROM data_files WHERE id=?", (file_id,)).fetchone()
    conn.close()
    data_file = row_to_dict(saved)
    memory = create_memory(
        agent_root,
        {
            "user_id": row["user_id"],
            "group_id": row["group_id"],
            "project_id": row["project_id"],
            "experiment_id": row["experiment_id"],
            "memory_type": "dataset_memory",
            "subject": filename,
            "content": f"Data file registered: {filename}. Type: {row['file_type']}. Summary: {row['parsed_summary'] or row['description']}.",
            "structured_content": data_file,
            "entities": {"file_id": file_id, "filename": filename, "columns": data_file.get("columns", [])},
            "tags": ["data_file", row["file_type"], row["analysis_status"]],
            "related_file_ids": [file_id],
            "confidence": data.get("confidence", 0.86),
        },
    )
    data_file["memory_id"] = memory["id"]
    return data_file


def _link_file(agent_root: Path, file_id: str, column: str, value: str) -> dict[str, Any]:
    conn = connect(agent_root)
    conn.execute(f"UPDATE data_files SET {column}=?, updated_at=? WHERE id=?", (value, now(), file_id))
    row = conn.execute("SELECT * FROM data_files WHERE id=?", (file_id,)).fetchone()
    if not row:
        conn.close()
        raise KeyError("data file not found")
    conn.commit()
    conn.close()
    return row_to_dict(row)


def link_file_to_project(agent_root: Path, file_id: str, project_id: str) -> dict[str, Any]:
    return _link_file(agent_root, file_id, "project_id", project_id)


def link_file_to_experiment(agent_root: Path, file_id: str, experiment_id: str) -> dict[str, Any]:
    return _link_file(agent_root, file_id, "experiment_id", experiment_id)
