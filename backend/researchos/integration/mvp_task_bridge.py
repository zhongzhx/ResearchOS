from __future__ import annotations

from typing import Any

from backend.researchos.tasks import ResearchTaskStateStore, build_contract_from_task_spec
from backend.researchos.tasks.task_planner import build_goal
from backend.researchos.settings.secret_store import redact_secrets_in_obj


def _listify(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def persist_product_feature_lifecycle(feature_id: str, request_payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    project_id = str(request_payload.get("project_id") or result.get("project_id") or "demo_project")
    query = str(request_payload.get("user_query") or request_payload.get("query") or result.get("summary") or feature_id)
    task_id = str(result.get("task_id") or "")
    store = ResearchTaskStateStore()
    task = store.create_task(project_id, query, task_id=task_id or None)

    goal = build_goal(query, project_id, feature_id, {"feature_id": feature_id, "source": "mvp_product_bridge"})
    store.write_goal(task, goal)

    plan_lines = [
        f"# Product Feature Lifecycle: {feature_id}",
        "",
        f"- Project: {project_id}",
        f"- Status: {result.get('status') or 'partial'}",
        "- MVP runtime remains the HTTP and data trunk.",
        "- Unavailable fields are represented as null, empty, partial, or not_connected.",
    ]
    store.write_plan(task, "\n".join(plan_lines))

    contract = {
        "feature_id": feature_id,
        "project_id": project_id,
        "status_contract": "ready means real execution; partial/not_connected/disabled are explicit",
        "memory_gate": "evidence_promotion",
        "mvp_runtime_trunk": True,
    }
    store.write_contract(task, contract)

    execution = {
        "status": result.get("execution_status") or result.get("status") or "partial",
        "feature_id": feature_id,
        "summary": result.get("summary") or "",
        "result": result.get("result") or {},
    }
    store.write_execution(task, execution)
    store.write_artifacts(task, _listify(result.get("artifacts")))

    validation = result.get("validation_report") if isinstance(result.get("validation_report"), dict) else {}
    if not validation:
        validation = {
            "safe_to_return": True,
            "safe_to_promote": False,
            "required_human_review": True,
            "issues": result.get("warnings") or ["validation unavailable"],
        }
    store.write_validation(task, validation)

    memory_commit = result.get("memory_commit") or result.get("memory_update") or {"status": "not_connected", "reason": "memory commit unavailable"}
    if not isinstance(memory_commit, dict):
        memory_commit = {"status": "not_connected", "reason": "memory commit unavailable"}
    memory_commit.setdefault("memory_gate", "evidence_promotion")
    store.write_memory_commit(task, memory_commit)

    handoff = "\n".join(
        [
            f"# Handoff: {feature_id}",
            "",
            f"Status: {result.get('status') or 'partial'}",
            f"Summary: {result.get('summary') or 'unavailable'}",
            f"Unavailable: {', '.join(result.get('warnings') or []) if isinstance(result.get('warnings'), list) else 'none reported'}",
        ]
    )
    store.write_handoff(task, handoff)
    return redact_secrets_in_obj({"ok": True, "research_task_id": task.task_id, "research_task_dir": str(store.task_dir(task.task_id)), "research_task": task.to_dict()})
