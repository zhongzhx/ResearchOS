from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4


ResearchTaskStatus = Literal[
    "created",
    "planned",
    "contracted",
    "running",
    "completed",
    "failed",
    "validated",
    "handed_off",
    "committed",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ResearchTask:
    task_id: str = field(default_factory=lambda: f"task_{uuid4().hex[:12]}")
    project_id: str | None = None
    user_query: str = ""
    status: ResearchTaskStatus = "created"
    goal: dict[str, Any] = field(default_factory=dict)
    plan: str = ""
    contract: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)
    handoff: str = ""
    memory_commit: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def touch(self) -> None:
        self.updated_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResearchTask":
        data = dict(payload or {})
        for key in ["created_at", "updated_at"]:
            if isinstance(data.get(key), str):
                data[key] = datetime.fromisoformat(data[key])
        return cls(**data)
