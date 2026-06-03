from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.researchos.execution.runtime_adapter import default_agent_root, import_research_os_mvp
from backend.researchos.memory.memory_config import append_jsonl, ensure_memoryos_dirs, read_json, read_jsonl, safe_project_id, utc_now_iso, write_jsonl
from backend.researchos.tasks.task_state_store import default_task_root


def _require_project_id(project_id: str | None) -> str:
    value = str(project_id or "").strip()
    if not value:
        raise ValueError("project_id is required")
    return value


def _path(project_id: str) -> Path:
    return ensure_memoryos_dirs()["episodic"] / safe_project_id(_require_project_id(project_id)) / "episodes.jsonl"


def _parse_json_field(row: dict[str, Any], key: str) -> Any:
    if key in row and not key.endswith("_json"):
        return row.get(key)
    raw = row.get(f"{key}_json")
    if isinstance(raw, str) and raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return row.get(key) or {}


def _upsert_episode(project_id: str, episode: dict[str, Any]) -> dict[str, Any]:
    path = _path(project_id)
    rows = [row for row in read_jsonl(path) if row.get("episode_id") != episode["episode_id"]]
    rows.append(episode)
    write_jsonl(path, rows)
    return episode


def create_episode_from_task(task_id: str, project_id: str = "", task_dir: Path | None = None) -> dict[str, Any]:
    task_dir = Path(task_dir) if task_dir else default_task_root() / task_id
    task = read_json(task_dir / "task.json", {"task_id": task_id, "project_id": "", "user_query": ""})
    execution = read_json(task_dir / "execution_result.json", {})
    validation = read_json(task_dir / "validation_report.json", {})
    artifacts = read_json(task_dir / "artifacts.json", [])
    project_id = _require_project_id(project_id or task.get("project_id") or execution.get("project_id"))
    status = str(execution.get("status") or task.get("status") or "")
    outcome = "failed" if status == "failed" else ("partial_success" if status == "partial_success" else "success")
    unresolved = list(execution.get("unresolved_items") or [])
    unresolved.extend(execution.get("errors") or [])
    episode = {
        "episode_id": f"ep_{uuid4().hex[:16]}",
        "project_id": project_id,
        "task_id": task_id,
        "skillrun_id": execution.get("skillrun_id") or "",
        "title": task.get("user_query") or execution.get("summary") or f"Task {task_id}",
        "goal": task.get("goal") or task.get("user_query") or "",
        "pipeline": execution.get("structured_outputs", {}).get("execution_plan", {}).get("pipeline", "") if isinstance(execution.get("structured_outputs"), dict) else "",
        "skills_used": execution.get("structured_outputs", {}).get("execution_plan", {}).get("steps", []) if isinstance(execution.get("structured_outputs"), dict) else [],
        "artifacts": artifacts,
        "outcome": outcome,
        "validation_summary": validation,
        "unresolved_items": unresolved,
        "user_feedback": [],
        "memory_commit_summary": read_json(task_dir / "memory_commit.json", {}),
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "tags": ["task_episode", outcome],
        "memory_ids": [],
    }
    return _upsert_episode(project_id, episode)


def create_episode_from_skillrun(skillrun_id: str, skillrun: dict[str, Any] | None = None) -> dict[str, Any]:
    run = skillrun
    if run is None:
        ros = import_research_os_mvp()
        run = ros.get_skill_run(default_agent_root(), skillrun_id)
    input_payload = _parse_json_field(run, "input_payload")
    output_payload = _parse_json_field(run, "output_payload")
    output_refs = _parse_json_field(run, "output_object_refs")
    logs = _parse_json_field(run, "logs")
    project_id = _require_project_id(run.get("project_id") or input_payload.get("project_id"))
    status = str(run.get("status") or output_payload.get("status") or "")
    outcome = "failed" if status == "failed" else ("partial_success" if status == "partial_success" else "success")
    episode = {
        "episode_id": f"ep_{uuid4().hex[:16]}",
        "project_id": project_id,
        "task_id": input_payload.get("task_id") or output_payload.get("task_id") or "",
        "skillrun_id": skillrun_id,
        "title": input_payload.get("user_query") or input_payload.get("message") or run.get("skill_name") or f"SkillRun {skillrun_id}",
        "goal": input_payload.get("objective") or input_payload.get("user_query") or "",
        "pipeline": input_payload.get("pipeline_name") or input_payload.get("task_type") or "",
        "skills_used": [run.get("skill_id") or run.get("skill_name")],
        "artifacts": output_refs or [],
        "outcome": outcome,
        "validation_summary": output_payload.get("validation_report") if isinstance(output_payload, dict) else {},
        "unresolved_items": output_payload.get("unresolved_items", []) if isinstance(output_payload, dict) else [],
        "user_feedback": [],
        "memory_commit_summary": output_payload.get("summary") if isinstance(output_payload, dict) else "",
        "created_at": run.get("created_at") or utc_now_iso(),
        "updated_at": utc_now_iso(),
        "tags": ["skillrun_episode", outcome],
        "memory_ids": [],
        "logs_summary": list(logs or [])[:5] if isinstance(logs, list) else [],
    }
    return _upsert_episode(project_id, episode)


def list_recent_episodes(project_id: str, limit: int = 20) -> list[dict[str, Any]]:
    rows = read_jsonl(_path(project_id))
    return sorted(rows, key=lambda item: item.get("updated_at", ""), reverse=True)[:limit]


def search_episodes(project_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
    terms = [term.lower() for term in str(query or "").split() if term.strip()]
    scored = []
    for row in read_jsonl(_path(project_id)):
        text = json.dumps(row, ensure_ascii=False).lower()
        score = sum(1 for term in terms if term in text)
        if score:
            item = dict(row)
            item["score"] = score
            scored.append(item)
    return sorted(scored, key=lambda item: item.get("score", 0), reverse=True)[:limit]


def link_episode_to_memory_items(episode_id: str, memory_ids: list[str], project_id: str) -> dict[str, Any]:
    path = _path(project_id)
    rows = read_jsonl(path)
    for row in rows:
        if row.get("episode_id") == episode_id:
            row["memory_ids"] = sorted(set(list(row.get("memory_ids") or []) + list(memory_ids or [])))
            row["updated_at"] = utc_now_iso()
            write_jsonl(path, rows)
            return row
    raise KeyError(f"episode not found: {episode_id}")

