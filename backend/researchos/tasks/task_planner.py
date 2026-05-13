from __future__ import annotations

from typing import Any

from backend.researchos.agents.agent_protocol import TaskSpec


def build_goal(user_query: str, project_id: str | None, intent: str, compiled_context: dict[str, Any]) -> dict[str, Any]:
    warnings = compiled_context.get("warnings") if isinstance(compiled_context, dict) else []
    return {
        "user_intent": intent,
        "research_objective": user_query,
        "success_criteria": [
            "A TaskSpec is planned from minimal execution context.",
            "ExecutionResult and artifacts are persisted in the task package.",
            "Outputs are validated before promotion or handoff.",
            "Memory commit records accepted and rejected items.",
        ],
        "scope_in": [user_query],
        "scope_out": [
            "Unrelated project files",
            "Full hidden agent memory",
            "Direct long-term memory writes from execution",
        ],
        "user_constraints": [],
        "assumptions": [
            f"Project id is {project_id or 'not provided'}.",
            "Existing TaskSpec, ExecutionResult, and BrainDecision remain authoritative protocol objects.",
        ],
        "unknowns": list(warnings or []),
    }


def _bullets(items: list[Any]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def build_plan_markdown(task_spec: TaskSpec, pipeline: dict[str, Any]) -> str:
    selected_pipeline = str(pipeline.get("pipeline_name") or task_spec.input_data.get("pipeline_name") or task_spec.task_type)
    control_skills = task_spec.input_data.get("control_skills") if isinstance(task_spec.input_data, dict) else {}
    stages = [
        "Create auditable ResearchTask package.",
        "Plan with Research Brain and persist plan.md.",
        "Build execution contract from TaskSpec.",
        "Run Execution Agent with execution_minimal context.",
        "Collect artifacts and validation report.",
        "Promote evidence through Brain memory gates.",
        "Compose handoff for user and next agent.",
    ]
    risk_points = list(task_spec.safety_constraints or [])
    if control_skills:
        risk_points.append(f"Control skills required: {control_skills}")
    return "\n".join(
        [
            "# Research Task Plan",
            "",
            f"selected_pipeline: {selected_pipeline}",
            "",
            "## required_skills",
            _bullets(list(task_spec.required_skills or [])),
            "",
            "## stages",
            _bullets(stages),
            "",
            "## fallback_plan",
            "- If execution fails, persist the failed ExecutionResult, write failure memory, and hand off unresolved items.",
            "- If promotion is unsafe, keep rejected items in memory_commit.json and require human review.",
            "",
            "## risk_points",
            _bullets(risk_points),
            "",
            "## expected_outputs",
            _bullets(list(task_spec.expected_outputs or [])),
            "",
        ]
    )
