from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.researchos.memory.events.event_store import append_event
from backend.researchos.memory.memory_config import append_jsonl, ensure_memoryos_dirs, read_jsonl, safe_project_id, utc_now_iso
from backend.researchos.memory.memory_event import create_memory_event
from backend.researchos.memory.semantic.semantic_memory_store import load_semantic_memory, update_semantic_memory


def _path(project_id: str) -> Path:
    return ensure_memoryos_dirs()["archives"] / safe_project_id(project_id) / "archived_memory.jsonl"


def archive_memory(memory_id: str, reason: str) -> dict[str, Any]:
    item = load_semantic_memory(memory_id)
    archived = update_semantic_memory(memory_id, {"status": "archived", "provenance_append": {"archive_reason": reason, "archived_at": utc_now_iso()}})
    append_jsonl(_path(str(item.get("project_id"))), archived)
    append_event(create_memory_event("memory_archived", project_id=item.get("project_id"), source_id=memory_id, source_type="brain_page", payload={"reason": reason}))
    return archived


def restore_archived_memory(memory_id: str, reason: str) -> dict[str, Any]:
    item = load_semantic_memory(memory_id)
    return update_semantic_memory(memory_id, {"status": "active", "provenance_append": {"restore_reason": reason, "restored_at": utc_now_iso()}})


def list_archived_memories(project_id: str) -> list[dict[str, Any]]:
    return read_jsonl(_path(project_id))

