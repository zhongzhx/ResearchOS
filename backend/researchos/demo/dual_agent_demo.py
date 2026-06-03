from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.researchos.agents.agent_protocol import TaskSpec
from backend.researchos.agents.brain_agent import ResearchBrainAgent
from backend.researchos.agents.coordinator import AgentCoordinator
from backend.researchos.agents.execution_agent import ResearchExecutionAgent
from backend.researchos.execution.runtime_adapter import default_agent_root, import_research_os_mvp


def _ensure_project(project_id: str) -> str:
    project_id = str(project_id or "").strip()
    if not project_id:
        raise ValueError("project_id is required")
    ros = import_research_os_mvp()
    agent_root = default_agent_root()
    try:
        ros.get_project_detail(agent_root, project_id)
        return project_id
    except Exception:
        project = ros.create_project(agent_root, {"id": project_id, "title": project_id, "research_area": "dual agent demo"})
        return project["id"]


def run_demo_pdf_evidence_flow(project_id: str) -> dict[str, Any]:
    project_id = _ensure_project(project_id)
    agent_root = default_agent_root()
    execution = ResearchExecutionAgent(agent_root=agent_root)
    brain = ResearchBrainAgent(execution_agent=execution, agent_root=agent_root)
    coordinator = AgentCoordinator(brain_agent=brain, execution_agent=execution)
    response = coordinator.run_full_cycle("Create a demo evidence summary report", project_id=project_id)
    processing = response.get("post_task_processing") or {}
    return {
        "ok": bool(response.get("ok")),
        "project_id": project_id,
        "task_spec": response.get("task_spec"),
        "execution_result": response.get("execution_result"),
        "brain_decision": response.get("brain_decision"),
        "brain_memory": processing.get("memory_write"),
        "research_graph": processing.get("research_graph"),
        "context_index": processing.get("context_index"),
        "pending_skill": processing.get("pending_skill"),
        "resolver_health": response.get("resolver_health"),
    }
