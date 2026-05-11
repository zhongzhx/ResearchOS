from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from backend.researchos.agents.agent_protocol import TaskSpec
from backend.researchos.skills.pipeline_registry import load_skill_catalog, resolve_skill_path

from .runtime_adapter import default_agent_root, import_research_os_mvp


ACTIVE_STATUSES = {"active", "enabled"}
INACTIVE_STATUSES = {"pending_review", "draft", "rejected", "deprecated", "disabled", "broken", "duplicate"}


def _root(agent_root: Path | None = None) -> Path:
    return agent_root or default_agent_root()


def load_skill_registry(agent_root: Path | None = None) -> dict[str, dict[str, Any]]:
    ros = import_research_os_mvp()
    skills = ros.list_skills(_root(agent_root), include_disabled=True)
    registry: dict[str, dict[str, Any]] = {}
    for skill in skills:
        registry[str(skill.get("skill_id"))] = skill
        registry[str(skill.get("skill_name"))] = skill
        if skill.get("source_path"):
            registry[str(skill.get("source_path")).replace("\\", "/")] = skill
    for skill_id, row in load_skill_catalog().items():
        catalog_row = {
            "skill_id": skill_id,
            "skill_name": skill_id,
            "status": row.get("status"),
            "source_path": row.get("canonical_path"),
            "canonical_path": row.get("canonical_path"),
            "catalog": row,
        }
        registry.setdefault(skill_id, catalog_row)
        registry.setdefault(str(row.get("canonical_path") or ""), catalog_row)
        for legacy in row.get("legacy_paths", []):
            registry.setdefault(str(legacy).replace("\\", "/"), catalog_row)
    return registry


def resolve_required_skill(skill_name: str, agent_root: Path | None = None) -> dict[str, Any]:
    registry = load_skill_registry(agent_root)
    key = str(skill_name or "").replace("\\", "/")
    skill = registry.get(key)
    canonical_path = resolve_skill_path(key)
    if not skill:
        catalog = load_skill_catalog()
        for row in catalog.values():
            if row.get("canonical_path") == canonical_path:
                skill = {
                    "skill_id": row["skill_id"],
                    "skill_name": row["skill_id"],
                    "status": row.get("status"),
                    "source_path": row.get("canonical_path"),
                    "catalog": row,
                }
                break
    if not skill:
        raise KeyError(f"skill not found: {skill_name}")
    status = str(skill.get("status") or "").strip()
    if status in INACTIVE_STATUSES:
        raise PermissionError(f"skill is not active: {skill_name}")
    result = dict(skill)
    result["canonical_path"] = canonical_path or str(skill.get("canonical_path") or skill.get("source_path") or "")
    return result


def _is_active_skill(skill: dict[str, Any]) -> bool:
    status = str(skill.get("status") or "").strip()
    skill_id = str(skill.get("skill_id") or "")
    source_path = str(skill.get("source_path") or "")
    if status in ACTIVE_STATUSES:
        return True
    if status in INACTIVE_STATUSES:
        return False
    if skill_id.startswith("core_") or source_path:
        return status not in INACTIVE_STATUSES
    return False


def get_active_skill(skill_name: str, agent_root: Path | None = None) -> dict[str, Any]:
    registry = load_skill_registry(agent_root)
    skill = registry.get(skill_name) or registry.get(str(skill_name).replace("\\", "/"))
    if not skill:
        skill = resolve_required_skill(skill_name, agent_root=agent_root)
    if not _is_active_skill(skill):
        raise PermissionError(f"skill is not active: {skill_name}")
    return skill


def validate_required_skills(required_skills: list[str], agent_root: Path | None = None) -> dict[str, Any]:
    active: list[dict[str, Any]] = []
    inactive_or_missing: list[str] = []
    errors: list[str] = []
    for skill_name in required_skills or []:
        try:
            active.append(resolve_required_skill(skill_name, agent_root=agent_root))
        except Exception as exc:  # noqa: BLE001
            inactive_or_missing.append(skill_name)
            errors.append(str(exc))
    return {"valid": not inactive_or_missing, "active": active, "inactive_or_missing": inactive_or_missing, "errors": errors}


def _summarize_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key, value in (inputs or {}).items():
        if key in {"content", "text", "pdf_text", "raw_text"}:
            summary[key] = f"<text:{len(str(value))} chars>"
        elif key in {"file", "path", "file_path", "input_files"}:
            summary[key] = value
        else:
            summary[key] = value if isinstance(value, (str, int, float, bool, type(None))) else f"<{type(value).__name__}>"
    return summary


def call_skill(skill_name: str, inputs: dict[str, Any], task_spec: TaskSpec, agent_root: Path | None = None) -> dict[str, Any]:
    started = perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        skill = get_active_skill(skill_name, agent_root=agent_root)
        ros = import_research_os_mvp()
        payload = {
            **(inputs or {}),
            "project_id": task_spec.project_id or "",
            "task_id": task_spec.task_id,
            "task_type": task_spec.task_type,
            "user_message": task_spec.user_query,
            "context_scope": task_spec.context_scope,
            "context_source_ids": task_spec.context_source_ids,
            "input_object_refs": [{"type": "file", "id": path} for path in task_spec.input_files],
        }
        result = ros.run_skill(_root(agent_root), skill["skill_id"], project_id=task_spec.project_id or "", input_payload=payload)
        duration = perf_counter() - started
        output_refs = []
        skill_run = result.get("skill_run") if isinstance(result.get("skill_run"), dict) else {}
        if isinstance(skill_run.get("output_object_refs"), list):
            output_refs = skill_run["output_object_refs"]
        return {
            "ok": True,
            "skill_name": skill_name,
            "skill_id": skill["skill_id"],
            "skill_run_id": result.get("skill_run_id"),
            "output": result,
            "output_refs": output_refs,
            "logs": [
                f"skill:{skill_name}",
                f"input_summary:{_summarize_inputs(inputs)}",
                f"duration_seconds:{duration:.3f}",
            ],
            "errors": [],
            "started_at": started_at,
            "duration_seconds": duration,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "skill_name": skill_name,
            "output": {},
            "output_refs": [],
            "logs": [f"skill:{skill_name}", f"failed_after_seconds:{perf_counter() - started:.3f}"],
            "errors": [str(exc)],
            "started_at": started_at,
            "duration_seconds": perf_counter() - started,
        }
