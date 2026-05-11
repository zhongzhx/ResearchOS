from __future__ import annotations

from typing import Any

from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec


SECRET_PATTERNS = ["api key", "sk-", "token=", "password", "cookie", "secret"]


def _contains_secret(value: object) -> bool:
    text = str(value or "").lower()
    return any(pattern in text for pattern in SECRET_PATTERNS)


def validate_skill_output(result: ExecutionResult, task_spec: TaskSpec, pipeline: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    redacted_outputs: dict[str, Any] = {}
    if _contains_secret(result.summary) or _contains_secret(result.logs) or _contains_secret(result.structured_outputs):
        issues.append("secret leakage detected")
        redacted_outputs = {"summary": "[redacted]", "logs": ["[redacted]"], "structured_outputs": "[redacted]"}
    expected = set(task_spec.expected_outputs or pipeline.get("expected_outputs") or [])
    if expected and not result.output_files and not result.structured_outputs:
        issues.append("missing expected output")
    target_validation = validate_before_promotion(result, "claims") if "claims" in set(pipeline.get("promotion_targets") or []) else {"valid": True, "issues": []}
    issues.extend(target_validation.get("issues") or [])
    risk_level = "high" if any("secret" in issue or "unsafe" in issue for issue in issues) else ("medium" if issues else "low")
    return {
        "control_skill": "skill-output-validator",
        "valid": not issues,
        "issues": issues,
        "risk_level": risk_level,
        "safe_to_return": not any("secret" in issue for issue in issues),
        "safe_to_promote": not issues,
        "safe_to_crystallize": result.status in {"success", "partial_success"} and not issues,
        "required_human_review": risk_level in {"medium", "high"},
        "redacted_outputs": redacted_outputs,
    }


def decide_promotion_targets(result: ExecutionResult, pipeline: dict[str, Any]) -> list[str]:
    if result.status == "failed":
        return ["failures"]
    name = str(pipeline.get("pipeline_name") or "")
    if name == "browser_research_learning":
        return ["browser_learning_evidence", "project_memory_low_confidence_notes"]
    if name == "writing_review":
        return ["reports", "decisions", "unresolved_issues"]
    return list(pipeline.get("promotion_targets") or [])


def validate_before_promotion(result: ExecutionResult, target_type: str) -> dict[str, Any]:
    issues: list[str] = []
    structured = result.structured_outputs if isinstance(result.structured_outputs, dict) else {}
    text = " ".join([str(result.summary or ""), str(structured)])
    source_ids = []
    for source in result.sources or []:
        if isinstance(source, dict):
            value = source.get("source_id") or source.get("id") or source.get("reference_id") or source.get("document_id")
            if value:
                source_ids.append(str(value))
    if target_type == "claims":
        if not source_ids and not result.skillrun_id:
            issues.append("claim promotion requires source_ids or skillrun provenance")
        if not any(token in text.lower() for token in ["p=", "p value", "confidence interval", "statistical", "replicate", "n="]):
            issues.append("claim promotion requires statistical evidence or explicit uncertainty for data-derived claims")
    if target_type in {"papers", "project memory", "context index"} and result.status == "failed":
        issues.append("failed result can only promote to failure memory")
    return {"valid": not issues, "issues": issues}


def promote_skill_outputs_to_brain(result: ExecutionResult, task_spec: TaskSpec, pipeline: dict[str, Any]) -> dict[str, Any]:
    targets = decide_promotion_targets(result, pipeline)
    validations = {target: validate_before_promotion(result, target) for target in targets}
    name = str(pipeline.get("pipeline_name") or "")
    return {
        "control_skill": "evidence-promotion",
        "project_id": task_spec.project_id,
        "task_id": task_spec.task_id,
        "pipeline_name": name,
        "targets": targets,
        "validations": validations,
        "high_confidence_claim_allowed": name not in {"browser_research_learning"} and validations.get("claims", {"valid": True})["valid"],
        "fact_evidence_allowed": name not in {"writing_review", "browser_research_learning"},
        "notes": [
            "browser learning output is low confidence only" if name == "browser_research_learning" else "",
            "peer review output is critique, not factual evidence" if name == "writing_review" else "",
        ],
    }
