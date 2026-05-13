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
    target_validation = validate_before_promotion(result, "claims") if _claim_text(result) and "claims" in set(pipeline.get("promotion_targets") or []) else {"valid": True, "issues": []}
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
        return ["criticism", "unresolved_issues"]
    return list(pipeline.get("promotion_targets") or [])


def _source_ids(result: ExecutionResult, include_skillrun: bool = False) -> list[str]:
    ids: list[str] = []
    if include_skillrun and result.skillrun_id:
        ids.append(str(result.skillrun_id))
    ids.extend(str(path) for path in (result.output_files or []))
    for source in result.sources or []:
        if isinstance(source, dict):
            value = source.get("source_id") or source.get("id") or source.get("reference_id") or source.get("document_id")
            if value:
                ids.append(str(value))
    return sorted(set(ids))


def _claim_text(result: ExecutionResult) -> str:
    structured = result.structured_outputs if isinstance(result.structured_outputs, dict) else {}
    return str(structured.get("claim_text") or (result.summary if "claim:" in str(result.summary or "").lower() else "") or "").strip()


def _has_statistics(result: ExecutionResult) -> bool:
    structured = result.structured_outputs if isinstance(result.structured_outputs, dict) else {}
    text = " ".join([str(result.summary or ""), str(structured)]).lower()
    return any(token in text for token in ["p=", "p value", "confidence interval", "statistical", "replicate", "n=", "mean", "sd", "sem"])


