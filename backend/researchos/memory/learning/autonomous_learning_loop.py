from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.researchos.memory.learning.project_gap_scanner import scan_project_gaps
from backend.researchos.memory.memory_config import append_jsonl, ensure_memoryos_dirs, safe_project_id, utc_now_iso


def propose_learning_tasks(project_id: str) -> list[dict[str, Any]]:
    gaps = scan_project_gaps(project_id)
    recommendations = []
    for item in gaps["open_questions_without_tasks"]:
        recommendations.append({"title": f"Create validation task for open question: {item.get('title')}", "source_memory_id": item.get("memory_id"), "risk": "medium", "action": "pending_task_recommendation"})
    for item in gaps["claims_without_validation"]:
        recommendations.append({"title": f"Validate unsupported claim: {item.get('title')}", "source_memory_id": item.get("memory_id"), "risk": "high", "action": "pending_validation_recommendation"})
    for item in gaps["failed_tasks_without_recovery"]:
        recommendations.append({"title": f"Plan recovery for failed task: {item.get('title')}", "source_memory_id": item.get("memory_id"), "risk": "medium", "action": "pending_recovery_recommendation"})
    return recommendations


def _path(project_id: str) -> Path:
    return ensure_memoryos_dirs()["learning"] / safe_project_id(project_id) / "recommendations.jsonl"


def create_pending_learning_recommendation(project_id: str, recommendation: dict[str, Any]) -> dict[str, Any]:
    rec = {
        "recommendation_id": f"learn_{uuid4().hex[:12]}",
        "project_id": project_id,
        "status": "pending",
        "created_at": utc_now_iso(),
        **dict(recommendation or {}),
    }
    append_jsonl(_path(project_id), rec)
    return rec


def run_autonomous_learning_check(project_id: str, dry_run: bool = True) -> dict[str, Any]:
    recommendations = propose_learning_tasks(project_id)
    pending = [create_pending_learning_recommendation(project_id, item) for item in recommendations]
    return {"project_id": project_id, "dry_run": dry_run, "executed": False, "recommendations": pending}

