from __future__ import annotations

from typing import Literal

MemoryLayer = Literal["working", "episodic", "semantic", "procedural", "archival"]
MemoryType = Literal[
    "goal",
    "constraint",
    "user_preference",
    "project_fact",
    "claim",
    "hypothesis",
    "evidence",
    "decision",
    "failure",
    "protocol",
    "dataset",
    "report",
    "episode",
    "skill_knowledge",
    "artifact_summary",
    "open_question",
    "next_action",
]
MemoryConfidence = Literal["low", "medium", "high"]
MemoryStability = Literal["volatile", "stable", "canonical"]
MemoryStatus = Literal["active", "needs_review", "superseded", "archived", "rejected"]
MemoryEventType = Literal[
    "user_message",
    "assistant_message",
    "task_created",
    "task_planned",
    "task_contracted",
    "skillrun_started",
    "skillrun_completed",
    "artifact_created",
    "validation_completed",
    "evidence_promoted",
    "claim_created",
    "claim_updated",
    "decision_made",
    "failure_logged",
    "brain_page_updated",
    "context_index_updated",
    "skill_generated",
    "user_feedback",
    "memory_archived",
    "memory_reinforced",
]
MemorySourceType = Literal["chat", "task", "skillrun", "artifact", "brain_page", "kb", "file", "user_confirmation"]

EVENT_TYPES = set(MemoryEventType.__args__)  # type: ignore[attr-defined]
SOURCE_TYPES = set(MemorySourceType.__args__)  # type: ignore[attr-defined]
MEMORY_LAYERS = set(MemoryLayer.__args__)  # type: ignore[attr-defined]
MEMORY_TYPES = set(MemoryType.__args__)  # type: ignore[attr-defined]
CONFIDENCE_LEVELS = set(MemoryConfidence.__args__)  # type: ignore[attr-defined]
STABILITY_LEVELS = set(MemoryStability.__args__)  # type: ignore[attr-defined]
MEMORY_STATUSES = set(MemoryStatus.__args__)  # type: ignore[attr-defined]

