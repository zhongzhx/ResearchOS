from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_memory import api as memory_api
from agent_memory.database import connect as connect_memory_db
from agent_memory.models import ACTIVE_STATUSES
from agent_memory.review_queue import enqueue_review, list_review_queue
from agent_memory.views import get_current_project_view, upsert_memory_view
from answer_kb import answer as legacy_kb_answer
from lab_agent_features import query_rag as runtime_query_rag
from runtime_common import project_kb_root


ACTIVE_OBJECT_STATUSES = {"active", "current", "draft", "weak", "confirmed", "pending", "completed"}
OBJECT_TYPE_PRIORITIES = {
    "decision": 120,
    "conclusion": 110,
    "experiment": 100,
    "data_file": 90,
    "protocol": 80,
    "failure": 70,
    "sample": 60,
    "reference_chunk": 50,
    "knowledge_base_entry": 45,
    "reference": 40,
    "agent_memory": 30,
    "legacy_kb": 20,
    "runtime_rag": 10,
}


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def stable_id(*parts: Any, length: int = 24) -> str:
    import hashlib

    joined = "|".join(clean(part).lower() for part in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:length]


def json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else None, ensure_ascii=False, sort_keys=True)


def json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return default


def as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            parsed = json_loads(stripped, [])
            return parsed if isinstance(parsed, list) else [parsed]
        return [item.strip() for item in re.split(r"[,;\n]+", stripped) if item.strip()]
    return [value]


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z0-9_.+-]{2,}|[\u4e00-\u9fa5]{2,}", text or "")]


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    for key in list(item.keys()):
        if key.endswith("_json"):
            parsed_key = key[:-5]
            default = [] if key.endswith("ids_json") or key in {
                "groups_json",
                "sample_ids_json",
                "conditions_json",
                "concentrations_json",
                "time_points_json",
                "cell_lines_json",
                "organisms_json",
                "instruments_json",
                "assays_json",
                "related_experiment_ids_json",
                "related_file_ids_json",
                "columns_json",
                "sample_mapping_json",
                "related_memory_ids_json",
                "supported_by_experiment_ids_json",
                "supported_by_file_ids_json",
                "contradicted_by_ids_json",
                "supersedes_json",
                "downstream_effects_json",
                "do_not_repeat_without_json",
                "related_sample_ids_json",
            } else {}
            item[parsed_key] = json_loads(item.pop(key), default)
    return item


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(row) or {} for row in rows]


def ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def ensure_research_memory_schema(conn: sqlite3.Connection) -> None:
    ensure_columns(
        conn,
        "experiments",
        {
            "design_summary": "TEXT",
            "groups_json": "TEXT",
            "sample_ids_json": "TEXT",
            "conditions_json": "TEXT",
            "concentrations_json": "TEXT",
            "time_points_json": "TEXT",
            "cell_lines_json": "TEXT",
            "organisms_json": "TEXT",
            "instruments_json": "TEXT",
            "assays_json": "TEXT",
            "processed_data_file_ids_json": "TEXT",
            "limitations": "TEXT",
            "evidence_strength": "TEXT",
            "confidence": "REAL DEFAULT 0.5",
        },
    )
    ensure_columns(
        conn,
        "samples",
        {
            "group_id": "TEXT",
            "sample_code": "TEXT",
            "name": "TEXT",
            "source": "TEXT",
            "batch": "TEXT",
            "preparation_method": "TEXT",
            "storage_condition": "TEXT",
            "current_status": "TEXT",
            "related_experiment_ids_json": "TEXT",
            "related_file_ids_json": "TEXT",
        },
    )
    ensure_columns(
        conn,
        "research_files",
        {
            "user_id": "TEXT",
            "group_id": "TEXT",
            "parsed_summary": "TEXT",
            "columns_json": "TEXT",
            "sample_mapping_json": "TEXT",
            "analysis_status": "TEXT",
            "related_memory_ids_json": "TEXT",
        },
    )
    ensure_columns(
        conn,
        "failure_logs",
        {
            "experiment_id": "TEXT",
            "failure_type": "TEXT",
            "failure_description": "TEXT",
            "likely_reason": "TEXT",
            "do_not_repeat_without_json": "TEXT",
            "related_protocol_id": "TEXT",
            "related_sample_ids_json": "TEXT",
            "confidence": "REAL DEFAULT 0.5",
        },
    )
    ensure_columns(
        conn,
        "decision_logs",
        {
            "reason": "TEXT",
            "downstream_effects_json": "TEXT",
            "supersedes_json": "TEXT",
            "status": "TEXT",
            "confidence": "REAL DEFAULT 0.5",
        },
    )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS conclusions (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            conclusion_text TEXT NOT NULL,
            supported_by_experiment_ids_json TEXT,
            supported_by_file_ids_json TEXT,
            contradicted_by_ids_json TEXT,
            evidence_strength TEXT,
            confidence REAL,
            status TEXT,
            valid_from TEXT,
            valid_until TEXT,
            supersedes_json TEXT,
            superseded_by TEXT,
            source_claim_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            decision_text TEXT NOT NULL,
            reason TEXT,
            downstream_effects_json TEXT,
            supersedes_json TEXT,
            status TEXT,
            confidence REAL,
            source_log_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_conclusions_project_status ON conclusions(project_id, status, updated_at);
        CREATE INDEX IF NOT EXISTS idx_decisions_project_status ON decisions(project_id, status, updated_at);
        """
    )
    conn.commit()


def connect_research_db(agent_root: Path) -> sqlite3.Connection:
    import research_os_mvp as research_os

    conn = research_os.connect(agent_root)
    ensure_research_memory_schema(conn)
    return conn


def _memory_payload_from_project(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": project.get("owner") or "local_user",
        "project_id": project["id"],
        "memory_type": "project_memory",
        "subject": project.get("title") or project["id"],
        "content": f"Project state: {project.get('title')}. Area: {project.get('research_area')}. Status: {project.get('status')}.",
        "structured_content": project,
        "entities": {"project_id": project["id"], "keywords": project.get("keywords", [])},
        "tags": ["project", project.get("status") or "active"],
        "confidence": 0.92,
        "evidence_strength": "user_confirmed",
        "status": "active",
    }


def _memory_payload_from_experiment(experiment: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": "local_user",
        "project_id": experiment["project_id"],
        "experiment_id": experiment["id"],
        "memory_type": "experiment_memory",
        "subject": experiment.get("title") or experiment["id"],
        "content": f"Experiment {experiment.get('title')} on {experiment.get('experiment_date') or experiment.get('date') or 'unknown date'}: {clean(experiment.get('result_summary') or experiment.get('conclusion'))}",
        "structured_content": experiment,
        "entities": {
            "experiment_id": experiment["id"],
            "protocol_id": experiment.get("protocol_id"),
            "sample_ids": experiment.get("sample_ids", []),
        },
        "tags": ["experiment", experiment.get("status") or "unknown", experiment.get("experiment_type") or "unknown"],
        "related_file_ids": as_list(experiment.get("raw_data_file_ids")) + as_list(experiment.get("processed_data_file_ids")),
        "related_sample_ids": as_list(experiment.get("sample_ids")),
        "related_protocol_ids": [experiment["protocol_id"]] if clean(experiment.get("protocol_id")) else [],
        "confidence": float(experiment.get("confidence") or 0.72),
        "evidence_strength": clean(experiment.get("evidence_strength")) or "preliminary",
        "status": "active" if clean(experiment.get("status")) not in {"superseded", "archived"} else "archived",
    }


def _memory_payload_from_sample(sample: dict[str, Any]) -> dict[str, Any]:
    sample_label = clean(sample.get("sample_code") or sample.get("sample_id") or sample.get("name") or sample["id"])
    return {
        "user_id": "local_user",
        "project_id": sample["project_id"],
        "memory_type": "sample_memory",
        "subject": sample_label,
        "content": f"Sample {sample_label}. Type: {sample.get('sample_type') or 'unknown'}. Batch: {sample.get('batch') or 'unknown'}. Status: {sample.get('current_status') or sample.get('status') or 'unknown'}.",
        "structured_content": sample,
        "entities": {"sample_id": sample["id"], "sample_code": sample_label},
        "tags": ["sample", sample.get("sample_type") or "unknown", sample.get("current_status") or sample.get("status") or "unknown"],
        "related_file_ids": as_list(sample.get("related_file_ids")),
        "related_sample_ids": [sample["id"], sample_label],
        "confidence": 0.84,
        "evidence_strength": "user_confirmed" if clean(sample.get("current_status")) else "preliminary",
        "status": "active",
    }


def _memory_payload_from_data_file(file_row: dict[str, Any]) -> dict[str, Any]:
    sample_mapping = file_row.get("sample_mapping") or {}
    if not isinstance(sample_mapping, dict):
        sample_mapping = {}
    return {
        "user_id": clean(file_row.get("user_id")) or "local_user",
        "project_id": file_row["project_id"],
        "experiment_id": clean(file_row.get("experiment_id")),
        "memory_type": "dataset_memory",
        "subject": file_row.get("original_filename") or file_row.get("filename") or file_row["id"],
        "content": f"Data file {file_row.get('original_filename') or file_row.get('filename')}. Type: {file_row.get('detected_document_category') or file_row.get('file_type')}. Analysis status: {file_row.get('analysis_status') or file_row.get('context_status') or 'registered'}.",
        "structured_content": file_row,
        "entities": {
            "file_id": file_row["id"],
            "experiment_id": file_row.get("experiment_id"),
            "sample_mapping": sample_mapping,
        },
        "tags": ["data_file", file_row.get("detected_document_category") or file_row.get("file_type") or "unknown", file_row.get("analysis_status") or "registered"],
        "related_file_ids": [file_row["id"]],
        "related_sample_ids": as_list(file_row.get("sample_source")) + list(sample_mapping.keys()),
        "confidence": 0.86,
        "evidence_strength": "raw_observation" if clean(file_row.get("raw_processed_status")) == "raw" else "preliminary",
        "status": "active",
    }


def _memory_payload_from_failure(failure: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": "local_user",
        "project_id": failure["project_id"],
        "experiment_id": clean(failure.get("experiment_id")),
        "memory_type": "failure_memory",
        "subject": failure.get("title") or failure["id"],
        "content": f"Failure: {clean(failure.get('failure_description') or failure.get('observed_failure'))}. Likely reason: {clean(failure.get('likely_reason') or failure.get('suspected_causes'))}.",
        "structured_content": failure,
        "entities": {"failure_id": failure["id"], "protocol_id": failure.get("related_protocol_id")},
        "tags": ["failure", failure.get("failure_type") or "unknown"],
        "related_sample_ids": as_list(failure.get("related_sample_ids")),
        "related_protocol_ids": [failure["related_protocol_id"]] if clean(failure.get("related_protocol_id")) else [],
        "confidence": float(failure.get("confidence") or 0.7),
        "evidence_strength": "raw_observation",
        "status": "active",
    }


def _memory_payload_from_conclusion(conclusion: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": "local_user",
        "project_id": conclusion["project_id"],
        "memory_type": "conclusion_memory",
        "subject": clean(conclusion.get("conclusion_text"))[:120] or conclusion["id"],
        "content": clean(conclusion.get("conclusion_text")),
        "structured_content": conclusion,
        "entities": {"conclusion_id": conclusion["id"]},
        "tags": ["conclusion", clean(conclusion.get("status")) or "draft"],
        "related_file_ids": as_list(conclusion.get("supported_by_file_ids")),
        "confidence": float(conclusion.get("confidence") or 0.6),
        "evidence_strength": clean(conclusion.get("evidence_strength")) or "preliminary",
        "status": "active" if clean(conclusion.get("status")) not in {"superseded", "archived", "rejected"} else "archived",
    }


def _memory_payload_from_decision(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": "local_user",
        "project_id": decision["project_id"],
        "memory_type": "decision_memory",
        "subject": clean(decision.get("decision_text"))[:120] or decision["id"],
        "content": f"Decision: {clean(decision.get('decision_text'))}. Reason: {clean(decision.get('reason'))}.",
        "structured_content": decision,
        "entities": {"decision_id": decision["id"]},
        "tags": ["decision", clean(decision.get("status")) or "active"],
        "confidence": float(decision.get("confidence") or 0.72),
        "evidence_strength": "user_confirmed",
        "status": "active" if clean(decision.get("status")) not in {"superseded", "archived"} else "archived",
    }


def record_memory_event(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return memory_api.create_memory(agent_root, payload)


def sync_project(agent_root: Path, project: dict[str, Any]) -> dict[str, Any]:
    saved = record_memory_event(agent_root, _memory_payload_from_project(project))
    refresh_memory_views(agent_root, project["id"])
    return saved


def sync_experiment(agent_root: Path, experiment: dict[str, Any]) -> dict[str, Any]:
    saved = record_memory_event(agent_root, _memory_payload_from_experiment(experiment))
    refresh_memory_views(agent_root, experiment["project_id"])
    return saved


def sync_sample(agent_root: Path, sample: dict[str, Any]) -> dict[str, Any]:
    saved = record_memory_event(agent_root, _memory_payload_from_sample(sample))
    refresh_memory_views(agent_root, sample["project_id"])
    return saved


def sync_data_file(agent_root: Path, file_row: dict[str, Any]) -> dict[str, Any]:
    saved = record_memory_event(agent_root, _memory_payload_from_data_file(file_row))
    refresh_memory_views(agent_root, file_row["project_id"])
    return saved


def sync_failure(agent_root: Path, failure: dict[str, Any]) -> dict[str, Any]:
    saved = record_memory_event(agent_root, _memory_payload_from_failure(failure))
    refresh_memory_views(agent_root, failure["project_id"])
    return saved


def sync_conclusion(agent_root: Path, conclusion: dict[str, Any]) -> dict[str, Any]:
    saved = record_memory_event(agent_root, _memory_payload_from_conclusion(conclusion))
    refresh_memory_views(agent_root, conclusion["project_id"])
    return saved


def sync_decision(agent_root: Path, decision: dict[str, Any]) -> dict[str, Any]:
    saved = record_memory_event(agent_root, _memory_payload_from_decision(decision))
    refresh_memory_views(agent_root, decision["project_id"])
    return saved


def sync_agent_memory_entry(agent_root: Path, entry: dict[str, Any]) -> dict[str, Any] | None:
    if clean(entry.get("memory_scope")) != "project" or not clean(entry.get("project_id")):
        return None
    memory_type = clean(entry.get("memory_type"))
    mapped_type = {
        "weekly_literature_digest": "literature_memory",
        "experiment_log": "experiment_memory",
        "retrospective": "project_memory",
        "rag_answer": "literature_memory",
        "writing_output": "writing_memory",
    }.get(memory_type, "project_memory")
    saved = record_memory_event(
        agent_root,
        {
            "user_id": "local_user",
            "project_id": entry["project_id"],
            "memory_type": mapped_type,
            "subject": entry.get("title") or entry["id"],
            "content": entry.get("content") or "",
            "structured_content": entry.get("structured_content") or {},
            "entities": {"agent_memory_entry_id": entry["id"], "source_type": entry.get("source_type"), "source_id": entry.get("source_id")},
            "tags": ["agent_memory_entry", memory_type or "note"],
            "confidence": float(entry.get("confidence") or 0.8),
            "evidence_strength": "preliminary" if clean(entry.get("trust_level")) == "raw_extracted" else "user_confirmed",
            "status": "active" if clean(entry.get("status")) == "active" else "archived",
        },
    )
    refresh_memory_views(agent_root, entry["project_id"])
    return saved


def list_experiments(agent_root: Path, project_id: str = "") -> list[dict[str, Any]]:
    conn = connect_research_db(agent_root)
    rows = conn.execute(
        "SELECT * FROM experiments WHERE (?='' OR project_id=?) ORDER BY COALESCE(experiment_date, created_at) DESC, updated_at DESC",
        (project_id, project_id),
    ).fetchall()
    conn.close()
    return rows_to_dicts(rows)


def list_samples(agent_root: Path, project_id: str = "") -> list[dict[str, Any]]:
    conn = connect_research_db(agent_root)
    rows = conn.execute(
        "SELECT * FROM samples WHERE (?='' OR project_id=?) ORDER BY COALESCE(sample_code, sample_id, name, id)",
        (project_id, project_id),
    ).fetchall()
    conn.close()
    return rows_to_dicts(rows)


def list_data_files(agent_root: Path, project_id: str = "") -> list[dict[str, Any]]:
    conn = connect_research_db(agent_root)
    rows = conn.execute(
        "SELECT * FROM research_files WHERE (?='' OR project_id=?) ORDER BY imported_at DESC, updated_at DESC",
        (project_id, project_id),
    ).fetchall()
    conn.close()
    return rows_to_dicts(rows)


def list_failures(agent_root: Path, project_id: str = "") -> list[dict[str, Any]]:
    conn = connect_research_db(agent_root)
    rows = conn.execute(
        "SELECT * FROM failure_logs WHERE (?='' OR project_id=?) ORDER BY updated_at DESC",
        (project_id, project_id),
    ).fetchall()
    conn.close()
    return rows_to_dicts(rows)


def list_conclusions(agent_root: Path, project_id: str = "", status: str = "") -> list[dict[str, Any]]:
    conn = connect_research_db(agent_root)
    clauses = ["1=1"]
    params: list[Any] = []
    if project_id:
        clauses.append("project_id=?")
        params.append(project_id)
    if status:
        clauses.append("status=?")
        params.append(status)
    rows = conn.execute(f"SELECT * FROM conclusions WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC", params).fetchall()
    conn.close()
    return rows_to_dicts(rows)


def list_decisions(agent_root: Path, project_id: str = "", status: str = "") -> list[dict[str, Any]]:
    conn = connect_research_db(agent_root)
    clauses = ["1=1"]
    params: list[Any] = []
    if project_id:
        clauses.append("project_id=?")
        params.append(project_id)
    if status:
        clauses.append("status=?")
        params.append(status)
    rows = conn.execute(f"SELECT * FROM decisions WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC", params).fetchall()
    conn.close()
    return rows_to_dicts(rows)


def _upsert_extended_experiment_fields(conn: sqlite3.Connection, experiment_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    allowed_map = {
        "design_summary": clean(patch.get("design_summary") or patch.get("design")),
        "groups_json": json_dumps(patch.get("groups") or patch.get("groups_json") or []),
        "sample_ids_json": json_dumps(as_list(patch.get("sample_ids") or patch.get("samples") or patch.get("sample_ids_json"))),
        "conditions_json": json_dumps(patch.get("conditions") or patch.get("conditions_json") or []),
        "concentrations_json": json_dumps(patch.get("concentrations") or patch.get("concentrations_json") or []),
        "time_points_json": json_dumps(patch.get("time_points") or patch.get("timepoints") or patch.get("time_points_json") or []),
        "cell_lines_json": json_dumps(as_list(patch.get("cell_lines") or patch.get("cell_lines_json"))),
        "organisms_json": json_dumps(as_list(patch.get("organisms") or patch.get("organisms_json"))),
        "instruments_json": json_dumps(as_list(patch.get("instruments") or patch.get("instruments_json"))),
        "assays_json": json_dumps(as_list(patch.get("assays") or patch.get("assays_json"))),
        "processed_data_file_ids_json": json_dumps(as_list(patch.get("processed_data_file_ids") or patch.get("processed_data_file_ids_json"))),
        "limitations": clean(patch.get("limitations")),
        "evidence_strength": clean(patch.get("evidence_strength")),
        "confidence": float(patch.get("confidence") or 0.5),
    }
    conn.execute(
        """
        UPDATE experiments
        SET design_summary=?, groups_json=?, sample_ids_json=?, conditions_json=?, concentrations_json=?,
            time_points_json=?, cell_lines_json=?, organisms_json=?, instruments_json=?, assays_json=?,
            processed_data_file_ids_json=?, limitations=?, evidence_strength=?, confidence=?, updated_at=?
        WHERE id=?
        """,
        (
            allowed_map["design_summary"],
            allowed_map["groups_json"],
            allowed_map["sample_ids_json"],
            allowed_map["conditions_json"],
            allowed_map["concentrations_json"],
            allowed_map["time_points_json"],
            allowed_map["cell_lines_json"],
            allowed_map["organisms_json"],
            allowed_map["instruments_json"],
            allowed_map["assays_json"],
            allowed_map["processed_data_file_ids_json"],
            allowed_map["limitations"],
            allowed_map["evidence_strength"],
            allowed_map["confidence"],
            now(),
            experiment_id,
        ),
    )
    return row_to_dict(conn.execute("SELECT * FROM experiments WHERE id=?", (experiment_id,)).fetchone()) or {}


def upsert_conclusion(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    project_id = clean(payload.get("project_id"))
    conclusion_text = clean(payload.get("conclusion_text") or payload.get("text"))
    if not project_id or not conclusion_text:
        raise ValueError("project_id and conclusion_text are required")
    timestamp = now()
    conclusion_id = clean(payload.get("id")) or stable_id(project_id, conclusion_text, payload.get("source_claim_id"), length=24)
    row = {
        "id": conclusion_id,
        "project_id": project_id,
        "conclusion_text": conclusion_text,
        "supported_by_experiment_ids_json": json_dumps(as_list(payload.get("supported_by_experiment_ids"))),
        "supported_by_file_ids_json": json_dumps(as_list(payload.get("supported_by_file_ids"))),
        "contradicted_by_ids_json": json_dumps(as_list(payload.get("contradicted_by_ids"))),
        "evidence_strength": clean(payload.get("evidence_strength")) or "preliminary",
        "confidence": float(payload.get("confidence") or 0.6),
        "status": clean(payload.get("status")) or "draft",
        "valid_from": clean(payload.get("valid_from")) or timestamp,
        "valid_until": clean(payload.get("valid_until")),
        "supersedes_json": json_dumps(as_list(payload.get("supersedes"))),
        "superseded_by": clean(payload.get("superseded_by")),
        "source_claim_id": clean(payload.get("source_claim_id")),
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    conn = connect_research_db(agent_root)
    conn.execute(
        """
        INSERT INTO conclusions(
            id, project_id, conclusion_text, supported_by_experiment_ids_json, supported_by_file_ids_json,
            contradicted_by_ids_json, evidence_strength, confidence, status, valid_from, valid_until,
            supersedes_json, superseded_by, source_claim_id, created_at, updated_at
        )
        VALUES (
            :id, :project_id, :conclusion_text, :supported_by_experiment_ids_json, :supported_by_file_ids_json,
            :contradicted_by_ids_json, :evidence_strength, :confidence, :status, :valid_from, :valid_until,
            :supersedes_json, :superseded_by, :source_claim_id, :created_at, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            conclusion_text=excluded.conclusion_text,
            supported_by_experiment_ids_json=excluded.supported_by_experiment_ids_json,
            supported_by_file_ids_json=excluded.supported_by_file_ids_json,
            contradicted_by_ids_json=excluded.contradicted_by_ids_json,
            evidence_strength=excluded.evidence_strength,
            confidence=excluded.confidence,
            status=excluded.status,
            valid_until=excluded.valid_until,
            supersedes_json=excluded.supersedes_json,
            superseded_by=excluded.superseded_by,
            source_claim_id=excluded.source_claim_id,
            updated_at=excluded.updated_at
        """,
        row,
    )
    for old_id in as_list(payload.get("supersedes")):
        conn.execute("UPDATE conclusions SET status='superseded', superseded_by=?, updated_at=? WHERE id=?", (conclusion_id, timestamp, str(old_id)))
    conn.commit()
    saved = row_to_dict(conn.execute("SELECT * FROM conclusions WHERE id=?", (conclusion_id,)).fetchone()) or {}
    conn.close()
    sync_conclusion(agent_root, saved)
    return saved


def upsert_decision(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    project_id = clean(payload.get("project_id"))
    decision_text = clean(payload.get("decision_text") or payload.get("decision") or payload.get("text"))
    if not project_id or not decision_text:
        raise ValueError("project_id and decision_text are required")
    timestamp = now()
    decision_id = clean(payload.get("id")) or stable_id(project_id, decision_text, payload.get("source_log_id"), length=24)
    row = {
        "id": decision_id,
        "project_id": project_id,
        "decision_text": decision_text,
        "reason": clean(payload.get("reason") or payload.get("rationale")),
        "downstream_effects_json": json_dumps(as_list(payload.get("downstream_effects"))),
        "supersedes_json": json_dumps(as_list(payload.get("supersedes"))),
        "status": clean(payload.get("status")) or "active",
        "confidence": float(payload.get("confidence") or 0.72),
        "source_log_id": clean(payload.get("source_log_id")),
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    conn = connect_research_db(agent_root)
    conn.execute(
        """
        INSERT INTO decisions(
            id, project_id, decision_text, reason, downstream_effects_json, supersedes_json,
            status, confidence, source_log_id, created_at, updated_at
        )
        VALUES (
            :id, :project_id, :decision_text, :reason, :downstream_effects_json, :supersedes_json,
            :status, :confidence, :source_log_id, :created_at, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            decision_text=excluded.decision_text,
            reason=excluded.reason,
            downstream_effects_json=excluded.downstream_effects_json,
            supersedes_json=excluded.supersedes_json,
            status=excluded.status,
            confidence=excluded.confidence,
            source_log_id=excluded.source_log_id,
            updated_at=excluded.updated_at
        """,
        row,
    )
    for old_id in as_list(payload.get("supersedes")):
        conn.execute("UPDATE decisions SET status='superseded', updated_at=? WHERE id=?", (timestamp, str(old_id)))
    conn.commit()
    saved = row_to_dict(conn.execute("SELECT * FROM decisions WHERE id=?", (decision_id,)).fetchone()) or {}
    conn.close()
    sync_decision(agent_root, saved)
    return saved


def sync_claim_to_conclusion(agent_root: Path, claim: dict[str, Any], evidence: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    if clean(claim.get("claim_type")) not in {"result", "conclusion", "unsupported_conclusion", "limitation", "hypothesis"}:
        return None
    evidence = evidence or []
    experiment_ids = [item.get("evidence_id") for item in evidence if item.get("evidence_type") == "experiment" and clean(item.get("evidence_id"))]
    file_ids = [
        item.get("source_file_id") or item.get("evidence_id")
        for item in evidence
        if item.get("evidence_type") in {"source_file", "provenance_record"} and clean(item.get("source_file_id") or item.get("evidence_id"))
    ]
    contradicted = [item.get("evidence_id") for item in evidence if item.get("evidence_type") == "failure_log" and clean(item.get("evidence_id"))]
    return upsert_conclusion(
        agent_root,
        {
            "id": stable_id("conclusion", claim["id"], length=24),
            "project_id": claim["project_id"],
            "conclusion_text": claim["claim_text"],
            "supported_by_experiment_ids": experiment_ids,
            "supported_by_file_ids": file_ids,
            "contradicted_by_ids": contradicted,
            "evidence_strength": "preliminary" if claim.get("status") in {"draft", "weak", "unsupported"} else "replicated",
            "confidence": claim.get("confidence") or 0.6,
            "status": claim.get("status") or "draft",
            "source_claim_id": claim["id"],
        },
    )


def sync_decision_log_to_canonical(agent_root: Path, decision_log: dict[str, Any]) -> dict[str, Any]:
    return upsert_decision(
        agent_root,
        {
            "id": stable_id("decision", decision_log["id"], length=24),
            "project_id": decision_log["project_id"],
            "decision_text": decision_log.get("decision"),
            "reason": decision_log.get("reason") or decision_log.get("rationale"),
            "confidence": decision_log.get("confidence") or 0.72,
            "source_log_id": decision_log["id"],
            "status": decision_log.get("status") or "active",
        },
    )


def _view_version(agent_root: Path, project_id: str) -> str:
    view = get_current_project_view(agent_root, project_id)
    if view:
        return clean(view.get("last_consolidated_at")) or clean(view.get("updated_at")) or "uninitialized"
    refresh_memory_views(agent_root, project_id)
    view = get_current_project_view(agent_root, project_id)
    return clean((view or {}).get("last_consolidated_at")) or clean((view or {}).get("updated_at")) or "uninitialized"


def refresh_memory_views(agent_root: Path, project_id: str, user_id: str = "local_user") -> dict[str, Any]:
    conn = connect_research_db(agent_root)
    project = row_to_dict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())
    if not project:
        conn.close()
        raise KeyError("project not found")
    experiments = rows_to_dicts(conn.execute("SELECT * FROM experiments WHERE project_id=? ORDER BY COALESCE(experiment_date, created_at) DESC", (project_id,)).fetchall())
    samples = rows_to_dicts(conn.execute("SELECT * FROM samples WHERE project_id=? ORDER BY COALESCE(sample_code, sample_id, name, id)", (project_id,)).fetchall())
    data_files = rows_to_dicts(conn.execute("SELECT * FROM research_files WHERE project_id=? ORDER BY imported_at DESC", (project_id,)).fetchall())
    conclusions = rows_to_dicts(conn.execute("SELECT * FROM conclusions WHERE project_id=? ORDER BY updated_at DESC", (project_id,)).fetchall())
    decisions = rows_to_dicts(conn.execute("SELECT * FROM decisions WHERE project_id=? ORDER BY updated_at DESC", (project_id,)).fetchall())
    failures = rows_to_dicts(conn.execute("SELECT * FROM failure_logs WHERE project_id=? ORDER BY updated_at DESC", (project_id,)).fetchall())
    protocols = rows_to_dicts(conn.execute("SELECT * FROM protocols WHERE project_id=? ORDER BY updated_at DESC", (project_id,)).fetchall())
    reports = rows_to_dicts(conn.execute("SELECT * FROM reports WHERE project_id=? ORDER BY updated_at DESC LIMIT 20", (project_id,)).fetchall())
    conn.close()

    project_memories = memory_api.list_project_memory(agent_root, project_id, include_archived=True)
    evidence_ids = [memory["id"] for memory in project_memories[:120]]
    views = [
        upsert_memory_view(
            agent_root,
            user_id=user_id,
            project_id=project_id,
            view_type="current_project_view",
            subject=project.get("title") or project_id,
            summary=f"{project.get('title')} currently tracks {len(experiments)} experiments, {len(samples)} samples, {len(data_files)} data files, {len(conclusions)} conclusions, {len(decisions)} decisions, and {len(failures)} failures.",
            structured_summary={
                "project": project,
                "experiment_count": len(experiments),
                "sample_count": len(samples),
                "data_file_count": len(data_files),
                "conclusion_count": len(conclusions),
                "decision_count": len(decisions),
                "failure_count": len(failures),
            },
            evidence_memory_ids=evidence_ids,
            confidence=0.9,
        ),
        upsert_memory_view(
            agent_root,
            user_id=user_id,
            project_id=project_id,
            view_type="project_current_state",
            subject=project.get("title") or project_id,
            summary=f"{project.get('title')} currently tracks {len(experiments)} experiments, {len(samples)} samples, {len(data_files)} data files, {len(conclusions)} conclusions, {len(decisions)} decisions, and {len(failures)} failures.",
            structured_summary={"project": project},
            evidence_memory_ids=evidence_ids,
            confidence=0.9,
        ),
        upsert_memory_view(agent_root, user_id=user_id, project_id=project_id, view_type="experiment_summary_view", subject=project.get("title") or project_id, summary=f"{len(experiments)} experiments recorded.", structured_summary={"experiments": experiments[:30]}, evidence_memory_ids=evidence_ids, confidence=0.84),
        upsert_memory_view(agent_root, user_id=user_id, project_id=project_id, view_type="sample_inventory_view", subject=project.get("title") or project_id, summary=f"{len(samples)} samples available or referenced.", structured_summary={"samples": samples[:40]}, evidence_memory_ids=evidence_ids, confidence=0.84),
        upsert_memory_view(agent_root, user_id=user_id, project_id=project_id, view_type="dataset_view", subject=project.get("title") or project_id, summary=f"{len(data_files)} datasets or files linked to the project.", structured_summary={"data_files": data_files[:40]}, evidence_memory_ids=evidence_ids, confidence=0.84),
        upsert_memory_view(agent_root, user_id=user_id, project_id=project_id, view_type="conclusion_view", subject=project.get("title") or project_id, summary=f"{len(conclusions)} active or draft conclusions are tracked.", structured_summary={"conclusions": conclusions[:30]}, evidence_memory_ids=evidence_ids, confidence=0.8),
        upsert_memory_view(agent_root, user_id=user_id, project_id=project_id, view_type="decision_view", subject=project.get("title") or project_id, summary=f"{len(decisions)} project decisions are tracked.", structured_summary={"decisions": decisions[:30]}, evidence_memory_ids=evidence_ids, confidence=0.82),
        upsert_memory_view(agent_root, user_id=user_id, project_id=project_id, view_type="failure_view", subject=project.get("title") or project_id, summary=f"{len(failures)} failures or negative outcomes are available for retrieval.", structured_summary={"failures": failures[:30]}, evidence_memory_ids=evidence_ids, confidence=0.84),
        upsert_memory_view(agent_root, user_id=user_id, project_id=project_id, view_type="writing_view", subject=project.get("title") or project_id, summary=f"{len(reports)} recent reports and {len(conclusions)} conclusions can support writing tasks.", structured_summary={"reports": reports[:20], "conclusions": conclusions[:20], "protocols": protocols[:20]}, evidence_memory_ids=evidence_ids, confidence=0.8),
        upsert_memory_view(agent_root, user_id=user_id, project_id=project_id, view_type="user_preference_view", subject=project.get("title") or project_id, summary="User preference view derived from active preference or writing memories.", structured_summary={"preferences": [m for m in project_memories if m.get('memory_type') in {'preference_memory', 'writing_memory', 'user_profile_memory'}][:20]}, evidence_memory_ids=evidence_ids, confidence=0.74),
        upsert_memory_view(agent_root, user_id=user_id, project_id=project_id, view_type="group_profile_view", subject=project.get("title") or project_id, summary="Group profile view derived from active group profile memories.", structured_summary={"group_profile": [m for m in project_memories if m.get('memory_type') == 'group_profile_memory'][:10]}, evidence_memory_ids=evidence_ids, confidence=0.72),
    ]
    return {"project_id": project_id, "views": views, "memory_view_version": _view_version(agent_root, project_id)}


def _exact_ref_match(query: str, item: dict[str, Any]) -> int:
    query_lower = query.lower()
    for candidate in [
        item.get("id"),
        item.get("project_id"),
        item.get("experiment_id"),
        item.get("sample_id"),
        item.get("sample_code"),
        item.get("file_id"),
        item.get("source_id"),
        item.get("reference_id"),
    ]:
        if clean(candidate) and clean(candidate).lower() == query_lower:
            return 1
    return 0


def _semantic_overlap(query_tokens: set[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    tokens = set(tokenize(text))
    if not tokens:
        return 0.0
    return len(query_tokens.intersection(tokens)) / max(1, len(query_tokens))


def _status_rank(value: str) -> int:
    lowered = clean(value).lower()
    if lowered in ACTIVE_OBJECT_STATUSES or lowered in ACTIVE_STATUSES:
        return 1
    return 0


def _timestamp_value(item: dict[str, Any]) -> str:
    return clean(item.get("updated_at") or item.get("created_at") or item.get("valid_from") or item.get("imported_at"))


def _priority_tuple(query: str, item: dict[str, Any], view_version: str) -> tuple[Any, ...]:
    query_tokens = set(tokenize(query))
    joined_text = " ".join(
        clean(item.get(field))
        for field in [
            "title",
            "subject",
            "content",
            "summary",
            "claim_text",
            "conclusion_text",
            "decision_text",
            "observed_failure",
            "failure_description",
            "chunk_text",
            "matched_text",
            "abstract",
        ]
    )
    item_type = clean(item.get("object_type") or item.get("memory_type") or item.get("source_kind") or item.get("evidence_type"))
    return (
        _exact_ref_match(query, item),
        1 if clean(item.get("project_id")) else 0,
        _status_rank(clean(item.get("status") or item.get("context_status"))),
        OBJECT_TYPE_PRIORITIES.get(item_type, 0),
        _timestamp_value(item),
        float(item.get("confidence") or 0.0),
        round(_semantic_overlap(query_tokens, joined_text), 6),
        view_version,
        clean(item.get("id")),
    )


def _dedupe_by_id(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    ordered: list[dict[str, Any]] = []
    for item in items:
        item_id = clean(item.get("id"))
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        ordered.append(item)
    return ordered


def _is_broad_project_query(query: str) -> bool:
    tokens = set(tokenize(query))
    broad_tokens = {
        "summary",
        "summarize",
        "overview",
        "state",
        "status",
        "progress",
        "current",
        "project",
        "memory",
        "项目",
        "进展",
        "总结",
        "概览",
        "现状",
    }
    return bool(tokens.intersection(broad_tokens))


def query_research_context(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    project_id = clean(payload.get("project_id"))
    query = clean(payload.get("query") or payload.get("question"))
    if not project_id:
        raise ValueError("project_id is required")
    if not query:
        raise ValueError("query is required")
    limit = int(payload.get("limit") or 25)
    view_version = clean(payload.get("memory_view_version")) or _view_version(agent_root, project_id)
    refresh_memory_views(agent_root, project_id)

    conn = connect_research_db(agent_root)
    project = row_to_dict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()) or {}
    experiments = rows_to_dicts(conn.execute("SELECT * FROM experiments WHERE project_id=?", (project_id,)).fetchall())
    samples = rows_to_dicts(conn.execute("SELECT * FROM samples WHERE project_id=?", (project_id,)).fetchall())
    files = rows_to_dicts(conn.execute("SELECT * FROM research_files WHERE project_id=?", (project_id,)).fetchall())
    protocols = rows_to_dicts(conn.execute("SELECT * FROM protocols WHERE project_id=?", (project_id,)).fetchall())
    failures = rows_to_dicts(conn.execute("SELECT * FROM failure_logs WHERE project_id=?", (project_id,)).fetchall())
    conclusions = rows_to_dicts(conn.execute("SELECT * FROM conclusions WHERE project_id=?", (project_id,)).fetchall())
    decisions = rows_to_dicts(conn.execute("SELECT * FROM decisions WHERE project_id=?", (project_id,)).fetchall())
    references = rows_to_dicts(conn.execute('SELECT * FROM "references" WHERE project_id=?', (project_id,)).fetchall())
    chunks = rows_to_dicts(conn.execute("SELECT * FROM reference_chunks WHERE project_id=?", (project_id,)).fetchall())
    kb_entries = rows_to_dicts(conn.execute("SELECT * FROM knowledge_base_entries WHERE project_id=?", (project_id,)).fetchall())
    conn.close()

    candidates: list[dict[str, Any]] = []
    for row in experiments:
        row["object_type"] = "experiment"
        candidates.append(row)
    for row in samples:
        row["object_type"] = "sample"
        candidates.append(row)
    for row in files:
        row["object_type"] = "data_file"
        candidates.append(row)
    for row in protocols:
        row["object_type"] = "protocol"
        candidates.append(row)
    for row in failures:
        row["object_type"] = "failure"
        candidates.append(row)
    for row in conclusions:
        row["object_type"] = "conclusion"
        candidates.append(row)
    for row in decisions:
        row["object_type"] = "decision"
        candidates.append(row)
    for row in references:
        row["object_type"] = "reference"
        candidates.append(row)
    for row in chunks:
        row["object_type"] = "reference_chunk"
        row["title"] = row.get("section") or f"Chunk {row.get('chunk_index')}"
        candidates.append(row)
    for row in kb_entries:
        row["object_type"] = "knowledge_base_entry"
        candidates.append(row)

    agent_memory_results = memory_api.retrieve_memory(
        agent_root,
        {
            "project_id": project_id,
            "query": query,
            "include_archived": bool(payload.get("include_archived")),
            "max_results": max(limit * 2, 50),
        },
    )
    for row in agent_memory_results:
        row["object_type"] = "agent_memory"
        candidates.append(row)

    project_name = clean(project.get("title"))
    runtime_rag = runtime_query_rag(agent_root, {"project_name": project_name, "question": query, "limit": min(5, limit)}) if project_name else {"citations": []}
    for citation in runtime_rag.get("citations", []):
        candidates.append(
            {
                "id": citation.get("chunk_id"),
                "project_id": project_id,
                "object_type": "runtime_rag",
                "title": citation.get("file_name"),
                "matched_text": citation.get("matched_text"),
                "source_kind": "runtime_rag",
                "confidence": citation.get("score") or 0.0,
                "updated_at": view_version,
            }
        )

    kb_answer = legacy_kb_answer(project_kb_root(agent_root, project_name), query, limit=5) if project_name else ""
    if kb_answer and not kb_answer.startswith("Knowledge base not found"):
        candidates.append(
            {
                "id": stable_id(project_id, query, "legacy_kb", length=24),
                "project_id": project_id,
                "object_type": "legacy_kb",
                "title": "Legacy project KB answer",
                "content": kb_answer,
                "status": "active",
                "confidence": 0.42,
                "updated_at": view_version,
            }
        )

    ranked = []
    for item in candidates:
        item["priority"] = _priority_tuple(query, item, view_version)
        if item["priority"][0] or item["priority"][6] > 0 or clean(item.get("project_id")) == project_id:
            ranked.append(item)
    ranked.sort(key=lambda item: item["priority"], reverse=True)

    relevant = ranked[:limit]
    if _is_broad_project_query(query):
        coverage: list[dict[str, Any]] = []
        for object_type in ["decision", "conclusion", "experiment", "data_file", "protocol", "failure", "sample"]:
            item = next((row for row in ranked if clean(row.get("object_type")) == object_type), None)
            if item:
                coverage.append(item)
        relevant = _dedupe_by_id(relevant + coverage)[:limit]
    return {
        "project_id": project_id,
        "query": query,
        "memory_view_version": view_version,
        "current_project_view": get_current_project_view(agent_root, project_id),
        "results": relevant,
        "source_summary": {
            "experiments": len(experiments),
            "samples": len(samples),
            "data_files": len(files),
            "protocols": len(protocols),
            "failures": len(failures),
            "conclusions": len(conclusions),
            "decisions": len(decisions),
            "references": len(references),
            "reference_chunks": len(chunks),
            "knowledge_base_entries": len(kb_entries),
            "agent_memory_hits": len(agent_memory_results),
            "runtime_rag_hits": len(runtime_rag.get("citations", [])),
            "legacy_kb_used": bool(kb_answer and not kb_answer.startswith("Knowledge base not found")),
        },
    }


def build_research_memory_context(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    project_id = clean(payload.get("project_id"))
    query = clean(payload.get("query") or payload.get("question"))
    result = query_research_context(agent_root, {"project_id": project_id, "query": query, "limit": int(payload.get("limit") or 30), "memory_view_version": payload.get("memory_view_version")})
    current_view = result.get("current_project_view") or {}
    view_summary = current_view.get("structured_summary") or {}

    experiments = [item for item in result["results"] if item.get("object_type") == "experiment"][:8]
    samples = [item for item in result["results"] if item.get("object_type") == "sample"][:10]
    files = [item for item in result["results"] if item.get("object_type") == "data_file"][:8]
    conclusions = [item for item in result["results"] if item.get("object_type") == "conclusion"][:8]
    failures = [item for item in result["results"] if item.get("object_type") == "failure"][:8]
    decisions = [item for item in result["results"] if item.get("object_type") == "decision"][:8]
    protocols = [item for item in result["results"] if item.get("object_type") == "protocol"][:6]
    literature = [item for item in result["results"] if item.get("object_type") in {"reference", "reference_chunk", "knowledge_base_entry", "runtime_rag", "legacy_kb"}][:8]
    memory_items = [item for item in result["results"] if item.get("object_type") == "agent_memory"]
    preferences = [item for item in memory_items if item.get("memory_type") in {"preference_memory", "writing_memory", "user_profile_memory", "group_profile_memory"}][:6]
    tasks = [item for item in memory_items if item.get("memory_type") == "task_memory"][:6]

    if not experiments:
        experiments = list_experiments(agent_root, project_id)[:8]
    if not samples:
        samples = list_samples(agent_root, project_id)[:10]
    if not files:
        files = list_data_files(agent_root, project_id)[:8]
    if not conclusions:
        conclusions = list_conclusions(agent_root, project_id)[:8]
    if not failures:
        failures = list_failures(agent_root, project_id)[:8]
    if not decisions:
        decisions = list_decisions(agent_root, project_id)[:8]
    if not protocols:
        conn = connect_research_db(agent_root)
        protocols = rows_to_dicts(conn.execute("SELECT * FROM protocols WHERE project_id=? ORDER BY updated_at DESC LIMIT 6", (project_id,)).fetchall())
        conn.close()

    lines = [
        "Relevant Research Memory:",
        "1. Current project state",
        f"- {current_view.get('summary') or 'No consolidated project view found.'}",
        "2. Completed experiments",
    ]
    lines.extend(
        [f"- {clean(item.get('title'))}: {clean(item.get('result_summary') or item.get('conclusion') or item.get('design_summary')) or 'Missing structured summary.'}" for item in experiments]
        or ["- Missing experiment context."]
    )
    lines.append("3. Key samples and batches")
    lines.extend(
        [f"- {clean(item.get('sample_code') or item.get('sample_id'))} | batch {clean(item.get('batch')) or 'missing'} | status {clean(item.get('current_status') or item.get('status')) or 'missing'}" for item in samples]
        or ["- Missing sample context."]
    )
    lines.append("4. Available datasets and files")
    lines.extend(
        [f"- {clean(item.get('original_filename') or item.get('filename'))} | {clean(item.get('detected_document_category') or item.get('file_type'))} | experiment {clean(item.get('experiment_id')) or 'missing'}" for item in files]
        or ["- Missing data file context."]
    )
    lines.append("5. Current conclusions")
    lines.extend(
        [f"- {clean(item.get('conclusion_text') or item.get('claim_text'))} [{clean(item.get('status')) or 'draft'}]" for item in conclusions]
        or ["- No active conclusions found."]
    )
    lines.append("6. Failed or negative results")
    lines.extend(
        [f"- {clean(item.get('title'))}: {clean(item.get('failure_description') or item.get('observed_failure'))}" for item in failures]
        or ["- No explicit failure memory found."]
    )
    lines.append("7. Important decisions")
    lines.extend(
        [f"- {clean(item.get('decision_text'))}: {clean(item.get('reason')) or 'reason missing'}" for item in decisions]
        or ["- No active decisions found."]
    )
    lines.append("8. Relevant protocols")
    lines.extend(
        [f"- {clean(item.get('title'))}: assay {clean(item.get('assay_type') or item.get('protocol_type')) or 'missing'}" for item in protocols]
        or ["- No linked protocol found."]
    )
    lines.append("9. Relevant references or RAG evidence")
    lines.extend(
        [f"- {clean(item.get('title'))}: {clean(item.get('content') or item.get('chunk_text') or item.get('matched_text'))[:220]}" for item in literature]
        or ["- No relevant literature or RAG evidence found."]
    )
    lines.append("10. Pending tasks")
    lines.extend([f"- {clean(item.get('subject') or item.get('title'))}: {clean(item.get('content'))}" for item in tasks] or ["- No pending task memory found."])
    lines.append("11. User or group preferences")
    lines.extend([f"- {clean(item.get('content'))}" for item in preferences] or ["- No explicit user or group preference found."])

    return {
        "project_id": project_id,
        "query": query,
        "memory_view_version": result["memory_view_version"],
        "current_project_view": current_view,
        "structured_context": {
            "project": view_summary.get("project") or {},
            "experiments": experiments,
            "samples": samples,
            "data_files": files,
            "conclusions": conclusions,
            "failures": failures,
            "decisions": decisions,
            "protocols": protocols,
            "literature": literature,
            "tasks": tasks,
            "preferences": preferences,
        },
        "context_text": "\n".join(lines),
        "results": result["results"],
    }


def _extract_group_lines(text: str) -> dict[str, list[str]]:
    groups = {"control_groups": [], "treatment_groups": [], "positive_controls": [], "negative_controls": []}
    for line in text.splitlines():
        cleaned = clean(line)
        if not cleaned:
            continue
        lower = cleaned.lower()
        if "positive control" in lower:
            groups["positive_controls"].append(cleaned)
        elif "negative control" in lower or "blank" in lower:
            groups["negative_controls"].append(cleaned)
        elif "control" in lower or "vehicle" in lower or "model" in lower:
            groups["control_groups"].append(cleaned)
        elif "treat" in lower or "dose" in lower or "group" in lower:
            groups["treatment_groups"].append(cleaned)
    return groups


def _first_regex(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return clean(match.group(1) if match and match.lastindex else match.group(0) if match else "")


def extract_experiment_memory(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    project_id = clean(payload.get("project_id"))
    file_id = clean(payload.get("file_id"))
    text = str(payload.get("text") or payload.get("content") or "")
    source_file = {}
    if file_id:
        conn = connect_research_db(agent_root)
        source_file = row_to_dict(conn.execute("SELECT * FROM research_files WHERE id=?", (file_id,)).fetchone()) or {}
        conn.close()
        if not text:
            text = str(source_file.get("extracted_text") or "")
        if not project_id:
            project_id = clean(source_file.get("project_id"))
    if not text:
        raise ValueError("text or file_id is required")

    sample_ids = sorted(set(re.findall(r"\b(?:S|M|A|NP|CELL|AN)[-_]?\d{2,4}[A-Za-z]?\b", text, re.IGNORECASE)))
    concentrations = sorted(set(re.findall(r"\b\d+(?:\.\d+)?\s?(?:nM|uM|µM|mM|M|mg/mL|ug/mL|µg/mL|ng/mL|mg/kg|%)\b", text, re.IGNORECASE)))
    time_points = sorted(set(re.findall(r"\b\d+(?:\.\d+)?\s?(?:s|min|h|hr|hrs|hour|hours|d|day|days)\b", text, re.IGNORECASE)))
    cell_lines = sorted(set(re.findall(r"\b(?:RAW264\.7|HEK293T?|HeLa|HepG2|A549|HUVEC|MCF-7|C2C12|CHO|Jurkat)\b", text, re.IGNORECASE)))
    organisms = sorted(set(re.findall(r"\b(?:mouse|mice|rat|rats|zebrafish|human|humans|E\. coli)\b", text, re.IGNORECASE)))
    instruments = sorted(set(re.findall(r"\b(?:qPCR|RT-qPCR|ELISA|plate reader|LC-MS|LCMS|HPLC|Western blot|WB|flow cytometer|NMR)\b", text, re.IGNORECASE)))
    assays = sorted(set(re.findall(r"\b(?:qPCR|ELISA|Western blot|LC-MS|cell viability|NO assay|animal study)\b", text, re.IGNORECASE)))
    stats = sorted(set(re.findall(r"\b(?:ANOVA|t-test|Mann-Whitney|Kruskal-Wallis|FDR|Benjamini-Hochberg|linear regression|4PL)\b", text, re.IGNORECASE)))
    groups = _extract_group_lines(text)
    experiment_title = clean(payload.get("title") or payload.get("experiment_name")) or _first_regex(text, r"^\s*(?:Experiment|Name)\s*:\s*(.+)$") or _first_regex(text, r"^\s*#\s*(.+)$") or (clean(source_file.get("original_filename")) if source_file else "Extracted experiment")
    experiment_type = clean(payload.get("experiment_type")) or ("qPCR" if "qpcr" in text.lower() else "ELISA" if "elisa" in text.lower() else "wet-lab experiment")
    result_summary = _first_regex(text, r"^\s*(?:Result|Results|Observation|Observations)\s*:\s*(.+)$")
    conclusion = _first_regex(text, r"^\s*(?:Conclusion)\s*:\s*(.+)$")
    limitations = as_list(_first_regex(text, r"^\s*(?:Limitation|Limitations)\s*:\s*(.+)$"))
    next_steps = as_list(_first_regex(text, r"^\s*(?:Next step|Next steps)\s*:\s*(.+)$"))
    decision_text = _first_regex(text, r"^\s*(?:Decision)\s*:\s*(.+)$")
    failure_text = _first_regex(text, r"^\s*(?:Failure reason|Abnormal|Issue|Problem)\s*:\s*(.+)$")
    operator = clean(payload.get("operator")) or _first_regex(text, r"^\s*Operator\s*:\s*(.+)$")
    experiment_date = clean(payload.get("experiment_date")) or _first_regex(text, r"\b(20\d{2}[-/]\d{1,2}[-/]\d{1,2})\b")
    protocol_id = clean(payload.get("protocol_id"))
    confidence = 0.35
    confidence += 0.1 if sample_ids else 0.0
    confidence += 0.1 if groups["control_groups"] or groups["treatment_groups"] else 0.0
    confidence += 0.1 if concentrations else 0.0
    confidence += 0.1 if time_points else 0.0
    confidence += 0.1 if instruments else 0.0
    confidence += 0.1 if assays else 0.0
    confidence += 0.1 if result_summary or conclusion else 0.0
    confidence = min(0.9, confidence)

    experiment = {
        "project_id": project_id,
        "title": experiment_title,
        "experiment_type": experiment_type,
        "date": experiment_date or None,
        "operator": operator or None,
        "purpose": clean(payload.get("purpose")) or None,
        "design_summary": clean(payload.get("design_summary")) or clean(text[:280]) or None,
        "groups_json": groups,
        "sample_ids_json": sample_ids,
        "protocol_id": protocol_id or None,
        "conditions_json": groups,
        "concentrations_json": concentrations,
        "time_points_json": time_points,
        "cell_lines_json": cell_lines,
        "organisms_json": organisms,
        "instruments_json": instruments,
        "assays_json": assays,
        "raw_data_file_ids_json": [file_id] if file_id else [],
        "processed_data_file_ids_json": [],
        "result_summary": result_summary or None,
        "conclusion": conclusion or None,
        "limitations": limitations,
        "status": "failed" if failure_text else "completed",
        "evidence_strength": "preliminary",
        "confidence": round(confidence, 2),
    }
    samples = [
        {
            "project_id": project_id,
            "sample_code": label,
            "sample_type": clean(payload.get("sample_type")) or "unknown",
            "name": label,
            "source": clean(payload.get("sample_source")) or None,
            "batch": clean(payload.get("batch")) or None,
            "preparation_method": None,
            "storage_condition": None,
            "current_status": "referenced",
            "related_experiment_ids_json": [],
            "related_file_ids_json": [file_id] if file_id else [],
            "metadata_json": {"extracted_from": "experiment_memory"},
        }
        for label in sample_ids
    ]
    candidate = {
        "project_id": project_id,
        "experiment": experiment,
        "samples": samples,
        "groups": groups,
        "controls": groups["control_groups"] + groups["positive_controls"] + groups["negative_controls"],
        "concentrations": concentrations,
        "time_points": time_points,
        "cell_lines": cell_lines,
        "organisms": organisms,
        "instruments": instruments,
        "assays": assays,
        "raw_files": [file_id] if file_id else [],
        "processed_files": [],
        "statistical_methods": stats,
        "key_results": [result_summary] if result_summary else [],
        "conclusion": conclusion or None,
        "limitations": limitations,
        "next_steps": next_steps,
        "decision": decision_text or None,
        "failure": failure_text or None,
        "confidence": round(confidence, 2),
        "needs_review": confidence < 0.65 or bool(conclusion or decision_text),
    }
    if candidate["needs_review"]:
        enqueue_review(
            agent_root,
            {
                "user_id": "local_user",
                "group_id": "",
                "candidate": candidate,
                "reason": "experiment extraction confidence is low or the candidate may supersede conclusions/decisions",
                "confidence": candidate["confidence"],
            },
        )
    return candidate


def list_memory_review_items(agent_root: Path, project_id: str = "", status: str = "pending") -> list[dict[str, Any]]:
    items = list_review_queue(agent_root, user_id="", group_id="", status=status)
    if not project_id:
        return items
    filtered = []
    for item in items:
        candidate = item.get("candidate") or {}
        if clean(candidate.get("project_id")) == project_id or clean((candidate.get("experiment") or {}).get("project_id")) == project_id:
            filtered.append(item)
    return filtered


def validate_research_answer(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    project_id = clean(payload.get("project_id"))
    answer_text = clean(payload.get("answer_text") or payload.get("draft") or payload.get("text"))
    if not project_id or not answer_text:
        raise ValueError("project_id and answer_text are required")
    context = build_research_memory_context(agent_root, {"project_id": project_id, "query": clean(payload.get("query")) or "project summary", "limit": 30})
    structured = context["structured_context"]
    experiments = structured["experiments"]
    failures = structured["failures"]
    decisions = structured["decisions"]
    samples = structured["samples"]
    files = structured["data_files"]

    known_experiment_titles = {clean(item.get("title")).lower() for item in experiments if clean(item.get("title"))}
    known_sample_codes = {clean(item.get("sample_code") or item.get("sample_id")).lower() for item in samples if clean(item.get("sample_code") or item.get("sample_id"))}
    known_file_names = {clean(item.get("original_filename") or item.get("filename")).lower() for item in files if clean(item.get("original_filename") or item.get("filename"))}
    hallucinated_facts: list[str] = []

    for mentioned in re.findall(r"\b(?:Experiment|Sample|File)\s+[A-Za-z0-9_.-]+\b", answer_text, re.IGNORECASE):
        lowered = clean(mentioned).lower()
        if lowered.startswith("experiment ") and lowered.replace("experiment ", "") not in " ".join(sorted(known_experiment_titles)):
            hallucinated_facts.append(mentioned)
        if lowered.startswith("sample ") and lowered.replace("sample ", "") not in known_sample_codes:
            hallucinated_facts.append(mentioned)
        if lowered.startswith("file ") and lowered.replace("file ", "") not in known_file_names:
            hallucinated_facts.append(mentioned)

    ignored_memory = []
    if failures and (
        not re.search(r"\b(fail|failure|negative|limitation|risk|abnormal)\b", answer_text, re.IGNORECASE)
        or re.search(r"\b(?:no|without)\s+fail(?:ure|ures)?\b", answer_text, re.IGNORECASE)
    ):
        ignored_memory.append("Existing failure or negative-result memory is not acknowledged.")
    if experiments and not re.search(r"\b(experiment|assay|dataset|file)\b", answer_text, re.IGNORECASE):
        ignored_memory.append("Completed experiments are not referenced.")

    conflicts_with_active_decision = []
    for decision in decisions:
        decision_text = clean(decision.get("decision_text"))
        if not decision_text:
            continue
        if re.search(r"\bdo not\b", decision_text, re.IGNORECASE):
            phrase = decision_text.split("do not", 1)[-1].strip().lower()
            if phrase and phrase in answer_text.lower():
                conflicts_with_active_decision.append(decision_text)

    issues = []
    if hallucinated_facts:
        issues.append("Answer references experiments, samples, or files that are not present in active project memory.")
    if ignored_memory:
        issues.append("Answer omits relevant active project memory.")
    if conflicts_with_active_decision:
        issues.append("Answer conflicts with an active project decision.")
    if re.search(r"\bproves\b", answer_text, re.IGNORECASE) and re.search(r"\b(preliminary|draft|weak)\b", context["context_text"], re.IGNORECASE):
        issues.append("Answer upgrades preliminary evidence into a final conclusion.")
    if re.search(r"\bp\s?[<=>]\s?0\.\d+", answer_text, re.IGNORECASE):
        mentioned_file = any(name in answer_text.lower() for name in known_file_names)
        if not mentioned_file:
            issues.append("Statistical statements are present without an explicit supporting data file.")

    required_revision = ""
    if issues:
        required_revision = "Revise the answer to cite active experiments, mention relevant failures, respect active decisions, and separate project data from literature evidence."
    return {
        "is_valid": not issues,
        "issues": issues,
        "hallucinated_facts": hallucinated_facts,
        "ignored_memory": ignored_memory,
        "conflicts_with_active_decision": conflicts_with_active_decision,
        "required_revision": required_revision,
    }
