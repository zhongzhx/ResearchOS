from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec
from backend.researchos.execution.runtime_adapter import is_sensitive_path


SECRET_PATTERNS = ["api key", "sk-", "token=", "password", "cookie", "secret", "bearer "]


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
        if is_sensitive_path(path):
            issues.append(f"output path points to forbidden sensitive location: {path}")
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


def check_forbidden_file_access(result: ExecutionResult) -> list[str]:
    text = "\n".join(result.logs or [])
    markers = ["forbidden file access", "blocked unsafe file write", "blocked unsafe csv write", "blocked path traversal", "sensitive file"]
    return [f"forbidden file access detected: {marker}" for marker in markers if marker in text]


def _contains_secret(value: object) -> bool:
    text = str(value or "").lower()
    return any(pattern in text for pattern in SECRET_PATTERNS)


def check_secret_leakage(result: ExecutionResult) -> list[str]:
    issues: list[str] = []
    if _contains_secret(result.summary):
        issues.append("secret leakage detected in summary")
    if _contains_secret(result.logs):
        issues.append("secret leakage detected in logs")
    if _contains_secret(result.errors):
        issues.append("secret leakage detected in errors")
    if _contains_secret(result.structured_outputs):
        issues.append("secret leakage detected in structured_outputs")
    return issues


def _walk(value: Any) -> list[Any]:
    items = [value]
    if isinstance(value, dict):
        for item in value.values():
            items.extend(_walk(item))
    elif isinstance(value, list):
        for item in value:
            items.extend(_walk(item))
    return items


def check_parser_not_connected(result: ExecutionResult) -> list[str]:
    issues: list[str] = []
    for item in _walk(result.structured_outputs):
        if isinstance(item, dict) and item.get("status") == "not_connected" and item.get("tool_name") in {"pdf_parser", "data_parser"}:
            issues.append(f"{item.get('tool_name')} returned not_connected")
    return issues


def validate_execution_result(result: ExecutionResult, task_spec: TaskSpec, require_validation_report: bool = False) -> dict[str, Any]:
    issues: list[str] = []
    issues.extend(check_expected_outputs(result, task_spec))
    issues.extend(check_source_requirements(result, task_spec))
    issues.extend(check_output_file_safety(result, task_spec))
    issues.extend(check_forbidden_tool_usage(result, task_spec))
    issues.extend(check_forbidden_file_access(result))
    issues.extend(check_secret_leakage(result))
    issues.extend(check_parser_not_connected(result))
    if result.unresolved_items:
        issues.append("result contains unresolved_items")
    if require_validation_report and not result.validation_report:
        issues.append("missing validation report")
    serialized = str(result.structured_outputs) + "\n" + "\n".join(result.logs or [])
    for forbidden in ["full_agent_memory", "full_research_brain_repo", "system_prompt", "hidden_policy"]:
        if forbidden in serialized:
            issues.append(f"forbidden context leaked into result: {forbidden}")
    return {"valid": not issues, "issues": issues}
