from __future__ import annotations

from typing import Any

from backend.researchos.memory.semantic.semantic_memory_store import list_semantic_memories


def find_open_questions_without_tasks(project_id: str) -> list[dict[str, Any]]:
    return [item for item in list_semantic_memories(project_id, memory_type="open_question", status="") if not item.get("task_ids")]


def find_claims_without_validation(project_id: str) -> list[dict[str, Any]]:
    return [item for item in list_semantic_memories(project_id, memory_type="claim", status="") if not item.get("source_ids") and not item.get("artifact_ids")]


def find_failed_tasks_without_recovery(project_id: str) -> list[dict[str, Any]]:
    return [item for item in list_semantic_memories(project_id, memory_type="failure", status="") if "recovered_by" not in (item.get("provenance") or {})]


def scan_project_gaps(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "open_questions_without_tasks": find_open_questions_without_tasks(project_id),
        "claims_without_validation": find_claims_without_validation(project_id),
        "failed_tasks_without_recovery": find_failed_tasks_without_recovery(project_id),
    }

