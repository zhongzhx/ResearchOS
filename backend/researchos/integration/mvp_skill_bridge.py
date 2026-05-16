from __future__ import annotations

from typing import Any

from backend.researchos.brain.skill_registry_review import activate_skill, list_pending_skills, reject_skill
from backend.researchos.execution.runtime_adapter import default_agent_root, import_research_os_mvp
from backend.researchos.skills.pipeline_registry import load_skill_catalog, list_pipelines, route_query_to_pipeline
from backend.researchos.skills.resolver_checker import run_resolver_smoke_tests
from backend.researchos.settings.secret_store import redact_secrets_in_obj


def get_skill_catalog() -> dict[str, Any]:
    supplemental = list(load_skill_catalog().values())
    try:
        ros = import_research_os_mvp()
        mvp_skills = ros.list_skills(default_agent_root(), include_disabled=True)
    except Exception:
        return {"ok": True, "source": "backend_supplemental", "count": len(supplemental), "skills": redact_secrets_in_obj(supplemental)}
    seen = {str(item.get("skill_id") or item.get("id") or item.get("name") or "") for item in mvp_skills if isinstance(item, dict)}
    merged = list(mvp_skills)
    for skill in supplemental:
        key = str(skill.get("skill_id") or skill.get("id") or skill.get("name") or "")
        if key and key not in seen:
            merged.append({**skill, "source": "backend_supplemental"})
            seen.add(key)
    return {"ok": True, "source": "mvp_runtime_with_backend_supplements", "count": len(merged), "skills": redact_secrets_in_obj(merged)}


def get_pipeline_registry() -> dict[str, Any]:
    pipelines = list_pipelines()
    return {"ok": True, "count": len(pipelines), "pipelines": redact_secrets_in_obj(pipelines)}


def route_skill_query(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("user_query") or payload.get("query") or payload.get("message") or "")
    project_id = str(payload.get("project_id") or "")
    try:
        ros = import_research_os_mvp()
        routing = ros.simulate_prompt_routing(
            default_agent_root(),
            {
                "user_message": query,
                "message": query,
                "query": query,
                "project_id": project_id,
                "task_type": payload.get("task_type") or "",
                "skill_name": payload.get("skill_name") or "",
                "skill_id": payload.get("skill_id") or "",
            },
        )
        task_type = str(routing.get("task_type") or "")
        pipeline = {
            "pipeline_name": task_type,
            "intent": task_type,
            "selected_skill": routing.get("resolved_skill_name") or "",
            "prompt_policy": routing.get("prompt_policy") or "",
            "source": "mvp_prompt_router",
        }
        return {
            "ok": True,
            "source": "mvp_runtime",
            "query": query,
            "pipeline": redact_secrets_in_obj(pipeline),
            "mvp_prompt_routing": redact_secrets_in_obj(routing),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "source": "backend_supplemental",
            "query": query,
            "pipeline": redact_secrets_in_obj(route_query_to_pipeline(query)),
            "mvp_error": str(exc),
        }


def resolver_check() -> dict[str, Any]:
    return redact_secrets_in_obj(run_resolver_smoke_tests())


def pending_skills() -> list[dict[str, Any]]:
    return redact_secrets_in_obj(list_pending_skills())


def activate_pending_skill(skill_name: str) -> dict[str, Any]:
    return redact_secrets_in_obj(activate_skill(skill_name))


def reject_pending_skill(skill_name: str, reason: str) -> dict[str, Any]:
    return redact_secrets_in_obj(reject_skill(skill_name, reason))
