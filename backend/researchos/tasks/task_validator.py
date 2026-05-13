from __future__ import annotations

from typing import Any

from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec
from backend.researchos.execution.execution_result_validator import validate_execution_result


SECRET_PATTERNS = ["api key", "sk-", "token=", "password", "cookie", "secret"]


def _contains_secret(value: object) -> bool:
    text = str(value or "").lower()
    return any(pattern in text for pattern in SECRET_PATTERNS)


def _source_validation(result: ExecutionResult, task_spec: TaskSpec) -> dict[str, Any]:
    issues: list[str] = []
    if (task_spec.source_requirements or {}).get("required") and not result.sources:
        issues.append("source_requirements require sources but none were returned")
    for index, source in enumerate(result.sources or []):
        if isinstance(source, dict) and not any(source.get(key) for key in ["source_id", "id", "reference_id", "document_id"]):
            issues.append(f"source {index} is missing source_id")
    return {"valid": not issues, "issues": issues, "source_count": len(result.sources or [])}


def validate_task_outputs(
    result: ExecutionResult,
    task_spec: TaskSpec,
    contract: dict[str, Any] | None = None,
    promotion_validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_validation = validate_execution_result(result, task_spec)
    source_validation = _source_validation(result, task_spec)
    secret_leakage = {
        "valid": not (_contains_secret(result.summary) or _contains_secret(result.logs) or _contains_secret(result.structured_outputs)),
        "issues": [],
    }
    if not secret_leakage["valid"]:
        secret_leakage["issues"].append("secret leakage detected")
    safety_issues: list[str] = []
    if result.status == "failed":
        safety_issues.append("execution failed")
    if result.unresolved_items:
        safety_issues.append("unresolved items remain")
    if (contract or {}).get("authorization_requirements", {}).get("blocked_if_missing"):
        safety_issues.append("required user authorization is missing")
    evidence_validation = promotion_validation or {"valid": True, "issues": []}
    all_issues = []
    all_issues.extend(output_validation.get("issues") or [])
    all_issues.extend(source_validation.get("issues") or [])
    all_issues.extend(secret_leakage.get("issues") or [])
    all_issues.extend(safety_issues)
    all_issues.extend(evidence_validation.get("issues") or [])
    safe_to_return = secret_leakage["valid"]
    safe_to_promote = result.status in {"success", "partial_success"} and not all_issues and bool(evidence_validation.get("safe_to_promote", True))
    safe_to_crystallize = result.status in {"success", "partial_success"} and secret_leakage["valid"] and bool(evidence_validation.get("safe_to_crystallize", True))
    required_human_review = bool(all_issues) or bool(evidence_validation.get("required_human_review"))
    return {
        "output_validation": output_validation,
        "evidence_validation": evidence_validation,
        "source_validation": source_validation,
        "safety_validation": {"valid": not safety_issues, "issues": safety_issues},
        "secret_leakage_check": secret_leakage,
        "safe_to_return": safe_to_return,
        "safe_to_promote": safe_to_promote,
        "safe_to_crystallize": safe_to_crystallize,
        "required_human_review": required_human_review,
        "issues": all_issues,
    }
