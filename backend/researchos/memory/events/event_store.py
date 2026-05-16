from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.researchos.memory.memory_config import append_jsonl, ensure_memoryos_dirs, read_jsonl, safe_project_id, write_json
from backend.researchos.memory.memory_event import MemoryEvent, event_from_dict, event_to_dict, redact_sensitive_event_payload, validate_memory_event


def _event_path(project_id: str | None) -> Path:
    dirs = ensure_memoryos_dirs()
    return dirs["events"] / safe_project_id(project_id) / "events.jsonl"


def append_event(event: MemoryEvent) -> dict[str, Any]:
    event = redact_sensitive_event_payload(event)
    validation = validate_memory_event(event)
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]))
    payload = event_to_dict(event)
    append_jsonl(_event_path(event.project_id), payload)
    return payload


def _all_event_paths() -> list[Path]:
    dirs = ensure_memoryos_dirs()
    return list(dirs["events"].glob("*/events.jsonl"))


def load_event(event_id: str) -> dict[str, Any]:
    for path in _all_event_paths():
        for row in read_jsonl(path):
            if row.get("event_id") == event_id:
                return row
    raise KeyError(f"memory event not found: {event_id}")


def list_events(project_id: str | None = None, task_id: str | None = None, event_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    paths = [_event_path(project_id)] if project_id else _all_event_paths()
    rows: list[dict[str, Any]] = []
    for path in paths:
        for row in read_jsonl(path):
            if task_id and row.get("task_id") != task_id:
                continue
            if event_type and row.get("event_type") != event_type:
                continue
            rows.append(row)
    return sorted(rows, key=lambda item: item.get("created_at", ""), reverse=True)[:limit]


def replay_events(project_id: str, since: str | None = None) -> list[dict[str, Any]]:
    rows = read_jsonl(_event_path(project_id))
    if since:
        rows = [row for row in rows if str(row.get("created_at", "")) >= since]
    return rows


def export_events(project_id: str, output_path: str) -> dict[str, Any]:
    rows = replay_events(project_id)
    path = Path(output_path)
    write_json(path, rows)
    return {"project_id": project_id, "output_path": str(path), "count": len(rows)}