def _is_mechanism_claim(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(term in lowered for term in ["mechanism", "pathway", "activate", "activates", "inhibit", "inhibits", "regulate", "regulates", "mediated", "drives", "causes", "nf-kb", "tlr"])


def _safe_compiled_truth(result: ExecutionResult, fallback: str = "") -> str:
    structured = result.structured_outputs if isinstance(result.structured_outputs, dict) else {}
    if structured.get("paper_table"):
        return f"Paper evidence indexed: {structured.get('paper_table')}"
    if structured.get("narrative"):
        return str(structured.get("narrative"))
    if structured.get("analysis_result"):
        return str(structured.get("analysis_result"))
    if structured.get("critique"):
        return str(structured.get("critique"))
    return str(fallback or result.summary or "").strip()


def _memory_item(page_type: str, title: str, compiled_truth: str, source_ids: list[str], confidence: str, tags: list[str] | None = None) -> dict[str, Any]:
    return {
        "page_type": page_type,
        "title": title,
        "compiled_truth": compiled_truth,
        "source_ids": source_ids,
        "confidence": confidence,
        "tags": tags or [],
    }


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
        if not source_ids:
            issues.append("claim promotion requires source_ids")
        if not _has_statistics(result):
            issues.append("claim promotion requires statistical evidence or explicit uncertainty for data-derived claims")
    if target_type in {"papers", "project memory", "context index"} and result.status == "failed":
        issues.append("failed result can only promote to failure memory")
    return {"valid": not issues, "issues": issues}


def promote_skill_outputs_to_brain(result: ExecutionResult, task_spec: TaskSpec, pipeline: dict[str, Any]) -> dict[str, Any]:
    targets = decide_promotion_targets(result, pipeline)
    output_validation = validate_skill_output(result, task_spec, pipeline)
    name = str(pipeline.get("pipeline_name") or "")
    source_ids = _source_ids(result, include_skillrun=False)
    provenance_ids = _source_ids(result, include_skillrun=True) or [task_spec.task_id]
    claim_text = _claim_text(result)
    rejected_items: list[dict[str, Any]] = []
    memory_items: list[dict[str, Any]] = []

    if any("secret" in issue for issue in output_validation.get("issues") or []):
        return {
            "control_skill": "evidence-promotion",
            "project_id": task_spec.project_id,
            "task_id": task_spec.task_id,
            "pipeline_name": name,
            "targets": targets,
            "accepted_targets": [],
            "rejected_items": [{"target": "all", "reason": "secret leakage detected"}],
            "required_human_review": True,
            "memory_items": [],
            "validations": {},
            "high_confidence_claim_allowed": False,
            "fact_evidence_allowed": False,
            "notes": ["promotion rejected because skill-output-validator detected secret-like content"],
        }

    accepted_targets = list(targets)
    validations = {target: validate_before_promotion(result, target) for target in targets}

    if result.status == "failed":
        memory_items.append(_memory_item("failure", f"Failed task {task_spec.task_id}", result.summary or "; ".join(result.errors), provenance_ids, "medium", ["execution_failure"]))
    elif name == "browser_research_learning":
        memory_items.append(_memory_item("project", f"Browser learning {task_spec.task_id}", _safe_compiled_truth(result), provenance_ids, "low", ["browser_learning_evidence", "low_confidence"]))
    elif name == "writing_review":
        memory_items.append(_memory_item("decision", f"Review criticism {task_spec.task_id}", _safe_compiled_truth(result), provenance_ids, "low", ["criticism", "unresolved_issue"]))
    else:
        if "papers" in targets:
            memory_items.append(_memory_item("paper", f"Papers from {task_spec.task_type}", _safe_compiled_truth(result, "Paper evidence indexed."), source_ids or provenance_ids, "medium", ["paper_evidence"]))
        if "datasets" in targets and result.output_files:
            memory_items.append(_memory_item("dataset", f"Outputs from {task_spec.task_type}", "\n".join(result.output_files), provenance_ids, "medium", ["dataset"]))
        if "project memory" in targets or "project_memory" in targets:
            memory_items.append(_memory_item("project", f"Brain result {task_spec.task_type}", _safe_compiled_truth(result), provenance_ids, "medium", ["project_memory"]))
        if "decisions" in targets and not claim_text:
            memory_items.append(_memory_item("decision", f"Decision from {task_spec.task_type}", _safe_compiled_truth(result), provenance_ids, "medium", ["decision"]))

    claim_validation = validate_before_promotion(result, "claims") if claim_text else {"valid": True, "issues": []}
    if claim_text:
        truth = claim_text
        confidence = "medium"
        tags = ["claim"]
        if not claim_validation["valid"] or _is_mechanism_claim(claim_text) and not source_ids:
            confidence = "low"
            tags = ["hypothesis"]
            accepted_targets = [target for target in accepted_targets if target != "claims"]
            if "hypotheses" not in accepted_targets:
                accepted_targets.append("hypotheses")
            rejected_items.append({"target": "claims", "reason": "; ".join(claim_validation.get("issues") or ["unsourced mechanism claim downgraded"])})
            if "hypothesis" not in truth.lower():
                truth = f"Hypothesis: {truth}"
        memory_items.append(_memory_item("claim", truth[:60], truth, source_ids or provenance_ids, confidence, tags))

    if not claim_text:
        accepted_targets = [target for target in accepted_targets if target != "claims"]
    else:
        accepted_targets = [target for target in accepted_targets if target != "claims" or claim_validation.get("valid", True)]
    required_human_review = bool(rejected_items) or name == "browser_research_learning" or output_validation.get("required_human_review", False)
    return {
        "control_skill": "evidence-promotion",
        "project_id": task_spec.project_id,
        "task_id": task_spec.task_id,
        "pipeline_name": name,
        "targets": targets,
        "accepted_targets": accepted_targets,
        "rejected_items": rejected_items,
        "required_human_review": required_human_review,
        "memory_items": memory_items,
        "validations": validations,
        "high_confidence_claim_allowed": name not in {"browser_research_learning"} and validations.get("claims", {"valid": True})["valid"],
        "fact_evidence_allowed": name not in {"writing_review", "browser_research_learning"},
        "notes": [
            "browser learning output is low confidence only" if name == "browser_research_learning" else "",
            "peer review output is critique, not factual evidence" if name == "writing_review" else "",
        ],
    }
