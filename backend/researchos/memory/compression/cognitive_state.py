from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.researchos.brain.brain_page import brain_root
from backend.researchos.memory.memory_config import read_json, redact_payload, utc_now_iso, write_json
from backend.researchos.memory.semantic.semantic_memory_store import list_semantic_memories


def _path(project_id: str) -> Path:
    return brain_root() / "projects" / project_id / "cognitive_state.json"


def _default(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "current_goal": "",
        "active_tasks": [],
        "active_constraints": [],
        "key_entities": [],
        "working_hypotheses": [],
        "validated_claims": [],
        "open_questions": [],
        "recent_decisions": [],
        "blocked_items": [],
        "next_actions": [],
        "important_failures": [],
        "active_protocols": [],
        "high_value_artifacts": [],
        "last_updated_from": [],
        "updated_at": utc_now_iso(),
    }


def load_cognitive_state(project_id: str) -> dict[str, Any]:
    return read_json(_path(project_id), _default(project_id))


def update_cognitive_state(project_id: str, patch: dict[str, Any], source_ids: list[str] | None = None) -> dict[str, Any]:
    state = load_cognitive_state(project_id)
    for key, value in (patch or {}).items():
        if key == "project_id":
            continue
        state[key] = redact_payload(value, max_chars=4000)
    if source_ids:
        state["last_updated_from"] = sorted(set(list(state.get("last_updated_from") or []) + [str(item) for item in source_ids]))
    state["updated_at"] = utc_now_iso()
    write_json(_path(project_id), state)
    return state


def compile_cognitive_state_from_memories(project_id: str) -> dict[str, Any]:
    memories = list_semantic_memories(project_id, status="")
    state = _default(project_id)
    for item in memories:
        if item.get("status") not in {"active", "needs_review"}:
            continue
        entry = {"memory_id": item.get("memory_id"), "title": item.get("title"), "content": item.get("content"), "confidence": item.get("confidence")}
        mtype = item.get("memory_type")
        if mtype == "goal" and not state["current_goal"]:
            state["current_goal"] = item.get("content") or item.get("title") or ""
        elif mtype == "constraint":
            state["active_constraints"].append(entry)
        elif mtype == "hypothesis":
            state["working_hypotheses"].append(entry)
        elif mtype == "claim":
            if item.get("confidence") in {"medium", "high"}:
                state["validated_claims"].append(entry)
            else:
                state["working_hypotheses"].append(entry)
        elif mtype == "open_question":
            state["open_questions"].append(entry)
        elif mtype == "decision":
            state["recent_decisions"].append(entry)
        elif mtype == "failure":
            state["important_failures"].append(entry)
        elif mtype == "protocol":
            state["active_protocols"].append(entry)
        elif mtype in {"dataset", "report", "artifact_summary"}:
            state["high_value_artifacts"].append(entry)
        elif mtype == "next_action":
            state["next_actions"].append(entry)
        state["key_entities"].extend(item.get("entities") or [])
    state["key_entities"] = sorted(set(state["key_entities"]))[:30]
    state["last_updated_from"] = sorted({item.get("memory_id") for item in memories if item.get("memory_id")})
    state["updated_at"] = utc_now_iso()
    write_json(_path(project_id), state)
    return state


def refresh_cognitive_state_after_task(project_id: str, task_id: str) -> dict[str, Any]:
    state = compile_cognitive_state_from_memories(project_id)
    state["last_updated_from"] = sorted(set(list(state.get("last_updated_from") or []) + [task_id]))
    state["updated_at"] = utc_now_iso()
    write_json(_path(project_id), state)
    return state


def summarize_cognitive_state_for_context(project_id: str, max_items: int = 20) -> dict[str, Any]:
    state = load_cognitive_state(project_id)
    summary = {"project_id": project_id, "current_goal": state.get("current_goal"), "updated_at": state.get("updated_at")}
    for key in [
        "active_tasks",
        "active_constraints",
        "key_entities",
        "working_hypotheses",
        "validated_claims",
        "open_questions",
        "recent_decisions",
        "blocked_items",
        "next_actions",
        "important_failures",
        "active_protocols",
        "high_value_artifacts",
    ]:
        value = state.get(key) or []
        summary[key] = value[:max_items] if isinstance(value, list) else value
    return summary

