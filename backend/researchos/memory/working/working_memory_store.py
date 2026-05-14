from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.researchos.memory.memory_config import ensure_memoryos_dirs, read_json, redact_payload, safe_project_id, utc_now_iso, write_json


def _path(project_id: str, conversation_id: str) -> Path:
    return ensure_memoryos_dirs()["working"] / safe_project_id(project_id) / f"{safe_project_id(conversation_id)}.json"


def _default(conversation_id: str, project_id: str) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "project_id": project_id,
        "current_task_id": "",
        "current_goal": "",
        "active_constraints": [],
        "current_plan": [],
        "open_questions": [],
        "recent_user_corrections": [],
        "pending_confirmation": None,
        "recent_messages": [],
        "last_agent_action": "",
        "updated_at": utc_now_iso(),
    }


def get_working_memory(conversation_id: str, project_id: str) -> dict[str, Any]:
    return read_json(_path(project_id, conversation_id), _default(conversation_id, project_id))


def update_working_memory(conversation_id: str, project_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    memory = get_working_memory(conversation_id, project_id)
    for key, value in (patch or {}).items():
        if key in {"conversation_id", "project_id"}:
            continue
        memory[key] = redact_payload(value, max_chars=4000)
    memory["updated_at"] = utc_now_iso()
    write_json(_path(project_id, conversation_id), memory)
    return memory


def append_recent_message(conversation_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = metadata or {}
    project_id = str(metadata.get("project_id") or "global")
    memory = get_working_memory(conversation_id, project_id)
    message = {
        "role": str(role),
        "content": redact_payload(str(content or ""), max_chars=4000),
        "metadata": redact_payload({key: value for key, value in metadata.items() if key != "project_id"}, max_chars=1000),
        "created_at": utc_now_iso(),
    }
    messages = list(memory.get("recent_messages") or [])
    messages.append(message)
    memory["recent_messages"] = messages[-20:]
    memory["updated_at"] = utc_now_iso()
    write_json(_path(project_id, conversation_id), memory)
    return memory


def set_current_task(conversation_id: str, task_id: str, project_id: str = "global") -> dict[str, Any]:
    return update_working_memory(conversation_id, project_id, {"current_task_id": task_id})


def clear_working_memory(conversation_id: str, reason: str | None = None, project_id: str = "global") -> dict[str, Any]:
    memory = _default(conversation_id, project_id)
    memory["last_agent_action"] = f"working_memory_cleared: {reason or ''}".strip()
    write_json(_path(project_id, conversation_id), memory)
    return memory


def compact_working_memory(conversation_id: str, max_items: int = 20, project_id: str = "global") -> dict[str, Any]:
    memory = get_working_memory(conversation_id, project_id)
    memory["recent_messages"] = list(memory.get("recent_messages") or [])[-max_items:]
    memory["current_plan"] = list(memory.get("current_plan") or [])[:max_items]
    memory["open_questions"] = list(memory.get("open_questions") or [])[:max_items]
    memory["updated_at"] = utc_now_iso()
    write_json(_path(project_id, conversation_id), memory)
    return memory

