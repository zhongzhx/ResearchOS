from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from .memory_config import contains_secret, redact_payload, utc_now_iso
from .memory_types import CONFIDENCE_LEVELS, MEMORY_LAYERS, MEMORY_STATUSES, MEMORY_TYPES, STABILITY_LEVELS


@dataclass
class MemoryItem:
    memory_id: str = field(default_factory=lambda: f"mem_{uuid4().hex[:16]}")
    project_id: str = ""
    memory_layer: str = "semantic"
    memory_type: str = "project_fact"
    title: str = ""
    content: str = ""
    structured_content: dict[str, Any] = field(default_factory=dict)
    entities: list[str] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    task_ids: list[str] = field(default_factory=list)
    skillrun_ids: list[str] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    confidence: str = "medium"
    importance_score: float = 0.5
    retrieval_count: int = 0
    last_accessed_at: str = ""
    last_confirmed_at: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    decay_score: float = 0.0
    stability: str = "stable"
    status: str = "active"
    supersedes: list[str] = field(default_factory=list)
    superseded_by: str = ""
    tags: list[str] = field(default_factory=list)
    safety_tags: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item)]
    return [str(value)] if str(value) else []


def _has_provenance(item: MemoryItem) -> bool:
    if item.source_ids or item.task_ids or item.skillrun_ids or item.artifact_ids:
        return True
    return item.provenance.get("user_confirmation") is True or item.provenance.get("source_type") == "user_confirmation"


def create_memory_item(
    project_id: str,
    memory_layer: str = "semantic",
    memory_type: str = "project_fact",
    title: str = "",
    content: str = "",
    structured_content: dict[str, Any] | None = None,
    entities: list[str] | None = None,
    relations: list[dict[str, Any]] | None = None,
    source_ids: list[str] | None = None,
    task_ids: list[str] | None = None,
    skillrun_ids: list[str] | None = None,
    artifact_ids: list[str] | None = None,
    confidence: str = "medium",
    importance_score: float = 0.5,
    stability: str = "stable",
    status: str = "active",
    supersedes: list[str] | None = None,
    tags: list[str] | None = None,
    safety_tags: list[str] | None = None,
    provenance: dict[str, Any] | None = None,
) -> MemoryItem:
    item = MemoryItem(
        project_id=str(project_id or ""),
        memory_layer=memory_layer,
        memory_type=memory_type,
        title=str(title or ""),
        content=str(redact_payload(content or "", max_chars=12000)),
        structured_content=redact_payload(structured_content or {}, max_chars=12000),
        entities=_as_list(entities),
        relations=relations or [],
        source_ids=_as_list(source_ids),
        task_ids=_as_list(task_ids),
        skillrun_ids=_as_list(skillrun_ids),
        artifact_ids=_as_list(artifact_ids),
        confidence=confidence,
        importance_score=float(importance_score),
        stability=stability,
        status=status,
        supersedes=_as_list(supersedes),
        tags=_as_list(tags),
        safety_tags=_as_list(safety_tags),
        provenance=redact_payload(provenance or {}, max_chars=4000),
    )
    if item.memory_type == "hypothesis" and item.confidence == "high":
        item.confidence = "medium"
    if item.memory_type == "hypothesis" and confidence == "medium":
        item.confidence = "low"
    if item.confidence == "high" and not _has_provenance(item):
        item.confidence = "medium"
        item.safety_tags.append("confidence_downgraded_missing_provenance")
    if item.provenance.get("pipeline_name") == "browser_research_learning" and item.confidence == "high":
        item.confidence = "low"
        item.safety_tags.append("browser_learning_low_confidence")
    if item.provenance.get("source_type") == "peer_review_simulation" and item.memory_type == "evidence":
        item.memory_type = "report"
        item.confidence = "low"
        item.safety_tags.append("peer_review_not_factual_evidence")
    if contains_secret({"content": item.content, "structured": item.structured_content}):
        item.content = str(redact_payload(item.content, max_chars=12000))
        item.structured_content = redact_payload(item.structured_content, max_chars=12000)
        item.safety_tags.append("secret_redacted")
    return item


def validate_memory_item(item: MemoryItem) -> dict[str, Any]:
    errors: list[str] = []
    if not item.project_id:
        errors.append("MemoryItem requires project_id")
    if item.memory_layer not in MEMORY_LAYERS:
        errors.append(f"unsupported memory_layer: {item.memory_layer}")
    if item.memory_type not in MEMORY_TYPES:
        errors.append(f"unsupported memory_type: {item.memory_type}")
    if item.confidence not in CONFIDENCE_LEVELS:
        errors.append(f"unsupported confidence: {item.confidence}")
    if item.stability not in STABILITY_LEVELS:
        errors.append(f"unsupported stability: {item.stability}")
    if item.status not in MEMORY_STATUSES:
        errors.append(f"unsupported status: {item.status}")
    if item.confidence == "high" and not _has_provenance(item):
        errors.append("high confidence memory requires provenance")
    if contains_secret({"content": item.content, "structured": item.structured_content, "provenance": item.provenance}):
        errors.append("memory item contains sensitive data")
    return {"valid": not errors, "errors": errors}


def memory_item_to_dict(item: MemoryItem | dict[str, Any]) -> dict[str, Any]:
    if isinstance(item, dict):
        return redact_payload(item, max_chars=12000)
    return redact_payload(asdict(item), max_chars=12000)


def memory_item_from_dict(data: dict[str, Any]) -> MemoryItem:
    return MemoryItem(**dict(data or {}))


def update_access_stats(memory_id: str) -> dict[str, Any]:
    from .semantic.semantic_memory_store import update_semantic_memory

    return update_semantic_memory(memory_id, {"retrieval_count_delta": 1, "last_accessed_at": utc_now_iso()})


def mark_superseded(memory_id: str, by_memory_id: str, reason: str) -> dict[str, Any]:
    from .semantic.semantic_memory_store import update_semantic_memory

    return update_semantic_memory(memory_id, {"status": "superseded", "superseded_by": by_memory_id, "provenance_append": {"superseded_reason": reason, "superseded_at": utc_now_iso()}})


def archive_memory_item(memory_id: str, reason: str) -> dict[str, Any]:
    from .governance.archive_policy import archive_memory

    return archive_memory(memory_id, reason)

