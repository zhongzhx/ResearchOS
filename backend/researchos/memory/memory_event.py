from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from .memory_config import contains_secret, redact_payload, utc_now_iso
from .memory_types import EVENT_TYPES, SOURCE_TYPES


@dataclass
class MemoryEvent:
    event_id: str = field(default_factory=lambda: f"mev_{uuid4().hex[:16]}")
    event_type: str = "user_message"
    project_id: str | None = None
    conversation_id: str | None = None
    task_id: str | None = None
    skillrun_id: str | None = None
    source_id: str | None = None
    source_type: str = "chat"
    payload: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    safety_tags: list[str] = field(default_factory=list)
    contains_sensitive_data: bool = False
    global_scope: bool = False


def create_memory_event(
    event_type: str,
    project_id: str | None = None,
    conversation_id: str | None = None,
    task_id: str | None = None,
    skillrun_id: str | None = None,
    source_id: str | None = None,
    source_type: str = "chat",
    payload: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    safety_tags: list[str] | None = None,
    global_scope: bool = False,
) -> MemoryEvent:
    raw_payload = payload or {}
    sensitive = contains_secret(raw_payload)
    tags = list(safety_tags or [])
    if sensitive and "secret_redacted" not in tags:
        tags.append("secret_redacted")
    return MemoryEvent(
        event_type=event_type,
        project_id=project_id,
        conversation_id=conversation_id,
        task_id=task_id,
        skillrun_id=skillrun_id,
        source_id=source_id,
        source_type=source_type,
        payload=redact_payload(raw_payload, max_chars=8000),
        provenance=redact_payload(provenance or {}, max_chars=4000),
        safety_tags=tags,
        contains_sensitive_data=sensitive,
        global_scope=global_scope,
    )


def validate_memory_event(event: MemoryEvent) -> dict[str, Any]:
    errors: list[str] = []
    if event.event_type not in EVENT_TYPES:
        errors.append(f"unsupported event_type: {event.event_type}")
    if event.source_type not in SOURCE_TYPES:
        errors.append(f"unsupported source_type: {event.source_type}")
    if not event.project_id and not event.global_scope:
        errors.append("MemoryEvent requires project_id or global_scope=True")
    if event.task_id is None and event.event_type.startswith("task_"):
        errors.append("task event should include task_id")
    if contains_secret(event.payload):
        errors.append("payload still contains sensitive data")
    return {"valid": not errors, "errors": errors}


def redact_sensitive_event_payload(event: MemoryEvent) -> MemoryEvent:
    event.contains_sensitive_data = event.contains_sensitive_data or contains_secret(event.payload)
    event.payload = redact_payload(event.payload, max_chars=8000)
    if event.contains_sensitive_data and "secret_redacted" not in event.safety_tags:
        event.safety_tags.append("secret_redacted")
    return event


def event_to_dict(event: MemoryEvent) -> dict[str, Any]:
    return asdict(redact_sensitive_event_payload(event))


def event_from_dict(data: dict[str, Any]) -> MemoryEvent:
    return MemoryEvent(**dict(data or {}))

