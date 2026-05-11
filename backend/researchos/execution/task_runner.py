from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.researchos.agents.agent_protocol import TaskSpec

from .skill_dispatcher import call_skill, validate_required_skills
from .tool_dispatcher import call_tool


SUPPORTED_TASK_TYPES = {
    "literature_harvest": {"skills": ["core_keyword_research_harvest"], "tools": []},
    "pdf_to_evidence_matrix": {"skills": [], "tools": ["pdf_parser"]},
    "rag_question_answering": {"skills": [], "tools": ["rag_query"]},
    "data_analysis": {"skills": [], "tools": ["data_parser"]},
    "sop_generation": {"skills": [], "tools": ["report_writer"]},
    "report_generation": {"skills": [], "tools": ["file_writer"]},
    "generic_skill_task": {"skills": [], "tools": []},
    "kb_summary": {"skills": ["core_build_user_research_kb"], "tools": []},
    "research_planning": {"skills": [], "tools": []},
    "browser_research_learning": {"skills": ["browser-research-learning"], "tools": []},
    "research_route_planning": {"skills": ["plan-research-route", "ingest-research-evidence"], "tools": []},
    "protocol_to_sop": {"skills": ["protocol-extraction", "sop-generation"], "tools": []},
    "experiment_design": {"skills": ["design-experiment-matrix"], "tools": []},
    "data_analysis_to_narrative": {"skills": ["parse-scientific-data", "analyze-experiment-results", "result-narrative"], "tools": []},
    "failure_recovery": {"skills": ["failure-log", "diagnose-research-bottleneck"], "tools": []},
    "writing_review": {"skills": ["result-narrative", "peer-review-simulation"], "tools": []},
    "weekly_reporting": {"skills": ["weekly-research-report", "weekly-research-digest"], "tools": []},
    "entity_extraction": {"skills": ["extract-domain-entities", "ingest-research-evidence"], "tools": []},
    "nature_citation_support": {"skills": ["nature-citation"], "tools": []},
    "nature_figure_generation": {"skills": ["nature-figure"], "tools": []},
    "nature_academic_polishing": {"skills": ["nature-polishing"], "tools": []},
    "nature_data_availability": {"skills": ["nature-data"], "tools": []},
    "nature_reviewer_response": {"skills": ["nature-response"], "tools": []},
    "nature_paper_to_ppt": {"skills": ["nature-paper2ppt"], "tools": []},
}


def create_task_workspace(task_id: str, base_dir: str | Path | None = None) -> str:
    root = Path(base_dir or Path.cwd() / "data" / "execution_tasks")
    path = root / task_id
    path.mkdir(parents=True, exist_ok=True)
    return str(path.resolve())


def build_execution_plan(task_spec: TaskSpec) -> dict[str, Any]:
    if task_spec.task_type not in SUPPORTED_TASK_TYPES:
        return {"status": "failed", "error": f"unknown task_type: {task_spec.task_type}", "steps": [], "skills": [], "tools": []}
    defaults = SUPPORTED_TASK_TYPES[task_spec.task_type]
    skills = list(task_spec.required_skills or defaults.get("skills") or [])
    tools = [tool for tool in list(task_spec.allowed_tools or defaults.get("tools") or []) if tool not in set(task_spec.forbidden_tools or [])]
    steps = []
    steps.extend({"type": "skill", "name": skill} for skill in skills)
    steps.extend({"type": "tool", "name": tool} for tool in tools)
    return {"status": "ready", "task_type": task_spec.task_type, "steps": steps, "skills": skills, "tools": tools}


def run_execution_plan(plan: dict[str, Any], task_spec: TaskSpec, agent_root: Path | None = None) -> dict[str, Any]:
    if plan.get("status") != "ready":
        return {"ok": False, "error": plan.get("error") or "execution plan is not ready", "logs": [], "outputs": {}, "output_files": [], "sources": []}
    workspace = create_task_workspace(task_spec.task_id, task_spec.input_data.get("workspace_base_dir"))
    task_spec.input_data.setdefault("workspace_dir", workspace)
    logs: list[str] = [f"workspace:{workspace}"]
    errors: list[str] = []
    output_files: list[str] = []
    sources: list[dict[str, Any]] = []
    outputs: dict[str, Any] = {"workspace": workspace, "skill_results": [], "tool_results": []}

    skill_validation = validate_required_skills(plan.get("skills", []), agent_root=agent_root)
    if not skill_validation["valid"]:
        return {"ok": False, "error": "; ".join(skill_validation["errors"]), "logs": logs, "outputs": outputs, "output_files": output_files, "sources": sources}

    if not plan.get("steps") and task_spec.task_type in {"generic_skill_task", "research_planning"}:
        outputs["message"] = "No concrete tools were required for this minimal execution task."

    for step in plan.get("steps", []):
        if step.get("type") == "skill":
            result = call_skill(step["name"], {**task_spec.input_data, "context_package": task_spec.context_package}, task_spec, agent_root=agent_root)
            outputs["skill_results"].append(result)
            logs.extend(result.get("logs", []))
            errors.extend(result.get("errors", []))
            if result.get("skill_run_id"):
                outputs["skill_run_id"] = result.get("skill_run_id")
            if isinstance(result.get("output_refs"), list):
                sources.extend(result.get("output_refs"))
        elif step.get("type") == "tool":
            result = call_tool(step["name"], task_spec.input_data, task_spec)
            outputs["tool_results"].append(result)
            logs.extend(result.get("logs", []))
            if result.get("error"):
                errors.append(result["error"])
            output_files.extend(result.get("output_files") or [])
            if isinstance(result.get("sources"), list):
                sources.extend(result.get("sources") or [])
    return {"ok": not errors, "error": "; ".join(errors), "logs": logs, "outputs": outputs, "output_files": output_files, "sources": sources}


def collect_task_outputs(task_id: str, workspace_dir: str | Path | None = None, declared_output_files: list[str] | None = None) -> dict[str, Any]:
    files = [str(Path(path).resolve()) for path in (declared_output_files or []) if Path(path).exists()]
    workspace = Path(workspace_dir) if workspace_dir else Path.cwd() / "data" / "execution_tasks" / task_id
    if workspace.exists():
        files.extend(str(path.resolve()) for path in workspace.rglob("*") if path.is_file())
    unique = []
    seen = set()
    for path in files:
        if path not in seen:
            unique.append(path)
            seen.add(path)
    return {"output_files": unique, "workspace": str(workspace.resolve())}
