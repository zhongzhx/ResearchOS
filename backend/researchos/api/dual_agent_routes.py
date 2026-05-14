from __future__ import annotations

from typing import Any

try:
    from fastapi import APIRouter
except Exception:  # pragma: no cover - FastAPI may not be installed in tests.
    APIRouter = None  # type: ignore

from backend.researchos.agents.brain_agent import ResearchBrainAgent
from backend.researchos.agents.coordinator import AgentCoordinator
from backend.researchos.agents.execution_agent import ResearchExecutionAgent
from backend.researchos.brain.skill_registry_review import activate_skill, list_pending_skills, reject_skill
from backend.researchos.demo.dual_agent_demo import run_demo_pdf_evidence_flow
from backend.researchos.execution.runtime_adapter import default_agent_root
from backend.researchos.skills.pipeline_registry import load_skill_catalog, list_pipelines, route_query_to_pipeline
from backend.researchos.skills.resolver_checker import run_resolver_smoke_tests
from backend.researchos.memory.compression.cognitive_state import load_cognitive_state, refresh_cognitive_state_after_task
from backend.researchos.memory.episodic.episodic_memory_store import list_recent_episodes
from backend.researchos.memory.events.event_store import list_events
from backend.researchos.memory.governance.memory_manager import run_memory_maintenance
from backend.researchos.memory.learning.autonomous_learning_loop import run_autonomous_learning_check
from backend.researchos.memory.learning.memory_health_scanner import scan_memory_health
from backend.researchos.memory.memory_config import redact_payload
from backend.researchos.memory.retrieval.memory_retriever import retrieve_memories
from backend.researchos.memory.semantic.semantic_memory_store import list_semantic_memories
from backend.researchos.memory.working.working_memory_store import get_working_memory


router = APIRouter() if APIRouter else None


def coordinator_for_request() -> AgentCoordinator:
    agent_root = default_agent_root()
    execution = ResearchExecutionAgent(agent_root=agent_root)
    brain = ResearchBrainAgent(execution_agent=execution, agent_root=agent_root)
    return AgentCoordinator(brain_agent=brain, execution_agent=execution)


def coordinator_run(payload: dict[str, Any]) -> dict[str, Any]:
    return coordinator_for_request().run_full_cycle(str(payload.get("user_query") or ""), project_id=payload.get("project_id"))


def process_skillrun(skillrun_id: str) -> dict[str, Any]:
    return coordinator_for_request().process_completed_skillrun(skillrun_id)


def pending_skills() -> list[dict[str, Any]]:
    return list_pending_skills()


def activate_generated_skill(skill_name: str) -> dict[str, Any]:
    return activate_skill(skill_name)


