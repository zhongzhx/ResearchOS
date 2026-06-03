from __future__ import annotations

from pathlib import Path
from typing import Any

from .consolidation import consolidate_memory as _consolidate_memory
from .context_builder import build_memory_context as _build_memory_context
from .experiments import create_experiment as _create_experiment
from .experiments import update_experiment as _update_experiment
from .extraction import extract_memory_candidates as _extract_memory_candidates
from .files import link_file_to_experiment as _link_file_to_experiment
from .files import link_file_to_project as _link_file_to_project
from .files import register_data_file as _register_data_file
from .ledger import archive_memory as _archive_memory
from .ledger import create_memory as _create_memory
from .ledger import delete_memory as _delete_memory
from .ledger import update_memory as _update_memory
from .projects import create_group as _create_group
from .projects import create_project as _create_project
from .projects import update_project as _update_project
from .protocols import create_protocol as _create_protocol
from .protocols import update_protocol as _update_protocol
from .retrieval import list_experiment_memory as _list_experiment_memory
from .retrieval import list_project_memory as _list_project_memory
from .retrieval import retrieve_memory as _retrieve_memory
from .review_queue import enqueue_review, list_review_queue, update_review_status
from .samples import create_sample as _create_sample
from .samples import update_sample as _update_sample
from .views import get_current_project_view as _get_current_project_view


def _require_project_id(value: Any) -> str:
    project_id = str(value or "").strip()
    if not project_id:
        raise ValueError("project_id is required")
    return project_id


def create_group(agent_root: Path, data: dict[str, Any]) -> dict[str, Any]:
    return _create_group(agent_root, data)


def create_memory(agent_root: Path, event: dict[str, Any]) -> dict[str, Any]:
    return _create_memory(agent_root, event)


def update_memory(agent_root: Path, memory_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    return _update_memory(agent_root, memory_id, patch)


def archive_memory(agent_root: Path, memory_id: str, project_id: str) -> dict[str, Any]:
    return _archive_memory(agent_root, memory_id, _require_project_id(project_id))


def delete_memory(agent_root: Path, memory_id: str, project_id: str) -> dict[str, Any]:
    return _delete_memory(agent_root, memory_id, _require_project_id(project_id))


def retrieve_memory(agent_root: Path, filters: dict[str, Any]) -> list[dict[str, Any]]:
    project_id = _require_project_id(filters.get("project_id"))
    return _retrieve_memory(
        agent_root,
        user_id=filters.get("user_id", ""),
        group_id=filters.get("group_id"),
        query=filters.get("query"),
        project_id=project_id,
        experiment_id=filters.get("experiment_id"),
        memory_types=filters.get("memory_types"),
        entities=filters.get("entities"),
        tags=filters.get("tags"),
        time_range=filters.get("time_range"),
        include_archived=bool(filters.get("include_archived", False)),
        max_results=int(filters.get("max_results") or 20),
    )


def build_memory_context(agent_root: Path, payload: dict[str, Any]) -> str:
    project_id = _require_project_id(payload.get("project_id"))
    return _build_memory_context(
        agent_root,
        user_id=payload.get("user_id", "local_user"),
        group_id=payload.get("group_id"),
        project_id=project_id,
        query=payload.get("query") or payload.get("question") or "",
        max_tokens=int(payload.get("max_tokens") or 1500),
    )


def consolidate_memory(agent_root: Path, filters: dict[str, Any]) -> dict[str, Any]:
    project_id = _require_project_id(filters.get("project_id"))
    return _consolidate_memory(
        agent_root,
        user_id=filters.get("user_id", "local_user"),
        group_id=filters.get("group_id"),
        project_id=project_id,
    )


def create_project(agent_root: Path, project_data: dict[str, Any]) -> dict[str, Any]:
    return _create_project(agent_root, project_data)


def update_project(agent_root: Path, project_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    return _update_project(agent_root, project_id, patch)


def create_experiment(agent_root: Path, experiment_data: dict[str, Any]) -> dict[str, Any]:
    return _create_experiment(agent_root, experiment_data)


def update_experiment(agent_root: Path, experiment_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    return _update_experiment(agent_root, experiment_id, patch)


def create_sample(agent_root: Path, sample_data: dict[str, Any]) -> dict[str, Any]:
    return _create_sample(agent_root, sample_data)


def update_sample(agent_root: Path, sample_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    return _update_sample(agent_root, sample_id, patch)


def create_protocol(agent_root: Path, protocol_data: dict[str, Any]) -> dict[str, Any]:
    return _create_protocol(agent_root, protocol_data)


def update_protocol(agent_root: Path, protocol_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    return _update_protocol(agent_root, protocol_id, patch)


def register_data_file(agent_root: Path, file_data: dict[str, Any]) -> dict[str, Any]:
    return _register_data_file(agent_root, file_data)


def link_file_to_project(agent_root: Path, file_id: str, project_id: str) -> dict[str, Any]:
    return _link_file_to_project(agent_root, file_id, project_id)


def link_file_to_experiment(agent_root: Path, file_id: str, experiment_id: str, project_id: str) -> dict[str, Any]:
    return _link_file_to_experiment(agent_root, file_id, experiment_id, _require_project_id(project_id))


def list_project_memory(agent_root: Path, project_id: str, include_archived: bool = False) -> list[dict[str, Any]]:
    return _list_project_memory(agent_root, project_id, include_archived=include_archived)


def list_experiment_memory(agent_root: Path, experiment_id: str, project_id: str, include_archived: bool = False) -> list[dict[str, Any]]:
    return _list_experiment_memory(agent_root, experiment_id, _require_project_id(project_id), include_archived=include_archived)


def get_current_project_view(agent_root: Path, project_id: str) -> dict[str, Any] | None:
    return _get_current_project_view(agent_root, project_id)


def extract_memory_candidates(input_text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    return _extract_memory_candidates(input_text, context=context)


def extract_and_queue_if_needed(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    project_id = _require_project_id(payload.get("project_id"))
    context = {**(payload.get("context") or {}), "project_id": project_id}
    candidate = extract_memory_candidates(payload.get("input_text") or payload.get("text") or "", context)
    review = None
    if candidate.get("needs_review") or float(candidate.get("confidence", 0.0)) < 0.6:
        review = enqueue_review(
            agent_root,
            {
                "user_id": payload.get("user_id", "local_user"),
                "group_id": payload.get("group_id", ""),
                "candidate": candidate,
                "reason": "memory extraction confidence is low or project matching is uncertain",
                "confidence": candidate.get("confidence", 0.0),
            },
        )
    return {"candidate": candidate, "review_item": review}


__all__ = [
    "archive_memory",
    "build_memory_context",
    "consolidate_memory",
    "create_experiment",
    "create_group",
    "create_memory",
    "create_project",
    "create_protocol",
    "create_sample",
    "delete_memory",
    "extract_and_queue_if_needed",
    "extract_memory_candidates",
    "get_current_project_view",
    "link_file_to_experiment",
    "link_file_to_project",
    "list_experiment_memory",
    "list_project_memory",
    "list_review_queue",
    "register_data_file",
    "retrieve_memory",
    "update_experiment",
    "update_memory",
    "update_project",
    "update_protocol",
    "update_review_status",
    "update_sample",
]
