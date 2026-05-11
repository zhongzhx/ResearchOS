from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.researchos.brain.brain_page import brain_root
from backend.researchos.execution.runtime_adapter import default_agent_root, import_research_os_mvp


REUSABLE_TASK_TYPES = {"literature_harvest", "pdf_to_evidence_matrix", "data_analysis", "sop_generation", "report_generation", "protocol_reverse_engineering", "kb_summary"}


def build_reflection_payload(skillrun_id: str) -> dict[str, Any]:
    ros = import_research_os_mvp()
    run = ros.get_skill_run(default_agent_root(), skillrun_id)
    execution = ros.list_execution_memory(default_agent_root(), project_id=run.get("project_id", ""), skill_id=run.get("skill_id", ""), limit=20)
    matching_exec = next((item for item in execution if item.get("skill_run_id") == skillrun_id), {})
    output_payload = run.get("output_payload") if isinstance(run.get("output_payload"), dict) else {}
    input_payload = run.get("input_payload") if isinstance(run.get("input_payload"), dict) else {}
    return {
        "skillrun_id": skillrun_id,
        "project_id": run.get("project_id"),
        "status": run.get("status"),
        "skill_id": run.get("skill_id"),
        "skill_name": run.get("skill_name"),
        "task_type": input_payload.get("task_type") or matching_exec.get("task_type") or output_payload.get("task_type"),
        "user_query": input_payload.get("user_query") or input_payload.get("user_message") or matching_exec.get("user_intent"),
        "input_payload": input_payload,
        "output_payload": output_payload,
        "output_files": output_payload.get("output_files") or output_payload.get("structured_outputs", {}).get("output_files") or [],
        "output_refs": run.get("output_object_refs") or [],
        "logs": run.get("logs") or [],
        "errors": [output_payload.get("error")] if output_payload.get("error") else [],
        "unresolved_items": output_payload.get("unresolved_items") or [],
        "validation_report": output_payload.get("validation_report") or {},
        "execution_memory": matching_exec,
    }


def classify_memory_targets(payload: dict[str, Any]) -> dict[str, Any]:
    targets: list[str] = []
    if payload.get("status") == "failed" or payload.get("errors"):
        targets.append("failure")
    else:
        task_type = payload.get("task_type")
        if task_type in {"report_generation", "kb_summary"}:
            targets.extend(["project", "claim"])
        if task_type in {"data_analysis", "pdf_to_evidence_matrix"} or payload.get("output_files"):
            targets.append("dataset")
        if payload.get("output_refs"):
            targets.append("project")
    return {"memory_targets": sorted(set(targets or ["project"]))}


def score_reuse_potential(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("status") == "failed":
        return {"reuse_score": 0.15, "risk_level": "medium", "requires_user_review": True}
    score = 0.25
    if payload.get("task_type") in REUSABLE_TASK_TYPES:
        score += 0.25
    if payload.get("output_files") or payload.get("output_refs"):
        score += 0.2
    if payload.get("validation_report") or payload.get("logs"):
        score += 0.15
    if payload.get("input_payload"):
        score += 0.1
    if payload.get("unresolved_items"):
        score -= 0.2
    risk = "high" if payload.get("unresolved_items") else ("medium" if score < 0.75 else "low")
    return {"reuse_score": round(max(0.0, min(score, 0.95)), 2), "risk_level": risk, "requires_user_review": True}


def write_reflection_artifacts(skillrun_id: str, reflection: dict[str, Any]) -> dict[str, Any]:
    path = brain_root() / "workflows" / "reflections" / f"{skillrun_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reflection, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {"path": str(path)}


def reflect_on_completed_skillrun(skillrun_id: str) -> dict[str, Any]:
    payload = build_reflection_payload(skillrun_id)
    targets = classify_memory_targets(payload)
    reuse = score_reuse_potential(payload)
    status = payload.get("status")
    should_crystallize = status == "completed" and reuse["reuse_score"] >= 0.7 and reuse["risk_level"] != "high"
    task_type = payload.get("task_type") or "generic_skill_task"
    reflection = {
        "skillrun_id": skillrun_id,
        "project_id": payload.get("project_id"),
        "task_type": task_type,
        "user_query": payload.get("user_query"),
        "task_summary": f"{payload.get('skill_name') or payload.get('skill_id')} completed task_type={task_type} with status={status}.",
        "memory_targets": targets["memory_targets"],
        "should_update_brain": True,
        "should_crystallize_skill": should_crystallize,
        "should_create_workflow_template": should_crystallize and task_type in REUSABLE_TASK_TYPES,
        "reuse_score": reuse["reuse_score"],
        "risk_level": reuse["risk_level"],
        "requires_user_review": reuse["requires_user_review"],
        "candidate_skill_name": f"Generated {str(task_type).replace('_', ' ').title()}",
        "candidate_skill_type": task_type,
        "evidence_items": payload.get("output_refs") or [],
        "failure_items": payload.get("errors") or [],
        "context_index_updates": [{"project_id": payload.get("project_id"), "reason": "post_task_reflection"}],
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "payload_summary": {
            "output_files": payload.get("output_files"),
            "log_count": len(payload.get("logs") or []),
            "error_count": len(payload.get("errors") or []),
        },
    }
    reflection["artifact"] = write_reflection_artifacts(skillrun_id, reflection)
    return reflection