def reject_generated_skill(skill_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return reject_skill(skill_name, str(payload.get("reason") or "rejected by reviewer"))


def resolver_check() -> dict[str, Any]:
    return run_resolver_smoke_tests()


def skill_catalog() -> dict[str, Any]:
    skills = list(load_skill_catalog().values())
    return {"ok": True, "count": len(skills), "skills": skills}


def pipeline_registry() -> dict[str, Any]:
    pipelines = list_pipelines()
    return {"ok": True, "count": len(pipelines), "pipelines": pipelines}


def route_skill_query(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("user_query") or payload.get("query") or payload.get("message") or "")
    pipeline = route_query_to_pipeline(query)
    return {"ok": True, "query": query, "pipeline": pipeline}


def memory_working(payload: dict[str, Any]) -> dict[str, Any]:
    project_id = str(payload.get("project_id") or "global")
    conversation_id = str(payload.get("conversation_id") or project_id)
    return {"ok": True, "working_memory": redact_payload(get_working_memory(conversation_id, project_id))}


def memory_cognitive_state(payload: dict[str, Any]) -> dict[str, Any]:
    project_id = str(payload.get("project_id") or "global")
    return {"ok": True, "cognitive_state": redact_payload(load_cognitive_state(project_id))}


def memory_cognitive_state_refresh(payload: dict[str, Any]) -> dict[str, Any]:
    project_id = str(payload.get("project_id") or "global")
    task_id = str(payload.get("task_id") or "manual_refresh")
    return {"ok": True, "cognitive_state": redact_payload(refresh_cognitive_state_after_task(project_id, task_id))}


def memory_episodes(payload: dict[str, Any]) -> dict[str, Any]:
    project_id = str(payload.get("project_id") or "global")
    return {"ok": True, "episodes": redact_payload(list_recent_episodes(project_id, limit=int(payload.get("limit") or 20)))}


def memory_items(payload: dict[str, Any]) -> dict[str, Any]:
    project_id = str(payload.get("project_id") or "global")
    memory_type = payload.get("type") or payload.get("memory_type")
    layer = payload.get("layer")
    items = list_semantic_memories(project_id, memory_type=str(memory_type) if memory_type else None, status=str(payload.get("status") or "active"))
    if layer:
        items = [item for item in items if item.get("memory_layer") == layer]
    return {"ok": True, "items": redact_payload(items)}


def memory_search(payload: dict[str, Any]) -> dict[str, Any]:
    project_id = str(payload.get("project_id") or "global")
    query = str(payload.get("query") or "")
    types = payload.get("memory_types")
    results = retrieve_memories(project_id, query, memory_types=types if isinstance(types, list) else None, top_k=int(payload.get("top_k") or 20))
    return {"ok": True, "results": redact_payload(results)}


def memory_health(payload: dict[str, Any]) -> dict[str, Any]:
    project_id = str(payload.get("project_id") or "global")
    return {"ok": True, "health": redact_payload(scan_memory_health(project_id))}


def memory_maintenance_run(payload: dict[str, Any]) -> dict[str, Any]:
    project_id = str(payload.get("project_id") or "global")
    dry_run = bool(payload.get("dry_run", True))
    if dry_run:
        return {"ok": True, "dry_run": True, "health": redact_payload(scan_memory_health(project_id))}
    return {"ok": True, "dry_run": False, "maintenance": redact_payload(run_memory_maintenance(project_id))}


def memory_events(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "events": redact_payload(
            list_events(
                project_id=payload.get("project_id"),
                task_id=payload.get("task_id"),
                event_type=payload.get("event_type"),
                limit=int(payload.get("limit") or 100),
            )
        ),
    }


def memory_autonomous_learning_check(payload: dict[str, Any]) -> dict[str, Any]:
    project_id = str(payload.get("project_id") or "global")
    return {"ok": True, "autonomous_learning": redact_payload(run_autonomous_learning_check(project_id, dry_run=bool(payload.get("dry_run", True))))}


def demo_dual_agent(project_id: str = "demo_project") -> dict[str, Any]:
    demo = run_demo_pdf_evidence_flow(project_id=project_id)
    execution_result = demo.get("execution_result") or {}
    resolver_health = demo.get("resolver_health") or {}
    pending_skill = demo.get("pending_skill") or {}
    return {
        "ok": bool(demo.get("ok")),
        "task_type": (demo.get("task_spec") or {}).get("task_type"),
        "execution_status": execution_result.get("status"),
        "skillrun_id": execution_result.get("skillrun_id"),
        "memory_pages": (demo.get("brain_memory") or {}).get("written") or [],
        "pending_skill": {
            "name": pending_skill.get("name"),
            "status": pending_skill.get("status"),
            "path": pending_skill.get("skill_dir"),
        },
        "resolver_entries": resolver_health.get("resolver_entries"),
        "details": demo,
    }


async def coordinator_run_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    return coordinator_run(payload)


async def process_skillrun_endpoint(skillrun_id: str) -> dict[str, Any]:
    return process_skillrun(skillrun_id)


async def pending_skills_endpoint() -> list[dict[str, Any]]:
    return pending_skills()


async def activate_generated_skill_endpoint(skill_name: str) -> dict[str, Any]:
    return activate_generated_skill(skill_name)


async def reject_generated_skill_endpoint(skill_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return reject_generated_skill(skill_name, payload)


async def resolver_check_endpoint() -> dict[str, Any]:
    return resolver_check()


async def skill_catalog_endpoint() -> dict[str, Any]:
    return skill_catalog()


async def pipeline_registry_endpoint() -> dict[str, Any]:
    return pipeline_registry()


async def route_skill_query_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    return route_skill_query(payload)


async def demo_dual_agent_endpoint(project_id: str = "demo_project") -> dict[str, Any]:
    return demo_dual_agent(project_id=project_id)


async def memory_search_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    return memory_search(payload)


if router is not None:
    router.post("/api/agents/coordinator/run")(coordinator_run_endpoint)
    router.post("/api/brain/skillrun/{skillrun_id}/process")(process_skillrun_endpoint)
    router.get("/api/self-evolution/pending-skills")(pending_skills_endpoint)
    router.post("/api/self-evolution/skills/{skill_name}/activate")(activate_generated_skill_endpoint)
    router.post("/api/self-evolution/skills/{skill_name}/reject")(reject_generated_skill_endpoint)
    router.get("/api/skills/resolver/check")(resolver_check_endpoint)
    router.get("/api/skills/catalog")(skill_catalog_endpoint)
    router.get("/api/skills/pipelines")(pipeline_registry_endpoint)
    router.post("/api/skills/route")(route_skill_query_endpoint)
    router.get("/api/demo/dual-agent")(demo_dual_agent_endpoint)
    router.post("/api/memory/search")(memory_search_endpoint)
