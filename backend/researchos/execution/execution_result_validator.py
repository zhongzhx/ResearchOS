from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec


def check_expected_outputs(result: ExecutionResult, task_spec: TaskSpec) -> list[str]:
    issues: list[str] = []
    for expected in task_spec.expected_outputs or []:
        if expected == "output_files" and not result.output_files:
            issues.append("expected output_files but none were produced")
        if expected == "structured_outputs" and not result.structured_outputs:
            issues.append("expected structured_outputs but none were produced")
        if expected == "sources" and not result.sources:
            issues.append("expected sources but none were returned")
    return issues


def check_source_requirements(result: ExecutionResult, task_spec: TaskSpec) -> list[str]:
    requirements = task_spec.source_requirements or {}
    if requirements.get("required") and not result.sources:
        return ["source_requirements require sources but none were returned"]
    missing = []
    if result.sources:
        for index, source in enumerate(result.sources):
            if not any(source.get(key) for key in ["source_id", "id", "reference_id", "document_id"]):
                missing.append(f"source {index} is missing source_id")
    return missing


def check_output_file_safety(result: ExecutionResult, task_spec: TaskSpec) -> list[str]:
    issues: list[str] = []
    workspace = Path(task_spec.input_data.get("workspace_dir") or Path.cwd() / "data" / "execution_tasks" / task_spec.task_id).resolve()
    for file_path in result.output_files or []:
        path = Path(file_path).resolve()
        try:
            path.relative_to(workspace)
        except ValueError:
            issues.append(f"output path escapes task workspace: {path}")
        if str(path) in {str(Path(item).resolve()) for item in task_spec.input_files}:
            issues.append(f"output attempts to overwrite input file: {path}")
    return issues


def check_forbidden_tool_usage(result: ExecutionResult, task_spec: TaskSpec) -> list[str]:
    issues: list[str] = []
    text = "\n".join(result.logs or [])
    for tool in task_spec.forbidden_tools or []:
        if f"tool:{tool}" in text:
            issues.append(f"forbidden tool used: {tool}")
    return issues


def validate_execution_result(result: ExecutionResult, task_spec: TaskSpec) -> dict[str, Any]:
    issues: list[str] = []
    issues.extend(check_expected_outputs(result, task_spec))
    issues.extend(check_source_requirements(result, task_spec))
    issues.extend(check_output_file_safety(result, task_spec))
    issues.extend(check_forbidden_tool_usage(result, task_spec))
    if result.unresolved_items:
        issues.append("result contains unresolved_items")
    serialized = str(result.structured_outputs) + "\n" + "\n".join(result.logs or [])
    for forbidden in ["full_agent_memory", "full_research_brain_repo", "system_prompt", "hidden_policy"]:
        if forbidden in serialized:
            issues.append(f"forbidden context leaked into result: {forbidden}")
    return {"valid": not issues, "issues": issues}
