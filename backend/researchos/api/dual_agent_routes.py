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
