from __future__ import annotations

from typing import Any

from backend.researchos.memory.episodic.episodic_memory_store import list_recent_episodes


def find_reusable_success_patterns(project_id: str) -> list[dict[str, Any]]:
    return [episode for episode in list_recent_episodes(project_id, limit=100) if episode.get("outcome") == "success"]


def find_repeated_failures(project_id: str) -> list[dict[str, Any]]:
    failures = [episode for episode in list_recent_episodes(project_id, limit=100) if episode.get("outcome") == "failed"]
    return failures if len(failures) > 1 else []


def evaluate_skill_usage(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "success_patterns": find_reusable_success_patterns(project_id),
        "repeated_failures": find_repeated_failures(project_id),
    }

