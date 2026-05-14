from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


FeatureStatus = Literal["ready", "partial", "disabled", "not_connected"]


@dataclass(frozen=True)
class ProductFeatureContract:
    feature_id: str
    display_name: str
    user_goal: str
    trigger_examples: list[str]
    preferred_pipeline: str
    required_backend_api: list[str]
    required_skills: list[str]
    expected_artifacts: list[str]
    expected_frontend_panels: list[str]
    status: FeatureStatus
    fallback_behavior: str
    safety_requirements: list[str]
    demo_available: bool = True
    not_connected_dependencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def product_response(
    *,
    ok: bool,
    feature_id: str,
    status: FeatureStatus,
    result: dict[str, Any] | None = None,
    task_lifecycle: dict[str, Any] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    memory_updates: list[dict[str, Any]] | None = None,
    next_actions: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        "ok": ok,
        "feature_id": feature_id,
        "status": status,
        "result": result or {},
        "task_lifecycle": task_lifecycle or {},
        "artifacts": artifacts or [],
        "memory_updates": memory_updates or [],
        "next_actions": next_actions or [],
        "warnings": warnings or [],
    }
    payload.update(extra)
    return payload
